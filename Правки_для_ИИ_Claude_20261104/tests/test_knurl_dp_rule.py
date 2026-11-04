"""Проверки knurl_dp_rule_1104 на синтетическом законе G = a·Δp^n. Запуск: python -I tests/test_knurl_dp_rule.py"""
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import knurl_dp_rule_1104 as K  # noqa: E402

GT = K.G_TARGET


def law(dp_eq, n=0.6):
    """Форма, у которой равный расход достигается при dp_eq кПа."""
    return lambda dp: GT * (dp / dp_eq) ** n


def test_fit_exponent():
    rnd = random.Random(1)
    series = {}
    for form, dp_eq in (('F01', 14.75), ('F05', 28.9), ('F06', 88.0)):
        g = law(dp_eq, 0.6)
        series[form] = [(dp, g(dp) * (1 + rnd.uniform(-0.003, 0.003))) for dp in (0.7 * dp_eq, dp_eq, 1.36 * dp_eq)]
    r = K.fit_exponent(series)
    assert abs(r['n'] - 0.6) < 0.02, r


def test_old_rule_loses_form_new_rule_brackets():
    # как N02: равный расход около 40 кПа, а план v1 дал первый перепад 87 кПа
    g = law(40.0)
    p1 = (87.07, g(87.07))
    assert p1[1] / GT > 1.5
    old = [p1, (43.53, g(43.53))]           # план v1: второй перепад ×0,5
    assert K.bracket(old) is None              # вилки нет → форма потеряна
    dp2 = K.next_dp([p1], n=0.6)
    new = [p1, (dp2, g(dp2))]
    assert K.bracket(new) is not None, new
    e = K.equal_flow([dict(dp=dp, G=gg, Q=1000 * (gg / GT) ** 0.8, effect=3.5) for dp, gg in new])
    assert e and abs(e['dp'] - 40.0) < 1e-6 and abs(e['Q'] - 1000.0) < 1e-6, e


def test_robust_to_wrong_exponent():
    g = law(40.0, n=0.6)
    p1 = (87.07, g(87.07))
    dp2 = K.next_dp([p1], n=0.5)             # предположили n = 0,5, а на самом деле 0,6
    assert K.bracket([p1, (dp2, g(dp2))]) is not None


def test_third_point_by_secant():
    g = law(40.0, n=0.6)
    pts = [(87.07, g(87.07)), (60.0, g(60.0))]  # обе выше цели — вилки нет
    dp3 = K.next_dp(pts, n=0.5)
    assert K.bracket(pts + [(dp3, g(dp3))]) is not None


def test_no_more_points_when_hit_or_bracket():
    g = law(30.0)
    assert K.next_dp([(30.0, g(30.0))], n=0.6) is None
    assert K.next_dp([(25.0, g(25.0)), (35.0, g(35.0))], n=0.6) is None


def test_curve_points_inside_omega():
    dp = K.curve_dps(28.9, n=0.6)
    g = law(28.9, 0.6)
    ms = [g(x) / K.G_SVZ for x in dp]
    assert all(K.M_MIN <= m <= K.M_MAX for m in ms), ms
    assert K.guard(dp[2], g(dp[2])) == []
    # старые точки ×2 и ×0,5: вне Ω и в зоне сбоев (F01: 29,5 и 7,4 кПа)
    gf = law(14.75, 0.6)
    assert any('вне Ω' in f for f in K.guard(29.5, gf(29.5)))
    assert any('риск сбоя' in f for f in K.guard(7.38, gf(7.38)))


def test_no_extrapolation():
    pts = [dict(dp=50.0, G=1.1 * GT, Q=1.0, effect=1.0), dict(dp=60.0, G=1.2 * GT, Q=1.0, effect=1.0)]
    assert K.equal_flow(pts) is None


def test_first_dp_between_anchors():
    anchors = [dict(h_mm=0.1, pitch_mm=2, width_mm=0.67, dp_eq=14.91), dict(h_mm=0.2, pitch_mm=2, width_mm=0.67, dp_eq=21.18),
               dict(h_mm=0.3, pitch_mm=2, width_mm=0.67, dp_eq=28.93), dict(h_mm=1.0, pitch_mm=4.75, width_mm=1.6, dp_eq=87.99)]
    n02 = dict(h_mm=0.387, pitch_mm=4.614, width_mm=1.748)
    dp = K.first_dp(n02, anchors)
    assert 14.91 < dp < 87.99, dp
    assert K.first_dp(anchors[2], anchors) == 28.93


def test_adverse_exponent_side_still_two_runs():
    # неблагоприятная сторона (замечание второго ИИ): принятый n больше истинного
    for n_true, n_assumed in ((0.5, 0.6), (0.55, 0.6), (0.45, 0.7), (0.5, 0.7)):
        for f in (0.4, 0.7, 1.5, 2.2, 3.0):
            g = law(40.0, n_true)
            pts = [(40.0 * f, g(40.0 * f))]
            dp2 = K.next_dp(pts, n=n_assumed)
            assert K.bracket(pts + [(dp2, g(dp2))]) is not None, (n_true, n_assumed, f)


def test_real_F01_numbers():
    # факт 04.11: P1 14,75 кПа → G 0,10257; P2 7,38 кПа → G 0,07278; n ≈ 0,4955; Δp равного расхода ≈ 23,2 кПа
    p1, p2 = (14.75, 0.10257), (7.38, 0.07278)
    n = K.fit_exponent({'F01': [p1, p2]})['n']
    assert abs(n - 0.4955) < 1e-3, n
    dp_eq = K.dp_for_flow(p1[0], p1[1], GT, n)
    assert abs(dp_eq - 23.2) < 0.1, dp_eq
    g = lambda dp: p1[1] * (dp / p1[0]) ** n
    assert K.bracket([p1, p2, (29.51, g(29.51))]) is not None        # точка v1 29,51 кПа даёт вилку — не менять
    assert K.guard(29.51, g(29.51)) == []                             # m ≈ 0,89 — внутри Ω
    assert K.bracket([p1, p2, (20.0, g(20.0))]) is None               # ошибочное «≈ 20 кПа» из первой версии вилки не даёт
    dp3 = K.next_dp([p1, p2], n=n)
    assert K.bracket([p1, p2, (dp3, g(dp3))]) is not None


if __name__ == '__main__':
    tests = [v for k, v in dict(globals()).items() if k.startswith('test_')]
    for t in tests:
        t()
        print('OK ', t.__name__)
    print(f'все {len(tests)} проверок knurl_dp_rule прошли')
