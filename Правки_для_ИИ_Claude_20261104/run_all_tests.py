"""Запуск всех проверок правок: python -I run_all_tests.py (из этой папки)."""
import runpy
import sys
from pathlib import Path

here = Path(__file__).resolve().parent
sys.path.insert(0, str(here))
total = 0
for f in sorted((here / 'tests').glob('test_*.py')):
    ns = runpy.run_path(str(f))
    tests = [v for k, v in ns.items() if k.startswith('test_') and callable(v)]
    for t in tests:
        t()
    total += len(tests)
    print(f'OK  {f.name}: {len(tests)} проверок')
print(f'всего {total} проверок — все прошли')
