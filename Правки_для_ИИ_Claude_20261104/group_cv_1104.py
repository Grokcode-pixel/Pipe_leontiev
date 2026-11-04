"""Повторная проверка по геометриям с масштабированием внутри каждой части (предложение Claude, 04.11.2026).

Новый файл; model_compare.cv, freeze_1031.gp_cv и classifier_final.oof НЕ меняются. Нужен для отчёта о
разбросе главного числа (ошибка эффекта по геометриям) и для калибровки σ без утечки.

Что меняется по сравнению с текущими функциями:
1. Масштаб 0–1 считается по ОБУЧАЮЩЕЙ части, а не по всем точкам (в model_compare.cv и freeze_1031.gp_cv
   lo/hi берутся по всему X, включая отложенную геометрию — небольшая утечка; на ГП влияет слабо, но её
   легко убрать).
2. GroupKFold(5) детерминирован: всегда одно и то же разбиение 18 геометрий на 5 частей. Здесь геометрии
   случайно делятся на части n_repeats раз (по умолчанию 20), и в отчёт идут среднее и разброс RMSE
   (5-й…95-й процентили), а также ошибка по каждой геометрии отдельно.

fit_predict(Z_train, y_train, Z_test) -> (mu, sd) — любая модель (например, обёртка над model_compare.gp_fit:
m = gp_fit(Ztr, ytr); mu, sd = m.predict(Zte, return_std=True)).
"""
from __future__ import annotations

from collections import defaultdict
from typing import Callable

import numpy as np


def geometry_folds(groups, n_folds: int = 5, n_repeats: int = 20, seed: int = 0):
    """Случайное разбиение уникальных геометрий на n_folds частей; повторить n_repeats раз."""
    g = np.asarray(groups)
    uniq = np.unique(g)
    k = min(n_folds, len(uniq))
    rng = np.random.default_rng(seed)
    for rep in range(n_repeats):
        perm = rng.permutation(uniq)
        for f in range(k):
            test_g = perm[f::k]
            te = np.where(np.isin(g, test_g))[0]
            tr = np.where(~np.isin(g, test_g))[0]
            yield rep, tr, te


def repeated_group_cv(X, y, groups, fit_predict: Callable, n_folds: int = 5, n_repeats: int = 20, seed: int = 0) -> dict:
    X, y, g = np.asarray(X, float), np.asarray(y, float), np.asarray(groups)
    err = defaultdict(list)          # повтор -> ошибки
    by_geo = defaultdict(list)       # геометрия -> ошибки
    z_all = []
    for rep, tr, te in geometry_folds(g, n_folds, n_repeats, seed):
        lo, hi = X[tr].min(0), X[tr].max(0)
        scale = np.where(hi > lo, hi - lo, 1.0)
        mu, sd = fit_predict((X[tr] - lo) / scale, y[tr], (X[te] - lo) / scale)
        e = np.asarray(mu, float) - y[te]
        err[rep].extend(e.tolist())
        for gi, ei in zip(g[te], e):
            by_geo[str(gi)].append(float(ei))
        z_all.extend((np.abs(e) / np.maximum(np.asarray(sd, float), 1e-12)).tolist())
    rmse = np.array([np.sqrt(np.mean(np.square(v))) for v in err.values()])
    z = np.array(z_all)
    q68, q95 = float(np.quantile(z, 0.68)), float(np.quantile(z, 0.95))
    return dict(rmse_mean=float(rmse.mean()), rmse_p5=float(np.percentile(rmse, 5)), rmse_p95=float(np.percentile(rmse, 95)),
                per_geometry={k: float(np.sqrt(np.mean(np.square(v)))) for k, v in sorted(by_geo.items())},
                sigma_mult=round(max(q68, q95 / 1.96), 2), coverage_raw=(float(np.mean(z <= 1)), float(np.mean(z <= 2))),
                n_repeats=n_repeats, n_folds=n_folds)
