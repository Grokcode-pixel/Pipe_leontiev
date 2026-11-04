"""Проверки group_cv_1104. Запуск: python -I tests/test_group_cv.py"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import group_cv_1104 as C  # noqa: E402


def make_data(n_geo=18, per=8, seed=0):
    rng = np.random.default_rng(seed)
    X, y, g = [], [], []
    for k in range(n_geo):
        td, L = rng.uniform(1.2, 1.6), rng.uniform(200, 660)
        for _ in range(per):
            dp, pc = rng.uniform(1, 4), rng.uniform(0.3, 1.6)
            X.append([td, L / 6.6, dp, pc])
            y.append(1.5 * td + 0.004 * L + 0.5 * dp - 0.3 * pc + rng.normal(0, 0.05))
            g.append(f'{td:.2f}/{L:.0f}')
    return np.array(X), np.array(y), np.array(g)


def ridge(Ztr, ytr, Zte):
    A = np.column_stack([Ztr, np.ones(len(Ztr))])
    coef = np.linalg.lstsq(A, ytr, rcond=None)[0]
    mu = np.column_stack([Zte, np.ones(len(Zte))]) @ coef
    return mu, np.full(len(Zte), 0.05)


def test_no_geometry_in_both_parts():
    X, y, g = make_data()
    for _, tr, te in C.geometry_folds(g, n_repeats=3):
        assert not set(g[tr]) & set(g[te])
        assert len(tr) + len(te) == len(g)


def test_scaling_uses_train_only():
    X, y, g = make_data()
    seen = []

    def spy(Ztr, ytr, Zte):
        seen.append((Ztr.min(0), Ztr.max(0)))
        return ridge(Ztr, ytr, Zte)
    C.repeated_group_cv(X, y, g, spy, n_repeats=2)
    for lo, hi in seen:
        assert np.allclose(lo, 0) and np.allclose(hi, 1)    # 0–1 ровно по обучающей части


def test_report_has_spread_and_per_geometry():
    X, y, g = make_data()
    r = C.repeated_group_cv(X, y, g, ridge, n_repeats=20)
    assert r['rmse_p5'] <= r['rmse_mean'] <= r['rmse_p95']
    assert len(r['per_geometry']) == len(set(g))
    assert 0.03 < r['rmse_mean'] < 0.1, r['rmse_mean']      # шум 0,05 — линейная модель его и видит


if __name__ == '__main__':
    tests = [v for k, v in dict(globals()).items() if k.startswith('test_')]
    for t in tests:
        t()
        print('OK ', t.__name__)
    print(f'все {len(tests)} проверок group_cv прошли')
