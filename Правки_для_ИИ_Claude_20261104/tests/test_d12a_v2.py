"""Проверки d12a_v2_1104 на синтетических данных. Запуск: python -I tests/test_d12a_v2.py (из папки с правками)."""
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import d12a_v2_1104 as D  # noqa: E402


def row(it, Q=1066.8, net=2.0, gs=0.16312, gd=0.12840, eff=3.0):
    return dict(iteration=it, Q=Q, net=net, m_svz=gs, m_dzv=gd, effect=eff)


def test_window_not_full_like_F01_P2():
    # как на скриншоте: отчёты 555 и 1055, разгон после смены перепада, дисбаланс −11 %
    rows = [row(555, Q=1180, net=-140, gd=0.0931, eff=2.70), row(1055, Q=1066.8, net=-92.1, gd=0.08452, eff=2.96)]
    e = D.evaluate(rows)
    assert e['ok'] is None and 'окно не заполнено' in e['why'], e
    assert D.rows_table(e)[0][3] is None  # серое «нет оценки», а не красный ✗


def test_converged_sparse():
    rows = [row(i) for i in (1500, 2000, 2500)]
    e = D.evaluate(rows)
    assert e['ok'] is True and e['method'] == 'редкие отчёты', e


def test_negative_Q_sign_is_not_a_free_pass():
    # Q отрицательный (другая сторона стенки) и колебание 3 % — должно НЕ пройти
    rows = [row(1500, Q=-1000, net=1), row(2000, Q=-1060, net=1), row(2500, Q=-1000, net=1)]
    e = D.evaluate(rows)
    assert e['checks']['Q'] is False and e['ok'] is False, e
    # старая формула: 100 * amp / Q.mean() < 0 → «проходит» (ошибка, которую исправляет v2)
    Q = np.array([-1000, -1060, -1000.0])
    assert 100 * (Q.max() - Q.min()) / 2 / Q.mean() <= 1.0


def dense_rows(n=101, start=2000, step=10, eff_amp=0.0, eff_drift=0.0, q_amp_pct=0.0):
    rows = []
    for k in range(n):
        it = start + k * step
        ph = 2 * math.pi * k / 12.0
        eff = 3.0 + eff_amp * math.sin(ph) + eff_drift * k / (n - 1)
        Q = 1100.0 * (1 + q_amp_pct / 100 * math.sin(ph))
        rows.append(row(it, Q=Q, eff=eff))
    return rows


def test_dense_oscillation_threshold():
    ok = D.evaluate(dense_rows(eff_amp=0.03, q_amp_pct=0.5))
    bad = D.evaluate(dense_rows(eff_amp=0.08))
    assert ok['ok'] is True and ok['method'] == 'плотные мониторы', ok
    assert bad['ok'] is False and bad['checks']['eff'] is False, bad


def test_dense_drift_threshold():
    # линейный тренд эффекта за окно 1000 итераций: 0,04 K → сползание половин 0,02 < 0,025 (проходит);
    # 0,06 K → 0,03 > 0,025 (не проходит)
    ok = D.evaluate(dense_rows(eff_drift=0.04))
    bad = D.evaluate(dense_rows(eff_drift=0.06))
    assert abs(ok['drift_eff'] - 0.02) < 1e-3 and ok['checks']['drift'] is True, ok
    assert abs(bad['drift_eff'] - 0.03) < 1e-3 and bad['checks']['drift'] is False, bad


def test_start_iteration_excludes_transient():
    rows = [row(500, net=-120, eff=2.5), row(1000, net=-60, eff=2.8)] + [row(i) for i in (2000, 2500, 3000)]
    assert D.evaluate(rows, start_iteration=2000)['ok'] is True
    rows2 = [row(500, net=-120, eff=2.5), row(1000, net=-60, eff=2.8), row(1500)]
    assert D.evaluate(rows2, start_iteration=1000)['ok'] is None  # после разгона окно ещё не полное


def test_parse_report_file_two_header_styles():
    a = '"mon-rfile"\n"Time Step" "q-dzv" "net-e" "g-svz" "g-dzv"\n("Iteration" "q-dzv" "net-e" "g-svz" "g-dzv")\n' \
        '10 1100.5 3.1 0.16312 0.12840\n20 1100.7 3.0 0.16312 0.12841\n'
    b = 'Iteration q-dzv net-e g-svz g-dzv\n10 1100.5 3.1 0.16312 0.12840\n'
    cols = {'Q': 'q-dzv', 'net': 'net-e', 'm_svz': 'g-svz', 'm_dzv': 'g-dzv'}
    ra, rb = D.parse_report_file(a, cols), D.parse_report_file(b, cols)
    assert len(ra) == 2 and ra[1]['iteration'] == 20 and ra[1]['Q'] == 1100.7, ra
    assert len(rb) == 1 and rb[0]['m_dzv'] == 0.12840, rb
    try:
        D.parse_report_file(a, {'Q': 'нет-такого'})
        raise AssertionError('должна быть ошибка про отсутствующий столбец')
    except KeyError:
        pass


if __name__ == '__main__':
    tests = [v for k, v in dict(globals()).items() if k.startswith('test_')]
    for t in tests:
        t()
        print('OK ', t.__name__)
    print(f'все {len(tests)} проверок d12a_v2 прошли')
