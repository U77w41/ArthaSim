"""Statistics shared by calibration and validation (plan 1e). Each is recomputed here by an independent query."""
import datetime as dt
import functools
import tempfile

import numpy as np
import pytest

from arthasim import Config, World, statistics as st

URBAN_SHARE = 0.36


@functools.lru_cache(maxsize=None)
def spring():
    """2,000 persons, 1 April to 30 June 2025: complete months April to June, so the window is May and June."""
    out = tempfile.mkdtemp(prefix="arthasim-stats-")
    return World.build(Config.tier("S", persons=2_000, out_dir=out), seed=11, checkpoints=False).run("2025-06-30")


@functools.lru_cache(maxsize=None)
def autumn():
    """1,500 persons, 1 August to 30 November 2025 (window September to November)."""
    out = tempfile.mkdtemp(prefix="arthasim-stats-")
    config = Config.tier("S", persons=1_500, start="2025-08-01", out_dir=out)
    return World.build(config, seed=12, checkpoints=False).run("2025-11-30")


AREA = """(select p.entity_id, p.household_id, case g.kind when 'metro' then 'urban' else 'rural' end as area
           from persons p join (select distinct district_id, kind from geo) g on g.district_id = p.district)"""


def per_area(frame):
    return {a: v for a, v in frame.iter_rows()}


def test_window_skips_the_first_and_the_incomplete_month(tmp_path):
    assert st.window(spring()) == ("2025-05", "2025-06")
    w = World.build(Config.tier("S", persons=300, out_dir=str(tmp_path)), seed=1, checkpoints=False)
    assert st.window(w.run("2025-05-20")) is None          # April complete, May not: nothing after the first month
    assert st.window(w.run("2025-06-30")) == ("2025-05", "2025-06")


def test_gini_matches_a_hand_computation():
    # Persons 1, 1 and 2 at values 1, 2 and 4: mean absolute difference over all pairs / (2 x mean).
    values = np.array([1.0, 2.0, 4.0, 4.0])
    mad = np.abs(values[:, None] - values[None, :]).mean()
    assert st.gini([1.0, 2.0, 4.0], [1, 1, 2]) == pytest.approx(mad / (2 * values.mean()))
    assert st.gini([5.0, 5.0], [1, 3]) == 0.0


def test_national_weights_urban_and_rural():
    ctx = st.context(spring())
    assert st.national(ctx, {"urban": 10.0, "rural": 1.0}) == pytest.approx(URBAN_SHARE * 10 + (1 - URBAN_SHARE) * 1)


def test_pay_and_labour_shares():
    run, ctx = spring(), st.context(spring())
    q = run.window("2025-05-01", "2025-06-30").sql(f"""
        select a.area, avg(e.monthly_income_paise) / 100 from entity_state_monthly e join {AREA} a using (entity_id)
        where e.life_stage = 'salaried' group by 1""")
    got = st.STATISTICS["pay.regular_monthly"](ctx)
    for area, value in per_area(q).items():
        assert got[area] == pytest.approx(value)
    q = run.window("2025-05-01", "2025-06-30").sql(f"""
        select a.area, avg((e.life_stage = 'salaried')::int) from entity_state_monthly e join {AREA} a using (entity_id)
        where e.life_stage in ('salaried', 'self_employed', 'gig', 'farm', 'casual') group by 1""")
    got = st.STATISTICS["labour.share.regular_salaried"](ctx)
    for area, value in per_area(q).items():
        assert got[area] == pytest.approx(value)
    casual = st.STATISTICS["pay.casual_daily"](ctx)
    q = run.window("2025-05-01", "2025-06-30").sql(f"""
        select a.area, avg(e.monthly_income_paise) / 100 / 22 from entity_state_monthly e join {AREA} a using (entity_id)
        where e.life_stage = 'casual' and e.monthly_income_paise > 0 group by 1""")
    for area, value in per_area(q).items():
        assert casual[area] == pytest.approx(value)


def test_labour_stages_gap_is_small_where_alignment_holds():
    got = st.STATISTICS["labour.stages"](st.context(spring()))
    assert set(got) == {"urban_F", "urban_M", "rural_F", "rural_M"}
    assert all(0.0 <= v < 0.05 for v in got.values())


def test_mpce_and_food_share():
    run, ctx = spring(), st.context(spring())
    spend = """('GROCERY','FOOD','FUEL','PHARMACY','APPAREL','ELECTRONICS','TRANSPORT','SERVICES','OTHER','UTILITIES',
                'TELECOM','MEDICAL')"""
    w = run.window("2025-05-01", "2025-06-30")
    paid = per_area(w.sql(f"""
        select a.area, sum(y.amount_paise) from payments y join accounts c on c.account_id = y.payer_account_id
        join {AREA} a on a.entity_id = c.holder_entity_id where y.status = 'SUCCESS' and y.purpose in {spend} group by 1"""))
    size = per_area(run.sql(f"""
        select case g.kind when 'metro' then 'urban' else 'rural' end, sum(h.adults + h.dependants)
        from households h join (select distinct district_id, kind from geo) g on g.district_id = h.district group by 1"""))
    got = st.STATISTICS["consumption.mpce"](ctx)
    for area in ("urban", "rural"):
        assert got[area] == pytest.approx(float(paid[area]) / 2 / float(size[area]) / 100)
    food = st.STATISTICS["consumption.food_share"](ctx)
    assert all(0.2 < v < 0.7 for v in food.values())
    gini = st.STATISTICS["consumption.gini"](ctx)
    assert all(0.0 < v < 1.0 for v in gini.values())


def test_counts_per_adult_and_tickets():
    run, ctx = spring(), st.context(spring())
    w = run.window("2025-05-01", "2025-06-30")
    persons = per_area(run.sql(f"select area, count(*) from {AREA} group by 1"))

    def area_counts(rail):
        return per_area(w.sql(f"""
            select coalesce(pa.area, pb.area), count(*) from payments y
            left join accounts ca on ca.account_id = y.payer_account_id left join {AREA} pa on pa.entity_id = ca.holder_entity_id
            left join accounts cb on cb.account_id = y.payee_account_id left join {AREA} pb on pb.entity_id = cb.holder_entity_id
            where y.status = 'SUCCESS' and y.rail = '{rail}' and coalesce(pa.area, pb.area) is not null group by 1"""))

    for check, rail in (("payments.upi_p2m_per_adult", "UPI_P2M"), ("payments.debit_card_per_adult", "DEBIT_CARD")):
        c = area_counts(rail)
        rate = {a: c.get(a, 0) / 2 / persons[a] for a in ("urban", "rural")}
        assert st.STATISTICS[check](ctx)["all"] == pytest.approx(URBAN_SHARE * rate["urban"] + 0.64 * rate["rural"])
    ticket = st.STATISTICS["payments.atm_ticket"](ctx)["all"]
    assert 100 <= ticket <= 1_00_000
    under = st.STATISTICS["payments.p2m_under_500"](ctx)["all"]
    assert 0.0 <= under <= 1.0


def test_balances_and_accounts():
    run, ctx = spring(), st.context(spring())
    q = run.window("2025-05-01", "2025-06-30").sql(f"""
        select a.area, sum(b.balance_paise) / 100, count(*), sum((b.balance_paise = 0)::int)
        from balances_monthly b join accounts c using (account_id) join {AREA} a on a.entity_id = c.holder_entity_id
        where c.subtype = 'basic' group by 1""")
    rows = {r[0]: r[1:] for r in q.iter_rows()}
    persons = per_area(run.sql(f"select area, count(*) from {AREA} group by 1"))
    w = {"urban": URBAN_SHARE, "rural": 0.64}
    num = sum(w[a] * float(rows[a][0]) / persons[a] for a in rows)
    den = sum(w[a] * float(rows[a][1]) / persons[a] for a in rows)
    assert st.STATISTICS["balances.basic_mean"](ctx)["all"] == pytest.approx(num / den)
    zero = st.STATISTICS["accounts.zero_balance"](ctx)["all"]
    assert zero == pytest.approx(sum(w[a] * float(rows[a][2]) / persons[a] for a in rows) / den)
    inop = st.STATISTICS["accounts.inoperative"](ctx)["all"]
    assert 0.0 <= inop <= 1.0


def test_month_start_spike_and_festival_ratio():
    run, ctx = autumn(), st.context(autumn())
    assert ctx.months == ("2025-09", "2025-11")
    spike = st.STATISTICS["payments.month_start_spike"](ctx)["all"]
    assert 0.5 < spike < 2.0
    persons = per_area(run.sql(f"select area, count(*) from {AREA} group by 1"))
    q = run.sql(f"""
        select strftime(make_timestamp(y.settle_ts) + interval 330 minute, '%Y-%m') as m, coalesce(pa.area, pb.area),
               sum(y.amount_paise) from payments y
        left join accounts ca on ca.account_id = y.payer_account_id left join {AREA} pa on pa.entity_id = ca.holder_entity_id
        left join accounts cb on cb.account_id = y.payee_account_id left join {AREA} pb on pb.entity_id = cb.holder_entity_id
        where y.status = 'SUCCESS' and y.rail in ('UPI_P2M', 'UPI_P2P') and coalesce(pa.area, pb.area) is not null
        group by 1, 2""")
    value = {}
    for m, area, v in q.iter_rows():
        w = URBAN_SHARE if area == "urban" else 0.64
        value[m] = value.get(m, 0.0) + w * float(v) / persons[area]
    per_day = {m: value[m] / d for m, d in (("2025-09", 30), ("2025-10", 31), ("2025-11", 30))}
    want = per_day["2025-10"] / ((per_day["2025-09"] + per_day["2025-11"]) / 2)
    assert st.STATISTICS["holdout.festival_uplift"](ctx)["all"] == pytest.approx(want)


def test_dbt_cashout_bins():
    got = st.STATISTICS["holdout.dbt_cashout"](st.context(autumn()))
    assert set(got) == {"d0_5", "d6_15", "d16_30"}
    assert all(0.0 <= v <= 1.0 for v in got.values()) and sum(got.values()) <= 1.0 + 1e-12


def test_missing_group_is_absent_not_nan():
    got = st.STATISTICS["labour.ur.graduate_15_29"](st.context(spring()))
    assert all(np.isfinite(v) for v in got.values())
    assert st.STATISTICS["holdout.festival_uplift"](st.context(spring())) == {}    # no September to November


def test_dbt_cashout_counts_only_withdrawals_after_the_credit():
    run, ctx = autumn(), st.context(autumn())
    ist = "cast(make_timestamp(settle_ts) + interval 330 minute as date)"
    q = run.sql(f"""
        with credit as (select payee_account_id as a, {ist} as day, min(settle_ts) as ts from payments
                        where status = 'SUCCESS' and rail = 'APBS' group by 1, 2),
             draw as (select payer_account_id as a, settle_ts as ts, {ist} as day from payments
                      where status = 'SUCCESS' and purpose = 'CASH_WITHDRAWAL'),
             last as (select max({ist}) as day from payments)
        select c.a, c.day, min(d.day) as nxt from credit c left join draw d on d.a = c.a and d.ts >= c.ts
        where c.day + interval 30 day <= (select day from last) group by 1, 2""")
    lag = [(n - d).days if n is not None else None for _, d, n in q.iter_rows()]
    n = len(lag)
    want = {"d0_5": sum(1 for x in lag if x is not None and 0 <= x <= 5) / n,
            "d6_15": sum(1 for x in lag if x is not None and 6 <= x <= 15) / n,
            "d16_30": sum(1 for x in lag if x is not None and 16 <= x <= 30) / n}
    got = st.STATISTICS["holdout.dbt_cashout"](ctx)
    assert got == pytest.approx(want)


def test_cashout_bins_by_hand():
    day = lambda d: 1_000_000 * 86_400 * d             # microseconds since 1970 (UTC midnight is 05:30 IST)
    credits = [(1, day(0) + 5_000_000), (1, day(40) + 0), (2, day(0) + 0), (3, day(0) + 0)]
    draws = [(1, day(0) + 1_000_000),                  # earlier on the credit's day: not after the credit
             (1, day(7)),                              # account 1: 7 days after its first credit
             (2, day(0) + 9_000_000),                  # account 2: same day, after the credit: 0 days
             (3, day(20))]                             # account 3: 20 days
    got = st.cashout_bins(credits, draws, last_day=day(45))
    # the credit on day 40 has no 30 days after it, so three credits count
    assert got == {"d0_5": pytest.approx(1 / 3), "d6_15": pytest.approx(1 / 3), "d16_30": pytest.approx(1 / 3)}
