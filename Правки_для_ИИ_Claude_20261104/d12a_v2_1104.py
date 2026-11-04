"""D-12a v2: оценка сходимости по окну (предложение Claude, 04.11.2026).

Новый файл. Исходные dataset\\d12a.py, single_writer_d12a_1103_v1.py и gui_convergence.py НЕ меняются.
Пороги D-12a те же, не ослаблены: средний дисбаланс энергии < 1 % |Q|; колебание эффекта <= ±0,05 K;
Q <= ±1 %; расходы СВЗ и ДЗВ <= ±0,5 %; сползание < половины допусков (0,025 K; 0,5 %; 0,25 %).

Что исправлено по сравнению с d12a.evaluate (его вызывает таблица интерфейса author_gui._d12a):
1. Окно оценивается, только когда оно ПОЛНОЕ: отчёты охватывают >= window итераций и их >= 3 (как в
   single_writer_d12a). Раньше хватало 2 отчётов: на F01_P2 (итерация 1055) окно включало разгон после
   смены перепада, и все строки были красными. Теперь статус «окно не заполнено» (ok = None).
2. Можно исключить разгон: start_iteration — итерация, с которой действует конечный режим.
   Отчёты раньше неё в окно не идут.
3. Проценты нормируются на |Q| и |G|. В d12a.evaluate при отрицательном Q колебание в % было бы
   отрицательным, и проверка «<= 1 %» проходила бы всегда.
4. Баланс массы СВЗ: если в строках есть 'dm' (как у closed_samples), проверяется |dm| <= 1 % во всём окне —
   так же, как в single_writer_d12a. Иначе таблица могла стать зелёной раньше, чем D48 примет точку.
5. Плотные мониторы (>= 10 значений в окне, например report-file каждые 10 итераций): решение принимается
   по ОФИЦИАЛЬНЫМ определениям D-12a — колебание = (max − min)/2, сползание = разница средних половин окна.
   Устойчивые варианты — колебание (P95 − P5)/2 и сползание |наклон МНК|·окно/2 — только «для информации»
   (поля robust_*). Перейти на них можно только решением автора (запись D-…): robust=True.
   Поправка 04.11, вечер, по замечанию второго ИИ: первая версия молча меняла определения в плотном режиме.

Строка (row) — dict с ключами: iteration, Q, net, m_svz, m_dzv и либо 'effect', либо функция effect_fn(row).
Совместимо с gui_convergence.closed_samples (ключи те же).
"""
from __future__ import annotations

import math
import re
from typing import Callable, Iterable

import numpy as np

WINDOW = 1000
MIN_REPORTS = 3
DENSE_MIN = 10
TOL = dict(imb_pct=1.0, eff_K=0.05, Q_pct=1.0, G_pct=0.5)


def _amp(a: np.ndarray, robust: bool = False) -> float:
    """Колебание: официально (max − min)/2; устойчиво (P95 − P5)/2."""
    if robust:
        p5, p95 = np.percentile(a, [5, 95])
        return float(p95 - p5) / 2.0
    return float(a.max() - a.min()) / 2.0


def _drift(it: np.ndarray, a: np.ndarray, window: float, last: float, robust: bool = False) -> float:
    """Сползание: официально — разница средних половин окна; устойчиво — |наклон МНК|·окно/2."""
    if robust:
        if np.ptp(it) <= 0:
            return 0.0
        return abs(float(np.polyfit(it, a, 1)[0])) * window / 2.0
    h1 = it <= last - window / 2.0
    h2 = ~h1
    if not h1.any() or not h2.any():
        return float('nan')
    return abs(float(a[h1].mean() - a[h2].mean()))


def _stats(it, eff, Q, Gs, Gd, qa, gsa, gda, window, last, robust):
    return dict(eff_amp=_amp(eff, robust), Q_amp_pct=100 * _amp(Q, robust) / qa,
                Gs_amp_pct=100 * _amp(Gs, robust) / gsa, Gd_amp_pct=100 * _amp(Gd, robust) / gda,
                drift_eff=_drift(it, eff, window, last, robust), drift_Q_pct=100 * _drift(it, Q, window, last, robust) / qa,
                drift_Gs_pct=100 * _drift(it, Gs, window, last, robust) / gsa,
                drift_Gd_pct=100 * _drift(it, Gd, window, last, robust) / gda)


def evaluate(rows: Iterable[dict], effect_fn: Callable[[dict], float] | None = None, window: int = WINDOW,
             min_reports: int = MIN_REPORTS, start_iteration: int | None = None, tol: dict = TOL,
             robust: bool = False) -> dict:
    """Оценка D-12a по последнему окну. ok: True / False / None (None — окно ещё не полное или данных нет).
    robust=True — решение по устойчивым статистикам (только после решения автора)."""
    rows = sorted((dict(r) for r in rows), key=lambda r: r['iteration'])
    if start_iteration is not None:
        rows = [r for r in rows if r['iteration'] >= start_iteration]
    if not rows:
        return dict(ok=None, n=0, why='нет отчётов после начала конечного режима')
    last = rows[-1]['iteration']
    w = [r for r in rows if r['iteration'] >= last - window]
    span = last - w[0]['iteration']
    if len(w) < min_reports or span < window:
        return dict(ok=None, n=len(w), it=(w[0]['iteration'], last),
                    why=f'окно не заполнено: {len(w)} отчёт(а) на {span} итерациях; нужно >= {min_reports} отчётов на >= {window} итерациях')
    keys = ('Q', 'net', 'm_svz', 'm_dzv')
    if not all(math.isfinite(float(r[k])) for r in w for k in keys):
        return dict(ok=None, n=len(w), it=(w[0]['iteration'], last), why='в окне есть нечисловые значения')
    it = np.array([r['iteration'] for r in w], float)
    Q, net, Gs, Gd = (np.array([float(r[k]) for r in w]) for k in keys)
    if effect_fn is not None:
        eff = np.array([float(effect_fn(r)) for r in w])
    elif all('effect' in r for r in w):
        eff = np.array([float(r['effect']) for r in w])
    else:
        return dict(ok=None, n=len(w), why='нет эффекта: передайте effect_fn или поле effect')
    qa, gsa, gda = abs(Q.mean()), abs(Gs.mean()), abs(Gd.mean())
    if min(qa, gsa, gda) < 1e-12:
        return dict(ok=None, n=len(w), why='Q или расход около нуля — проценты не определены')
    dense = len(w) >= DENSE_MIN
    out = dict(n=len(w), it=(int(it[0]), int(last)), method='плотные мониторы' if dense else 'редкие отчёты',
               statistics='устойчивые (решение автора)' if robust else 'официальные D-12a',
               effect=float(eff.mean()), Q=float(Q.mean()), G_svz=float(Gs.mean()), G_dzv=float(Gd.mean()),
               imb_pct=float(100 * net.mean() / qa), imb_max_pct=float(100 * np.max(np.abs(net)) / qa))
    out.update(_stats(it, eff, Q, Gs, Gd, qa, gsa, gda, window, last, robust))
    if dense and not robust:
        out.update({'robust_' + k: v for k, v in _stats(it, eff, Q, Gs, Gd, qa, gsa, gda, window, last, True).items()})
    out = {k: (float(v) if isinstance(v, (float, np.floating)) else v) for k, v in out.items()}
    drift_ok = all(math.isfinite(out[k]) for k in ('drift_eff', 'drift_Q_pct', 'drift_Gs_pct', 'drift_Gd_pct')) and (
        out['drift_eff'] < tol['eff_K'] / 2 and out['drift_Q_pct'] < tol['Q_pct'] / 2
        and max(out['drift_Gs_pct'], out['drift_Gd_pct']) < tol['G_pct'] / 2)
    checks = dict(imb=abs(out['imb_pct']) < tol['imb_pct'], eff=out['eff_amp'] <= tol['eff_K'],
                  Q=out['Q_amp_pct'] <= tol['Q_pct'], G=max(out['Gs_amp_pct'], out['Gd_amp_pct']) <= tol['G_pct'],
                  drift=drift_ok)
    if all('dm' in r for r in w):
        dm = [float(r['dm']) for r in w]
        out['dm_max_pct'] = max(abs(x) for x in dm) if all(math.isfinite(x) for x in dm) else float('nan')
        checks['mass'] = all(math.isfinite(x) and abs(x) <= 1.0 for x in dm)
    else:
        out['dm_max_pct'] = None
    checks = {k: bool(v) for k, v in checks.items()}
    return dict(out, checks=checks, ok=all(checks.values()), why='; '.join(k for k, v in checks.items() if not v))


def rows_table(e: dict) -> list[tuple]:
    """Строки для таблицы интерфейса: (критерий, сейчас, нужно, True/False/None)."""
    if not e or e.get('ok') is None:
        return [('D-12a: ' + str((e or {}).get('why', 'нет данных')), f"отчётов {(e or {}).get('n', 0)}",
                 f'>= {MIN_REPORTS} отчётов на >= {WINDOW} итерациях', None)]
    c = e['checks']
    note = '' if e['method'] == 'плотные мониторы' else ' (оценка по редким отчётам)'
    return [('D-12a: средний дисбаланс (со знаком), % |Q|', f"{e['imb_pct']:+.2f}", '< 1 по модулю', c['imb']),
            ('D-12a: колебание эффекта, K' + note, f"± {e['eff_amp']:.3f}", '<= ± 0,05', c['eff']),
            ('D-12a: колебание Q, %' + note, f"± {e['Q_amp_pct']:.2f}", '<= ± 1', c['Q']),
            ('D-12a: колебание расходов СВЗ / ДЗВ, %', f"± {e['Gs_amp_pct']:.2f} / {e['Gd_amp_pct']:.2f}", '<= ± 0,5', c['G']),
            ('D-12a: сползание: эффект K / Q % / расход %',
             f"{e['drift_eff']:.3f} / {e['drift_Q_pct']:.2f} / {max(e['drift_Gs_pct'], e['drift_Gd_pct']):.2f}",
             '< 0,025 / 0,5 / 0,25', c['drift']),
            ('D-12a: максимум |дисбаланса| в окне, % |Q| (для информации)', f"{e['imb_max_pct']:.2f}", '—', None)] + (
            [('Баланс массы СВЗ в окне, % (как в D48)', f"{e['dm_max_pct']:.2f}", '<= 1', c['mass'])] if 'mass' in c else []) + (
            [('Устойчивые оценки (для информации): колебание эффекта K / Q % / сползание эффекта K',
              f"± {e['robust_eff_amp']:.3f} / ± {e['robust_Q_amp_pct']:.2f} / {e['robust_drift_eff']:.3f}", '—', None)]
            if 'robust_eff_amp' in e else [])


def parse_report_file(text: str, columns: dict[str, str]) -> list[dict]:
    """Строки из файла мониторов Fluent (report-file, *.out).

    columns — соответствие ключей строки и имён определений отчёта, например
    {'Q': 'q-dzv', 'net': 'net-energy', 'm_svz': 'inlet_mass_flow_rate_svz', 'm_dzv': 'inlet_mass_flow_rate_dzv'}.
    Заголовок — последняя строка до данных, в которой есть "Iteration" (в кавычках или в скобках).
    Строки данных — начинаются с номера итерации. Нечисловые строки пропускаются.
    """
    header, out = None, []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        if 'Iteration' in s and not re.match(r'^\d', s):
            names = re.findall(r'"([^"]+)"', s) or s.strip('()').split()
            header = [n.strip() for n in names]
            continue
        if header is None or not re.match(r'^\d', s):
            continue
        parts = s.split()
        if len(parts) != len(header):
            raise ValueError(f'в строке {len(parts)} чисел, а в заголовке {len(header)} имён: {header} — '
                             'проверьте кавычки в заголовке (имена с пробелами без кавычек разбиваются)')
        try:
            vals = dict(zip(header, (float(p) for p in parts)))
        except ValueError:
            continue
        row = dict(iteration=int(vals['Iteration']))
        for key, name in columns.items():
            if name not in vals:
                raise KeyError(f'в файле мониторов нет столбца {name!r}; есть: {header}')
            row[key] = vals[name]
        out.append(row)
    return out
