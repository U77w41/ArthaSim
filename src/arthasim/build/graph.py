"""Social graph: household, co-worker, neighbour and remittance edges."""
from __future__ import annotations

from typing import Sequence

import numpy as np
import polars as pl

from arthasim.build import categories as c
from arthasim.build.households import Households
from arthasim.build.marginals import DistrictMarginals
from arthasim.build.orgs import Orgs
from arthasim.build.population import Persons
from arthasim.engine import rng
from arthasim.params import ParamRegistry

HOUSEHOLD, COWORKER, NEIGHBOUR, REMITTANCE = 1, 2, 3, 4
_EMPTY = np.empty(0, dtype=np.int64)


def _grouped(members: np.ndarray, group: np.ndarray, tie: np.ndarray):
    """Members sorted by group then `tie`, with each element's group start and size."""
    order = np.lexsort((tie, group))
    members, group = members[order], group[order]
    starts = np.flatnonzero(np.diff(group, prepend=group[0] - 1) != 0) if members.size else _EMPTY
    sizes = np.diff(np.append(starts, members.size))
    return members, np.repeat(starts, sizes), np.repeat(sizes, sizes)


def _ring(members: np.ndarray, group: np.ndarray, tie: np.ndarray, forward: int) -> tuple[np.ndarray, np.ndarray]:
    """Link each member to the next `forward` members of its group on a ring; both directions."""
    if members.size == 0:
        return _EMPTY, _EMPTY
    members, start, size = _grouped(members, group, tie)
    pos = np.arange(members.size)
    src, dst = [], []
    for k in range(1, forward + 1):
        nxt = start + (pos - start + k) % size
        ok = nxt != pos
        src.append(members[pos[ok]])
        dst.append(members[nxt[ok]])
    s, d = np.concatenate(src), np.concatenate(dst)
    pairs = np.unique(np.stack([np.concatenate([s, d]), np.concatenate([d, s])], axis=1), axis=0)
    return pairs[:, 0], pairs[:, 1]


def build_edges(persons: Persons, households: Households, orgs: Orgs, districts: Sequence[DistrictMarginals],
                params: ParamRegistry, seed: int) -> pl.DataFrame:
    n = len(persons)
    ids = np.arange(n, dtype=np.int64)
    S = rng.stream_id
    hh = households.household_of_person
    edges: list[tuple[np.ndarray, np.ndarray, int]] = []

    # Household: every ordered pair of members.
    members, start, size = _grouped(ids, hh, ids)
    pos = np.arange(n)
    for a in range(int(households.adults.max()) if n else 0):
        for b in range(int(households.adults.max())):
            if a == b:
                continue
            first = (pos == start) & (size > max(a, b))
            edges.append((members[pos[first] + a], members[pos[first] + b], HOUSEHOLD))

    # Co-workers: a ring inside each employer.
    staff = np.flatnonzero(orgs.person_employer >= 0)
    forward = (int(params.get("graph.coworker_degree")) + 1) // 2
    s, d = _ring(staff, orgs.person_employer[staff], rng.uniform(seed, S("graph.coworker"), staff, 0), forward)
    edges.append((s, d, COWORKER))

    # Neighbours: a ring over household heads inside each (district, locality).
    heads = households.head
    place = households.district * 1_000_000 + households.locality
    forward = (int(params.get("graph.neighbour_degree")) + 1) // 2
    s, d = _ring(heads, place, rng.uniform(seed, S("graph.neighbour"), heads, 0), forward)
    edges.append((s, d, NEIGHBOUR))

    # Remittances: metro earners who are migrants send to a rural household head.
    kinds = np.array([dist.kind for dist in districts])
    rural_heads = heads[kinds[households.district] == "rural"]
    if rural_heads.size:
        earner = np.flatnonzero((kinds[persons.district] == "metro") & np.isin(persons.life_stage, c.EARNING))
        migrant = earner[rng.uniform(seed, S("graph.migrant"), earner, 0) < params.get("graph.migrant_share")]
        pick = np.minimum((rng.uniform(seed, S("graph.origin"), migrant, 0) * rural_heads.size).astype(np.int64),
                          rural_heads.size - 1)
        edges.append((migrant, rural_heads[pick], REMITTANCE))

    src = np.concatenate([e[0] for e in edges]) if edges else _EMPTY
    dst = np.concatenate([e[1] for e in edges]) if edges else _EMPTY
    kind = np.concatenate([np.full(e[0].size, e[2], dtype=np.int64) for e in edges]) if edges else _EMPTY
    frame = pl.DataFrame({"src": src, "dst": dst, "type": kind},
                         schema={"src": pl.Int64, "dst": pl.Int64, "type": pl.Int64})
    return frame.sort(["type", "src", "dst"])
