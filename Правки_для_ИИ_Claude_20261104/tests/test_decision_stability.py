"""Проверки decision_stability_1104. Запуск: python -I tests/test_decision_stability.py"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import decision_stability_1104 as S  # noqa: E402


def test_correlated_neighbours_are_not_real_rivals():
    # два соседних варианта одной модели: 10,0 и 10,3 кВт, ±0,6 кВт, ошибки связаны (корреляция 0,995)
    v, s, c = [10.0, 10.3], [0.6, 0.6], np.array([[1, 0.995], [0.995, 1]])
    assert S.overlap_rivals(v, s, best=0, eps=0.5) == [1]        # нынешнее правило: «соперник» → П2
    r = S.p_change(v, s, c, best=0, eps=0.5)
    assert r['P_change'] < 0.01, r                                 # на самом деле порядок не меняется


def test_independent_equal_variants():
    r = S.p_change([10.0, 10.0], [0.5, 0.5], np.eye(2), best=0, eps=0.0, n_samples=20000)
    assert abs(r['P_change'] - 0.5) < 0.02, r


def test_independent_close_variants_are_rivals():
    r = S.p_change([10.0, 10.3], [0.6, 0.6], np.eye(2), best=0, eps=0.5, n_samples=20000)
    assert 0.1 < r['P_change'] < 0.3, r                            # при независимых ошибках соперничество есть


def test_clear_winner():
    r = S.p_change([5.0, 9.0, 12.0], [0.3, 0.3, 0.3], np.eye(3), best=0, eps=0.5)
    assert r['P_change'] == 0.0


def test_goal_max_lng():
    # СПГ: выдан 86,1 кг/ч, соседи 85,7 и 80; связанные ошибки
    c = np.array([[1, 0.99, 0.5], [0.99, 1, 0.5], [0.5, 0.5, 1]])
    r = S.p_change([86.1, 85.7, 80.0], [0.8, 0.8, 0.8], c, best=0, eps=1.0, goal='max')
    assert r['P_change'] < 0.01, r
    assert S.overlap_rivals([86.1, 85.7, 80.0], [0.8, 0.8, 0.8], best=0, eps=1.0, goal='max') == [1]


def test_posterior_correlation_from_gp_like_object():
    class FakeGP:
        def predict(self, Z, return_cov=False):
            cov = np.array([[4.0, 3.8], [3.8, 4.0]])
            return np.zeros(2), cov
    c = S.posterior_correlation(FakeGP(), np.zeros((2, 7)))
    assert np.allclose(c, [[1, 0.95], [0.95, 1]])


if __name__ == '__main__':
    tests = [v for k, v in dict(globals()).items() if k.startswith('test_')]
    for t in tests:
        t()
        print('OK ', t.__name__)
    print(f'все {len(tests)} проверок decision_stability прошли')
