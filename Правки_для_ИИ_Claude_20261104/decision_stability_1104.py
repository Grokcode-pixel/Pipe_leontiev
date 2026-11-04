"""Устойчивость выбора лучшего варианта как вероятность P_смены (предложение Claude, 04.11.2026).

Новый файл; program\\sppr.py не меняется. Предлагается сначала ПОКАЗЫВАТЬ P_смены рядом с нынешним правилом
«соперники» (_decide: пересечение интервалов подогревателя ±σ с запасом ε_N), а заменить правило — только после
решения автора и проверки на журнале решений и проверках вслепую.

Зачем. Нынешнее правило считает соперником любой вариант, у которого интервал N ± σ пересекается с интервалом
лучшего. Но ошибки соседних вариантов одной модели сильно связаны (один и тот же ГП тепла Q). Если модель
ошибается, она ошибается у соседей почти одинаково, и порядок вариантов от этого не меняется. Пересечение
интервалов этого не учитывает и даёт лишние «досчитать». P_смены — доля совместных выборок модели, в которых
лучший вариант уступает какому-либо другому больше чем на ε_N.

Как считается (линеаризация; баланс станции заново не пересчитывается):
  N_i(z) ≈ N_i + s_i·z_i, где
  N_i — подогреватель варианта i по среднему прогнозу;
  s_i = (N_i(+σ_Q) − N_i(−σ_Q)) / 2 — уже считается в sppr (dQ = ±1);
  z ~ N(0, C), C — корреляция апостериорного ГП тепла Q в точках вариантов (gp.predict(Z, return_cov=True)).
  Для цели «max СПГ» — то же с G_СПГ вместо N и обратным знаком сравнения.
Правило: П2 «устойчивость», если P_смены > α (α — параметр ЛПР, например 0,1).
"""
from __future__ import annotations

import numpy as np


def posterior_correlation(gp, Z: np.ndarray) -> np.ndarray:
    """Корреляция апостериорного ГП в точках Z (строки — варианты). gp — sklearn GaussianProcessRegressor
    (или любой объект с predict(Z, return_cov=True)). Множитель калибровки σ на корреляцию не влияет."""
    _, cov = gp.predict(np.asarray(Z, float), return_cov=True)
    cov = np.atleast_2d(np.asarray(cov, float))
    if cov.ndim == 3:            # многомерный выход sklearn: (n, n, n_targets) — берём первый
        cov = cov[:, :, 0]
    d = np.sqrt(np.clip(np.diag(cov), 1e-300, None))
    c = cov / np.outer(d, d)
    np.fill_diagonal(c, 1.0)
    return np.clip(c, -1.0, 1.0)


def p_change(value: np.ndarray, slope: np.ndarray, corr: np.ndarray, best: int = 0, eps: float = 0.5,
             goal: str = 'min', n_samples: int = 4000, seed: int = 0) -> dict:
    """P_смены лучшего варианта.

    value — показатель вариантов при среднем прогнозе (N, кВт, или G_СПГ, кг/ч); slope — его изменение на 1σ;
    corr — корреляция ошибок вариантов; best — индекс выданного варианта; eps — порог различимости ЛПР;
    goal — 'min' (топливо) или 'max' (СПГ).
    Возвращает P_change и для каждого варианта вероятность обойти лучший больше чем на eps."""
    v = np.asarray(value, float)
    s = np.asarray(slope, float)
    c = np.asarray(corr, float)
    n = len(v)
    if c.shape != (n, n) or s.shape != (n,):
        raise ValueError('размеры value, slope, corr не согласованы')
    w, U = np.linalg.eigh((c + c.T) / 2)
    L = U * np.sqrt(np.clip(w, 0, None))     # устойчиво и для почти вырожденной корреляции
    z = np.random.default_rng(seed).standard_normal((n_samples, n)) @ L.T
    sample = v + z * s
    sign = 1.0 if goal == 'min' else -1.0
    margin = sign * (sample[:, [best]] - sample)  # > 0 — вариант лучше выданного
    beats = margin > eps
    beats[:, best] = False
    return dict(P_change=float(beats.any(axis=1).mean()), P_beats=beats.mean(axis=0).tolist(), n_samples=n_samples)


def overlap_rivals(value: np.ndarray, slope: np.ndarray, best: int = 0, eps: float = 0.5, goal: str = 'min') -> list[int]:
    """Нынешнее правило sppr._decide (для сравнения): соперник, если интервалы ±|slope| пересекаются с запасом eps."""
    v = np.asarray(value, float)
    a = np.abs(np.asarray(slope, float))
    lo, hi = v - a, v + a
    if goal == 'min':
        return [i for i in range(len(v)) if i != best and lo[i] < hi[best] - eps]
    return [i for i in range(len(v)) if i != best and hi[i] > lo[best] + eps]
