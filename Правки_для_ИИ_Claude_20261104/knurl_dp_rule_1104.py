"""Правило перепадов ДЗВ для серии накатки при равном расходе (предложение Claude, 04.11.2026).

Новый файл. knurl_dataset_queue_1104_v1.py, resume_1104_v2 и их планы НЕ меняются. Правило предлагается
зафиксировать в новой версии плана (v3) для ещё не посчитанных точек — ДО их расчёта, как и всё в проекте.

Почему (по плану knurl_dataset_queue_1104_v1.json):
1. Первый перепад — одно из трёх значений (14,75 / 28,89 / 87,07 кПа) по «ближайшей» опорной форме.
   Формы между опорными получают перепад не своего уровня: N02 (h 0,39 мм) и N08 (h 0,45 мм, проверочная!)
   — 87 кПа, как выступ 1 мм. Расход может уйти на +40…60 % от цели.
2. Второй перепад для обычных форм — заранее заданный ×0,5 или ×2. При первом расходе +40…60 % точка
   ×0,5 тоже часто выше цели. «Вилки» нет, интерполяция невозможна, экстраполяция запрещена — форма потеряна.
3. У форм-«кривых» (F01, F05, F06) точки ×2 по перепаду дают расход около +40 %, m ≈ 1,1 > 0,96 — вне Ω,
   в выводы не идут. Точки ×0,5 у F01 — 7,4 кПа, в зоне частых сбоев (< 15 кПа).

Что предлагается (всё — формулы, фиксируемые до расчёта; подбора «на глаз» нет):
- n в законе G = a·Δp^n — по уже принятым точкам форм-«кривых», общий наклон с отдельной константой у каждой формы (fit_exponent);
- второй перепад — по результату первого, с запасом 3 % на противоположную от цели сторону: «вилка» почти гарантирована (next_dp);
- третий (только если вилки нет) — по секущей двух точек в логарифмах;
- у форм-«кривых» — расходы ±20 % от цели (curve_dps): m ≈ 0,63…0,94, внутри Ω;
- защита (guard): пометка, если по прогнозу m > 0,96, m < 0,2 или Δp < 8 кПа (зона частых сбоев);
- равный расход — интерполяция в логарифмах между двумя точками вилки (equal_flow); экстраполяция запрещена, как в v1.
"""
from __future__ import annotations

import math

G_SVZ = 0.16312          # кг/с, расход СВЗ — сопло заперто (F01_P2, F05)
G_TARGET = 0.12839508333333333   # кг/с, цель равного расхода ДЗВ (A9_19, план v1)
M_MIN, M_MAX = 0.2, 0.96
DP_RISK_KPA = 8.0     # при 2–8 кПа сошлись 7 из 49 расчётов, при >= 15 кПа — 9 из 10 (КОНТЕКСТ, разд. 5)


def fit_exponent(series: dict[str, list[tuple[float, float]]]) -> dict:
    """series: форма -> [(Δp, G), ...] принятых точек. МНК: ln G = a_форма + n·ln Δp (общий n)."""
    sxx = sxy = 0.0
    per_form = {}
    for form, pts in series.items():
        pts = [(dp, g) for dp, g in pts if dp > 0 and g > 0]
        if len({round(dp, 9) for dp, _ in pts}) < 2:
            continue
        lx = [math.log(dp) for dp, _ in pts]
        ly = [math.log(g) for _, g in pts]
        mx, my = sum(lx) / len(lx), sum(ly) / len(ly)
        fxx = sum((x - mx) ** 2 for x in lx)
        fxy = sum((x - mx) * (y - my) for x, y in zip(lx, ly))
        per_form[form] = fxy / fxx
        sxx += fxx
        sxy += fxy
    if sxx == 0:
        raise ValueError('нужна хотя бы одна форма с двумя разными перепадами')
    return dict(n=sxy / sxx, per_form=per_form)


def dp_for_flow(dp_known: float, g_known: float, g_goal: float, n: float) -> float:
    return dp_known * (g_goal / g_known) ** (1.0 / n)


def bracket(points: list[tuple[float, float]], g_target: float = G_TARGET):
    """Пара соседних по расходу точек, между которыми лежит цель, или None."""
    s = sorted(points, key=lambda p: p[1])
    for a, b in zip(s, s[1:]):
        if a[1] <= g_target <= b[1] and b[1] > a[1]:
            return a, b
    return None


def next_dp(points: list[tuple[float, float]], n: float, g_target: float = G_TARGET, tol: float = 0.01,
            margin: float = 0.03) -> float | None:
    """Следующий перепад для одной формы по уже принятым точкам [(Δp, G)]; None — больше не нужно (есть прямое попадание или вилка)."""
    if not points:
        raise ValueError('сначала первый перепад (first_dp)')
    if min(abs(g / g_target - 1) for _, g in points) <= tol or bracket(points, g_target):
        return None
    near = min(points, key=lambda p: abs(p[1] / g_target - 1))
    above = near[1] > g_target
    goal = g_target * (1 - margin) if above else g_target * (1 + margin)
    n_loc = n
    if len(points) >= 2:
        a, b = sorted(points, key=lambda p: abs(p[1] / g_target - 1))[:2]
        if a[0] != b[0] and a[1] > 0 and b[1] > 0:
            cand = math.log(a[1] / b[1]) / math.log(a[0] / b[0])
            if 0.2 <= cand <= 1.5:
                n_loc = cand
    return dp_for_flow(near[0], near[1], goal, n_loc)


def curve_dps(dp_eq: float, n: float, flow_frac: float = 0.2) -> list[float]:
    """Три перепада формы-«кривой»: расход −20 %, цель, +20 % (вместо ×0,5 / ×1 / ×2 по перепаду)."""
    return [dp_eq * (1 - flow_frac) ** (1 / n), dp_eq, dp_eq * (1 + flow_frac) ** (1 / n)]


def guard(dp_kpa: float, g_pred: float, g_svz: float = G_SVZ) -> list[str]:
    m = g_pred / g_svz
    flags = []
    if m > M_MAX:
        flags.append(f'вне Ω: m ≈ {m:.2f} > {M_MAX}')
    if m < M_MIN:
        flags.append(f'вне Ω: m ≈ {m:.2f} < {M_MIN}')
    if dp_kpa < DP_RISK_KPA:
        flags.append(f'риск сбоя: Δp {dp_kpa:.1f} < {DP_RISK_KPA} кПа')
    return flags


def equal_flow(points: list[dict], g_target: float = G_TARGET, tol: float = 0.01) -> dict | None:
    """points: [dict(dp, G, Q, effect)]. Прямое попадание (|G/цель − 1| <= tol) или интерполяция в логарифмах по вилке.
    Q и Δp — в координатах ln(·) от ln G; эффект — линейно по ln G. Экстраполяция запрещена → None."""
    best = min(points, key=lambda p: abs(p['G'] / g_target - 1))
    if abs(best['G'] / g_target - 1) <= tol:
        return dict(kind='прямо', **{k: best[k] for k in ('dp', 'Q', 'effect')}, G=best['G'])
    s = sorted(points, key=lambda p: p['G'])
    for a, b in zip(s, s[1:]):
        if a['G'] <= g_target <= b['G'] and b['G'] > a['G']:
            t = (math.log(g_target) - math.log(a['G'])) / (math.log(b['G']) - math.log(a['G']))
            lg = lambda k: math.exp(math.log(a[k]) + t * (math.log(b[k]) - math.log(a[k])))
            return dict(kind='интерполяция по вилке (не CFD)', dp=lg('dp'), Q=lg('Q'),
                        effect=a['effect'] + t * (b['effect'] - a['effect']), G=g_target, bracket=(a['dp'], b['dp']))
    return None


def first_dp(shape: dict, anchors: list[dict], power: float = 2.0, weights: tuple = (1.0, 0.25, 0.25)) -> float:
    """Априорный перепад равного расхода для новой формы: взвешивание по расстоянию (IDW) в ln Δp_eq.

    shape, anchors: dict(h_mm, pitch_mm, width_mm[, dp_eq]); координаты нормированы на диапазон плана:
    lg h ∈ [−1, 0], шаг ∈ [1,5; 4,75], w/шаг ∈ [0,2; 0,6]; веса осей (h, шаг, w/шаг) — по умолчанию высота
    главная (сопротивление определяет прежде всего высота выступа). Это только стартовое приближение —
    второй перепад всё равно считается по фактическому расходу (next_dp). Опорные формы — все уже принятые
    точки равного расхода (F01…F06, KM01–KM03, KQ), по мере появления — и новые формы серии."""
    def z(p):
        return (weights[0] * (math.log10(p['h_mm']) + 1.0), weights[1] * (p['pitch_mm'] - 1.5) / 3.25,
                weights[2] * (p['width_mm'] / p['pitch_mm'] - 0.2) / 0.4)
    zs = z(shape)
    num = den = 0.0
    for a in anchors:
        d = math.dist(zs, z(a))
        if d < 1e-9:
            return a['dp_eq']
        w = d ** -power
        num += w * math.log(a['dp_eq'])
        den += w
    return math.exp(num / den)
