#!/usr/bin/env bash
# Chạy toàn bộ test: python unittest + các test_*.sh
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
RC=0

echo "== python"
PYOUT=$(python3 -m unittest discover -s tests -p 'test_*.py' 2>&1); PYRC=$?
if [ "$PYRC" -eq 0 ]; then echo "$PYOUT" | tail -n 3; else echo "$PYOUT"; RC=1; fi

for f in tests/test_*.sh; do
  echo "== $f"
  bash "$f" || RC=1
done

[ "$RC" -eq 0 ] && echo "TẤT CẢ PASS" || echo "CÓ TEST FAIL"
exit $RC
