import datetime as dt

import polars as pl
import pytest

from arthasim import Config, World


def _cfg(tmp_path, name):
    return Config.tier("S", persons=2_000, start="2025-04-28", out_dir=str(tmp_path / name))


def _salaried(world):
    s = world.state
    return int(s.person_ids[(s.person_employer >= 0) & (s.person_deposit >= 0)][0])


def test_watch_matches_stored_rows_and_changes_nothing(tmp_path):
    calls = []
    w = World.build(_cfg(tmp_path, "w"), seed=7)
    eid = _salaried(w)
    w.watch(eid, calls.append)
    run = w.run(until="2025-05-06")
    plain = World.build(_cfg(tmp_path, "p"), seed=7).run(until="2025-05-06")
    assert run.manifest["content_hash"] == plain.manifest["content_hash"]
    accounts = run.sql(f"select account_id from accounts where holder_entity_id = {eid}")["account_id"].to_list()
    stored = run.table("payments").filter(pl.col("payer_account_id").is_in(accounts)
                                          | pl.col("payee_account_id").is_in(accounts)).collect()
    assert calls and sum(len(c["payments"]) for c in calls) == stored.height
    got = sorted(p["payment_id"] for c in calls for p in c["payments"])
    assert got == sorted(stored["payment_id"].to_list())
    assert all(c["entity_id"] == eid and isinstance(c["date"], dt.date) for c in calls)
    assert all(p["direction"] in ("DR", "CR", "SELF") for c in calls for p in c["payments"])
    for c in calls:
        assert (c["state"] is not None) == (c["date"] == dt.date(2025, 5, 1) or c["date"] == dt.date(2025, 4, 28))
        if c["state"] is not None:
            assert c["state"]["entity_id"] == eid and c["state"]["month"] == f"{c['date']:%Y-%m}"
    last = calls[-1]
    assert set(last["balances"]) == set(accounts)
    final = run.sql(f"""select p.account_id, arg_max(p.balance_after_paise, p.journal_id * 64 + p.line_no) b
                        from postings p where p.account_id in ({', '.join(map(str, accounts))}) group by 1""")
    if last["date"] == dt.date(2025, 5, 6):
        for a, b in final.iter_rows():
            assert last["balances"][a] == b
    events = run.table("life_events").filter(pl.col("entity_id") == eid).collect()
    assert sum(len(c["events"]) for c in calls) == events.height


def test_unwatch_and_unbanked(tmp_path):
    w = World.build(_cfg(tmp_path, "u"), seed=7)
    s = w.state
    eid = int(s.person_ids[s.person_deposit < 0][0])
    calls = []
    w.watch(eid, calls.append)
    w.step(3)
    assert calls and all(set(c["balances"]) == {int(s.person_cash[eid])} for c in calls)
    n = len(calls)
    w.unwatch(eid)
    w.step(3)
    assert len(calls) == n


def test_callback_errors_stop_the_run(tmp_path):
    w = World.build(_cfg(tmp_path, "e"), seed=7)

    def boom(_):
        raise RuntimeError("stop")

    w.watch(_salaried(w), boom)
    with pytest.raises(RuntimeError, match="stop"):
        w.run(until="2025-05-06")
