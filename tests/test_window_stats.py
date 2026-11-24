"""Windowed runs and the Student-t interval (plan 1d-2, Task 9)."""
import pytest

from arthasim import metrics, stats
from run_fixture import small_run


@pytest.mark.parametrize("p, df, t", [(0.975, 1, 12.7062), (0.975, 2, 4.3027), (0.975, 9, 2.2622),
                                      (0.95, 5, 2.0150), (0.995, 9, 3.2498), (0.975, 30, 2.0423),
                                      (0.975, 1000, 1.9623), (0.5, 4, 0.0), (0.025, 9, -2.2622)])
def test_t_quantile(p, df, t):
    assert abs(stats.t_quantile(p, df) - t) < 1e-4


def test_interval():
    m, lo, hi, n = stats.interval([1, 2, 3, 4], 0.95)
    assert (m, n) == (2.5, 4) and abs(lo - 0.44574) < 1e-4 and abs(hi - 4.55426) < 1e-4
    assert stats.interval([3, 3, 3], 0.95) == (3.0, 3.0, 3.0, 3)
    assert stats.interval([5], 0.95) == (5.0, None, None, 1)
    m, lo, hi, n = stats.interval([1, 2, 3, 4], 0.90)
    assert abs(hi - lo - 2 * 2.3534 * 1.290994 / 2) < 1e-3


def test_window_sees_only_its_months():
    run = small_run()                                          # 2025-04-20 to 2025-05-25, read-only
    w = run.window("2025-05-01", "2025-05-31")
    may = run.sql(f"select count(*) as n from payments y where {metrics._MONTH} = '2025-05'")["n"][0]
    assert w.months == ("2025-05", "2025-05") and run.months is None
    assert w.table("payments").collect().height == may
    assert w.sql("select count(*) as n from payments")["n"][0] == may
    assert w.metric("txn_volume", by="month")["month"].to_list() == ["2025-05"]
    assert w.metric("txn_volume", status=None)["value"][0] == may
    assert w.table("persons").collect().height == run.table("persons").collect().height
    assert "balances_monthly" not in w.tables() and w.metric("deposit_balance").height == 0
    assert "balances_monthly" in run.window("2025-04-01", "2025-05-31").tables()
