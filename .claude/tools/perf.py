#!/usr/bin/env python3
"""Đo độ mượt của một thao tác trên máy Android thật: thời điểm present của SurfaceFlinger → khung rớt, FPS.

  perf.py <ca> [--runs 3] [--save-baseline] [--json]         # ca khai ở toolchain.json mục "perf"
  perf.py <ca> -- "input swipe 900 1100 180 1100 300" [...]  # ca tạm, không cần khai
  perf.py --list

Exit 0 đạt · 1 vượt ngân sách của ca · 2 không đo được (không có máy, không thấy layer, bảng tràn, quá ít khung).
Baseline ở docs/napoleon/perf.json, chỉ ghi khi có --save-baseline. Số chỉ có nghĩa trên bản release.
Bảng --latency giữ 127 khung gần nhất: ca dài hơn ~2 s ở 60 Hz sẽ tràn → chia ca nhỏ.
"""
import argparse
import json
import re
import shlex
import statistics
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

TOOLCHAIN_REL = Path(".claude/instructions/toolchain.json")
BASELINE_REL = Path("docs/napoleon/perf.json")
PENDING = 9223372036854775807
TABLE_ROWS = 127
IDLE_MS = 200.0
FALLBACK_PERIOD_NS = 16_666_667
MEDIAN_KEYS = ("fps", "p50_ms", "p90_ms", "max_ms", "dropped_pct")
BUDGETS = (("max_dropped_pct", "dropped_pct", 1), ("max_p90_ms", "p90_ms", 1), ("min_fps", "fps", -1))


class PerfError(Exception):
    pass


class Device:
    def __init__(self, serial):
        self.serial = serial

    def sh(self, cmd):
        r = subprocess.run(["adb", "-s", self.serial, "shell", cmd], capture_output=True, text=True,
                           stdin=subprocess.DEVNULL)
        if r.returncode != 0:
            raise PerfError(f"adb shell {cmd!r} thoát {r.returncode}: {r.stderr.strip()}")
        return r.stdout.replace("\r", "")


def find_serial():
    try:
        out = subprocess.run(["adb", "devices"], capture_output=True, text=True).stdout
    except FileNotFoundError:
        raise PerfError("không thấy adb trong PATH")
    serials = [ln.split("\t")[0] for ln in out.splitlines()[1:] if ln.endswith("\tdevice")]
    if len(serials) != 1:
        raise PerfError(f"cần đúng một máy đang cắm (thấy {len(serials)}); nhiều máy thì truyền --serial")
    return serials[0]


def parse_latency(text):
    """(chu kỳ làm tươi ns, [thời điểm present ns]). Dòng đầu của --latency là chu kỳ của chính máy đang đo."""
    lines = text.replace("\r", "").splitlines()
    head = lines[0].strip() if lines else ""
    present = []
    for ln in lines[1:]:
        f = ln.split()
        if len(f) == 3 and f[1].isdigit() and 0 < int(f[1]) < PENDING:
            present.append(int(f[1]))
    return (int(head) if head.isdigit() else 0), present


def analyze(present, start, period_ns, steps=1):
    """Thống kê các khung sau mốc `start` (khung cuối trước thao tác; --latency-clear không ăn trên mọi máy)."""
    assumed = period_ns <= 0
    period = (FALLBACK_PERIOD_NS if assumed else period_ns) / 1e6
    truncated = (start not in present) if start else len(present) >= TABLE_ROWS
    t = [x for x in present if x > start]
    if len(t) < 3:
        return {"frames": len(t), "error": "quá ít khung — thao tác không vẽ khung nào?"}
    raw = [(b - a) / 1e6 for a, b in zip(t, t[1:])]
    # Giữa N lệnh adb chỉ có tối đa N-1 quãng app đứng yên hợp lệ. Quãng dài còn lại là đứng hình giữa thao tác,
    # phải nằm trong thống kê chứ không được loại như quãng nghỉ.
    gaps = sorted((i for i, x in enumerate(raw) if x > IDLE_MS), key=lambda i: -raw[i])
    idle, stalls = set(gaps[:max(steps - 1, 0)]), gaps[max(steps - 1, 0):]
    d = sorted(x for i, x in enumerate(raw) if i not in idle)
    if not d:
        return {"frames": len(t), "error": "chỉ có quãng nghỉ giữa các lệnh, không có khung liền nhau"}
    dropped = sum(max(0, int(x / period + 0.5) - 1) for x in d)
    pick = lambda q: d[min(len(d) - 1, int(q * len(d)))]
    return {
        "frames": len(d) + 1,
        "fps": round(1000 * len(d) / sum(d), 2),
        "p50_ms": round(pick(0.5), 2), "p90_ms": round(pick(0.9), 2), "max_ms": round(d[-1], 2),
        "dropped": dropped, "dropped_pct": round(100 * dropped / (len(d) + dropped), 2),
        "idle": len(idle), "stalls": len(stalls),
        "longest_stall_ms": round(max((raw[i] for i in stalls), default=0.0), 2),
        "truncated": truncated, "period_ms": round(period, 2), "period_assumed": assumed,
    }


def verdict(now, base, higher_is_better):
    """So hai dải kết quả: chỉ kết luận khi hai dải không chồng nhau, còn lại là nhiễu giữa các lần chạy."""
    if len(now) < 2 or len(base) < 2:
        return "chưa đủ lần chạy để kết luận"
    if min(now) > max(base):
        return "tốt hơn" if higher_is_better else "tệ hơn"
    if max(now) < min(base):
        return "tệ hơn" if higher_is_better else "tốt hơn"
    return "trong nhiễu"


def read_latency(dev, layer):
    return parse_latency(dev.sh("dumpsys SurfaceFlinger --latency " + shlex.quote(layer)))


def pick_layer(dev, pkg):
    """Tên layer đổi theo ROM và theo lúc: thử mọi layer của đúng gói này, lấy cái có bảng dài nhất."""
    own = re.compile(r"(?<![\w.])" + re.escape(pkg) + "/")
    best, layer = -1, None
    for line in dev.sh("dumpsys SurfaceFlinger --list").splitlines():
        name = re.sub(r"^[0-9a-f]+ ", "", line.strip())
        if not own.search(name):
            continue
        n = len(read_latency(dev, name)[1])
        if n > best:
            best, layer = n, name
    return layer


def measure_once(dev, layer, steps, wait, sleep):
    start = (read_latency(dev, layer)[1] or [0])[-1]
    for s in steps:
        dev.sh(s)
    sleep(wait)
    period, present = read_latency(dev, layer)
    return analyze(present, start, period, len(steps))


def over_budget(summary, case):
    return [f"{metric} {summary[metric]} vượt {key} {case[key]}"
            for key, metric, sign in BUDGETS if key in case and (summary[metric] - case[key]) * sign > 0]


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def compare(result, base):
    if not base:
        return None
    if base.get("device") != result["device"]:
        return {"at": base.get("at"), "skipped": f"baseline đo trên máy khác ({base.get('device')})"}
    now = {k: [r[k] for r in result["runs"]] for k in ("dropped_pct", "fps")}
    return {"at": base.get("at"), "summary": base["summary"],
            "dropped_pct": verdict(now["dropped_pct"], base["runs"]["dropped_pct"], higher_is_better=False),
            "fps": verdict(now["fps"], base["runs"]["fps"], higher_is_better=True)}


def run_case(root, a, dev, sleep):
    cfg = load_json(root / TOOLCHAIN_REL).get("perf", {})
    case = dict(cfg.get("cases", {}).get(a.case, {}))
    if a.steps:
        case["steps"] = a.steps
    if not case.get("steps"):
        raise PerfError(f"ca '{a.case}' chưa khai ở toolchain.json mục perf.cases và không có lệnh nào sau --")
    pkg = a.package or cfg.get("package")
    if not pkg:
        raise PerfError("chưa biết gói: khai perf.package trong toolchain.json hoặc truyền --package")
    runs = a.runs or case.get("runs") or cfg.get("runs") or 3
    wait = a.wait or case.get("wait") or cfg.get("wait") or 1.5
    dev = dev or Device(a.serial or cfg.get("serial") or find_serial())
    layer = a.layer or pick_layer(dev, pkg)
    if not layer:
        raise PerfError(f"không thấy layer nào của {pkg} — app đã mở chưa? (thử --layer)")
    measured = []
    for i in range(1, runs + 1):
        r = measure_once(dev, layer, case["steps"], wait, sleep)
        if "error" in r:
            raise PerfError(f"lần {i}: {r['error']}")
        if r["truncated"]:
            raise PerfError(f"lần {i}: bảng latency tràn ({TABLE_ROWS} khung), mất khung đầu — chia ca nhỏ hơn")
        measured.append(r)
        if case.get("reset"):
            for s in case["reset"]:
                dev.sh(s)
            sleep(wait)
    summary = {k: round(statistics.median(r[k] for r in measured), 1) for k in MEDIAN_KEYS}
    summary["stalls"] = max(r["stalls"] for r in measured)
    result = {"case": a.case, "package": pkg, "layer": layer,
              "device": dev.sh("getprop ro.product.model").strip(),
              "period_ms": round(measured[0]["period_ms"], 1),
              "period_assumed": measured[0]["period_assumed"],
              "debuggable": "DEBUGGABLE" in dev.sh("dumpsys package " + shlex.quote(pkg)),
              "runs": measured, "summary": summary, "over_budget": over_budget(summary, case)}
    store = load_json(root / BASELINE_REL)
    result["baseline"] = compare(result, store.get("cases", {}).get(a.case))
    if a.save_baseline:
        store.setdefault("cases", {})[a.case] = {
            "at": date.today().isoformat(), "device": result["device"], "period_ms": result["period_ms"],
            "summary": summary, "runs": {k: [r[k] for r in measured] for k in ("dropped_pct", "fps")}}
        path = root / BASELINE_REL
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(store, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def render(d, saved):
    s = d["summary"]
    lines = [f"{d['case']}  {len(d['runs'])} lần · {d['device']} · chu kỳ {d['period_ms']} ms · layer: {d['layer']}",
             f"  FPS {s['fps']}  khoảng p50 {s['p50_ms']} p90 {s['p90_ms']} max {s['max_ms']} ms"
             f"  rớt {s['dropped_pct']}%  đứng hình {s['stalls']}"]
    b = d["baseline"]
    if b and "skipped" in b:
        lines.append(f"  không so: {b['skipped']}")
    elif b:
        o = b["summary"]
        lines.append(f"  so với baseline {b['at']}: rớt {o['dropped_pct']}% → {s['dropped_pct']}% ({b['dropped_pct']}),"
                     f" FPS {o['fps']} → {s['fps']} ({b['fps']})")
    else:
        lines.append("  chưa có baseline cho ca này (--save-baseline để ghi)")
    if saved:
        lines.append(f"  đã ghi baseline → {BASELINE_REL}")
    for v in d["over_budget"]:
        lines.append(f"  VƯỢT NGÂN SÁCH: {v}")
    if d["period_assumed"]:
        lines.append("  cảnh báo: máy không báo chu kỳ làm tươi, đang giả định 60 Hz")
    if d["debuggable"]:
        lines.append("  cảnh báo: bản debuggable — số không đại diện cho bản release")
    return "\n".join(lines)


def main(argv=None, dev=None, sleep=time.sleep):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("case", nargs="?", help="tên ca; lệnh adb shell của ca tạm đặt sau --")
    p.add_argument("--root", default=".")
    p.add_argument("--serial")
    p.add_argument("--package")
    p.add_argument("--layer", help="bỏ qua bước tự chọn layer")
    p.add_argument("--runs", type=int)
    p.add_argument("--wait", type=float, help="giây chờ sau thao tác trước khi đọc bảng")
    p.add_argument("--save-baseline", action="store_true")
    p.add_argument("--json", action="store_true")
    p.add_argument("--list", action="store_true")
    argv = list(sys.argv[1:] if argv is None else argv)
    # argparse không gom được positional nằm sau option xen giữa, nên tự cắt phần sau "--".
    cut = argv.index("--") if "--" in argv else len(argv)
    a = p.parse_args(argv[:cut])
    a.steps = argv[cut + 1:]
    root = Path(a.root).resolve()
    if a.list:
        for name, c in load_json(root / TOOLCHAIN_REL).get("perf", {}).get("cases", {}).items():
            budget = ", ".join(f"{k}={c[k]}" for k, _, _ in BUDGETS if k in c) or "chưa có ngân sách"
            print(f"{name}: {len(c.get('steps', []))} lệnh, {budget}")
        return 0
    if not a.case:
        p.error("thiếu tên ca (hoặc --list)")
    try:
        d = run_case(root, a, dev, sleep)
    except PerfError as e:
        print(f"perf: {e}", file=sys.stderr)
        return 2
    print(json.dumps(d, ensure_ascii=False, indent=2) if a.json else render(d, a.save_baseline))
    return 1 if d["over_budget"] else 0


if __name__ == "__main__":
    sys.exit(main())
