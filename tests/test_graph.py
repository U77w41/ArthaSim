import numpy as np
import polars as pl
from arthasim.build import categories as c
from arthasim.build.attributes import attach_attributes
from arthasim.build.graph import build_edges
from arthasim.build.households import form_households
from arthasim.build.orgs import build_orgs
from arthasim.build.population import synthesise_persons
from helpers import D, PR, P

p = synthesise_persons(D, PR, 20_000, seed=7)
h = form_households(p, D, 20, P, seed=7)
a = attach_attributes(p, D, P, seed=7)
o = build_orgs(p, a, D, 20, P, seed=7)
E = build_edges(p, h, o, D, P, seed=7)


def of(t):
    e = E.filter(pl.col("type") == t)
    return e["src"].to_numpy(), e["dst"].to_numpy()


def test_schema_no_self_loops_and_symmetry():
    assert E.columns == ["src", "dst", "type"] and E.schema["src"] == pl.Int64
    assert (E["src"] != E["dst"]).all() and E.unique().height == E.height
    for t in (1, 2, 3):
        s, d = of(t)
        pairs = set(zip(s.tolist(), d.tolist()))
        assert pairs == {(y, x) for x, y in pairs}


def test_each_type_stays_inside_its_group():
    s, d = of(1)
    assert np.array_equal(h.household_of_person[s], h.household_of_person[d])
    assert len(s) == int((h.adults * (h.adults - 1)).sum())
    s, d = of(2)
    assert np.array_equal(o.person_employer[s], o.person_employer[d]) and (o.person_employer[s] >= 0).all()
    assert np.bincount(s).max() <= 6
    s, d = of(3)
    hs, hd = h.household_of_person[s], h.household_of_person[d]
    assert (hs != hd).all() and np.array_equal(h.locality[hs], h.locality[hd])
    assert np.array_equal(h.district[hs], h.district[hd])
    assert np.array_equal(h.head[hs], s) and np.array_equal(h.head[hd], d) and np.bincount(s).max() <= 4


def test_remittance_edges():
    s, d = of(4)
    metro_earner = (p.district == 0) & np.isin(p.life_stage, c.EARNING)
    assert metro_earner[s].all() and len(np.unique(s)) == len(s)
    assert (p.district[d] == 1).all() and np.array_equal(h.head[h.household_of_person[d]], d)
    assert abs(len(s) / metro_earner.sum() - 0.15) < 0.02


def test_single_district_and_determinism():
    one = [D[0]]
    p1 = synthesise_persons(one, PR, 3_000, seed=7)
    h1 = form_households(p1, one, 20, P, seed=7)
    a1 = attach_attributes(p1, one, P, seed=7)
    e1 = build_edges(p1, h1, build_orgs(p1, a1, one, 20, P, seed=7), one, P, seed=7)
    assert e1.filter(pl.col("type") == 4).height == 0 and e1.filter(pl.col("type") == 1).height > 0
    assert build_edges(p, h, o, D, P, seed=7).equals(E)
