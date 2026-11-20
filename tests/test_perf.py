"""perf.py: bảng --latency của SurfaceFlinger → khung rớt theo chu kỳ thật của máy, đứng hình, tràn bảng, baseline."""
import contextlib
import io
import json
import shlex
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".claude" / "tools"))
import perf  # noqa: E402

HZ60 = 16_666_667
HZ120 = 8_333_333
FRAME = 16.667
APP = "com.demo.app/com.demo.app.MainActivity#0"


def timeline(intervals_ms, first=1_000_000_000):
    t = [first]
    for iv in intervals_ms:
        t.append(t[-1] + int(iv * 1e6))
    return t


class FakeDevice:
    """Mỗi lệnh `input` đẩy một lô khung vào layer của app, sau một quãng nghỉ 1 s như adb thật."""

    def __init__(self, batches=(), layers=None, model="SM-TEST", period=HZ60, debuggable=False):
        self.layers = layers if layers is not None else {APP: timeline([FRAME] * 5)}
        self.batches = list(batches)
        self.model, self.period, self.debuggable = model, period, debuggable
        self.steps = []

    def table(self, name):
        rows = [f"0\t{t}\t0" for t in self.layers.get(name, [])[-perf.TABLE_ROWS:]]
        return "\n".join([str(self.period)] + rows) + "\n"

    def sh(self, cmd):
        if cmd == "dumpsys SurfaceFlinger --list":
            return "\n".join(self.layers) + "\n"
        if cmd.startswith("dumpsys SurfaceFlinger --latency"):
            return self.table(shlex.split(cmd)[-1])
        if cmd == "getprop ro.product.model":
            return self.model + "\n"
        if cmd.startswith("dumpsys package"):
            return "    flags=[ DEBUGGABLE HAS_CODE ]\n" if self.debuggable else "    flags=[ HAS_CODE ]\n"
        self.steps.append(cmd)
        if cmd.startswith("input"):
            batch = self.batches.pop(0) if self.batches else [FRAME] * 60
            self.layers[APP] += timeline(batch, self.layers[APP][-1] + 1_000_000_000)
        return ""


class ParseTest(unittest.TestCase):
    def test_reads_period_and_skips_pending_rows(self):
        text = f"{HZ120}\r\n0\t100\t0\r\n0\t{perf.PENDING}\t0\r\n0\t0\t0\r\n0\t200\t0\r\n"
        self.assertEqual(perf.parse_latency(text), (HZ120, [100, 200]))

    def test_missing_header_gives_zero_period(self):
        self.assertEqual(perf.parse_latency("")[0], 0)


class AnalyzeTest(unittest.TestCase):
    def run_on(self, intervals, period=HZ60, steps=1):
        t = timeline(intervals)
        return perf.analyze(t, t[0], period, steps)

    def test_smooth_60hz(self):
        r = self.run_on([FRAME] * 60)
        self.assertAlmostEqual(r["fps"], 60.0, delta=0.1)
        self.assertEqual((r["dropped"], r["stalls"], r["truncated"]), (0, 0, False))

    def test_threshold_follows_device_period(self):
        """Cùng nhịp 16,7 ms: mượt trên máy 60 Hz nhưng là rớt một nửa số khung trên máy 120 Hz."""
        r = self.run_on([FRAME] * 31, period=HZ120)
        self.assertEqual(r["dropped"], 30)
        self.assertAlmostEqual(r["dropped_pct"], 50.0, delta=0.1)

    def test_long_interval_counts_every_missed_frame(self):
        r = self.run_on([FRAME] * 10 + [50.0] + [FRAME] * 10)
        self.assertEqual(r["dropped"], 2)

    def test_gap_inside_single_step_is_a_stall_not_idle(self):
        r = self.run_on([FRAME] * 20 + [250.0] + [FRAME] * 20)
        self.assertEqual((r["stalls"], r["idle"]), (1, 0))
        self.assertAlmostEqual(r["max_ms"], 250.0, delta=0.1)
        self.assertEqual(r["dropped"], 14)

    def test_gap_between_two_steps_is_idle(self):
        r = self.run_on([FRAME] * 20 + [250.0] + [FRAME] * 20, steps=2)
        self.assertEqual((r["stalls"], r["idle"], r["dropped"]), (0, 1, 0))
        self.assertLess(r["max_ms"], 20)

    def test_extra_gaps_beyond_step_boundaries_are_stalls(self):
        r = self.run_on([FRAME] * 5 + [900.0] + [FRAME] * 5 + [300.0] + [FRAME] * 5, steps=2)
        self.assertEqual((r["idle"], r["stalls"]), (1, 1))
        self.assertAlmostEqual(r["longest_stall_ms"], 300.0, delta=0.1)

    def test_truncated_when_start_mark_left_the_table(self):
        t = timeline([FRAME] * 20)
        self.assertTrue(perf.analyze(t, t[0] - 5, HZ60, 1)["truncated"])

    def test_too_few_frames_is_an_error(self):
        t = timeline([FRAME] * 5)
        self.assertIn("error", perf.analyze(t, t[-2], HZ60, 1))

    def test_unknown_period_is_flagged(self):
        t = timeline([FRAME] * 10)
        self.assertTrue(perf.analyze(t, t[0], 0, 1)["period_assumed"])


class VerdictTest(unittest.TestCase):
    def test_ranges_apart(self):
        self.assertEqual(perf.verdict([1.0, 1.2], [3.0, 3.4], higher_is_better=False), "tốt hơn")
        self.assertEqual(perf.verdict([55, 56], [59, 60], higher_is_better=True), "tệ hơn")

    def test_overlap_is_noise(self):
        self.assertEqual(perf.verdict([1.0, 3.1], [3.0, 3.4], higher_is_better=False), "trong nhiễu")

    def test_single_run_cannot_conclude(self):
        self.assertIn("chưa đủ", perf.verdict([1.0], [3.0, 3.4], higher_is_better=False))


class MainTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / ".claude" / "instructions").mkdir(parents=True)
        self.addCleanup(self.tmp.cleanup)

    def config(self, **case):
        cfg = {"perf": {"package": "com.demo.app", "runs": 3, "cases": {
            "vuot": {"steps": ["input swipe 900 1100 180 1100 300"], "reset": ["input swipe 180 1100 900 1100 300"],
                     **case}}}}
        (self.root / perf.TOOLCHAIN_REL).write_text(json.dumps(cfg), encoding="utf-8")

    def call(self, dev, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = perf.main(["--root", str(self.root), *argv], dev=dev, sleep=lambda s: None)
        return rc, out.getvalue(), err.getvalue()

    def test_runs_reset_between_runs_and_reports_median(self):
        self.config()
        dev = FakeDevice()
        rc, out, _ = self.call(dev, "vuot", "--json")
        d = json.loads(out)
        self.assertEqual(rc, 0)
        self.assertEqual(len(d["runs"]), 3)
        self.assertEqual(len(dev.steps), 6)
        self.assertAlmostEqual(d["summary"]["fps"], 60.0, delta=0.1)
        self.assertEqual((d["layer"], d["device"], d["period_ms"]), (APP, "SM-TEST", 16.7))

    def test_over_budget_exits_1(self):
        self.config(max_dropped_pct=2)
        janky = [FRAME] * 20 + [50.0] * 10 + [FRAME] * 20
        dev = FakeDevice(batches=[janky, [FRAME] * 60, janky, [FRAME] * 60, janky])
        rc, out, _ = self.call(dev, "vuot")
        self.assertEqual(rc, 1)
        self.assertIn("VƯỢT NGÂN SÁCH", out)

    def test_overflowing_table_exits_2(self):
        self.config()
        rc, _, err = self.call(FakeDevice(batches=[[FRAME] * 140]), "vuot")
        self.assertEqual(rc, 2)
        self.assertIn("tràn", err)

    def test_baseline_saved_then_compared(self):
        self.config()
        janky = [FRAME] * 20 + [50.0] * 10 + [FRAME] * 20
        rc, _, _ = self.call(FakeDevice(batches=[janky, [FRAME] * 60] * 3), "vuot", "--save-baseline")
        self.assertEqual(rc, 0)
        saved = json.loads((self.root / perf.BASELINE_REL).read_text(encoding="utf-8"))
        self.assertEqual(len(saved["cases"]["vuot"]["runs"]["dropped_pct"]), 3)
        rc, out, _ = self.call(FakeDevice(), "vuot")
        self.assertIn("tốt hơn", out)
        self.assertEqual(json.loads((self.root / perf.BASELINE_REL).read_text(encoding="utf-8")), saved,
                         "không có --save-baseline thì không được ghi đè")

    def test_baseline_from_other_device_is_not_compared(self):
        self.config()
        self.call(FakeDevice(), "vuot", "--save-baseline")
        _, out, _ = self.call(FakeDevice(model="Pixel 8"), "vuot")
        self.assertIn("máy khác", out)

    def test_ad_hoc_steps_after_double_dash(self):
        self.config()
        dev = FakeDevice()
        rc, _, _ = self.call(dev, "tam", "--runs", "1", "--", "input tap 1 1")
        self.assertEqual((rc, dev.steps), (0, ["input tap 1 1"]))

    def test_unknown_case_without_steps_exits_2(self):
        self.config()
        rc, _, err = self.call(FakeDevice(), "khong-co")
        self.assertEqual(rc, 2)
        self.assertIn("perf.cases", err)

    def test_picks_app_layer_with_longest_table_and_ignores_other_packages(self):
        self.config()
        layers = {"com.demo.app.dev/com.demo.app.MainActivity#0": timeline([FRAME] * 100),
                  "SurfaceView - com.demo.app/com.demo.app.MainActivity#0": timeline([FRAME] * 2),
                  APP: timeline([FRAME] * 5)}
        _, out, _ = self.call(FakeDevice(layers=layers), "vuot", "--json")
        self.assertEqual(json.loads(out)["layer"], APP)

    def test_debuggable_build_is_warned(self):
        self.config()
        _, out, _ = self.call(FakeDevice(debuggable=True), "vuot")
        self.assertIn("debuggable", out)

    def test_list_prints_cases(self):
        self.config(max_dropped_pct=2)
        rc, out, _ = self.call(None, "--list")
        self.assertEqual(rc, 0)
        self.assertIn("vuot", out)


if __name__ == "__main__":
    unittest.main()
