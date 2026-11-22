"""The life course: each month people age, move between life stages on PLFS targets, are hired, laid off
and switch jobs, get raises and open accounts. Runs first, so every module sees the month's state."""
from __future__ import annotations

import datetime as dt

import numpy as np
import polars as pl

from arthasim.build import categories as c
from arthasim.build.attributes import draw_sector
from arthasim.build.banking import pick_banks
from arthasim.engine import rng
from arthasim.life.accounts import open_accounts
from arthasim.life.align import align
from arthasim.life.events import STAGE_EVENT, EventLog, state_frame
from arthasim.life.helpers import HELPER_STAGES, assign_helpers, orphaned
from arthasim.life.jobs import (choose_employers, entry_income, firm_shock, raise_due, raised_pay,
                                recompute_payroll, switch_pay)
from arthasim.life.rates import RateInputs, person_probs, study_exit
from arthasim.life.state import month_index
from arthasim.modules.base import BehaviourModule


class LifeCourse(BehaviourModule):
    name = "lifecourse"

    def __init__(self) -> None:
        self._tables: dict[str, pl.DataFrame] = {}

    def tables(self) -> dict[str, pl.DataFrame]:
        out, self._tables = self._tables, {}
        return out

    def monthly(self, world, month: dt.date) -> None:
        s = world.state
        if s.life is None:
            return
        first = month.replace(day=1)
        log = EventLog()
        cycle = _Cycle(world, first)
        if world.days_simulated == 0:
            cycle.raises(log)
            recompute_payroll(s)
        else:
            cycle.run(log)
        events = log.frame(first, s.life.next_event_id)
        s.life.next_event_id += events.height
        self._tables = {"life_events": events, "entity_state_monthly": state_frame(s, f"{month:%Y-%m}")}


class _Cycle:
    """One month of the life course. Draws are keyed on the first day of the month."""

    def __init__(self, world, first: dt.date) -> None:
        self.world, self.s, self.params, self.seed = world, world.state, world.params, world.seed
        self.month, self.key, self.m = first, first.toordinal(), month_index(first)
        pop = self.s.population
        self.pop, self.life, self.p, self.a = pop, self.s.life, pop.persons, pop.attributes
        self.hh = pop.households.household_of_person
        kinds = np.array([d.kind for d in pop.districts])
        self.is_metro = kinds[self.p.district] == "metro"
        self.n_banks = int(world.config.banks)

    def u(self, stream: str, index: int = 0) -> np.ndarray:
        return rng.uniform(self.seed, rng.stream_id(stream), self.s.person_ids, self.key, index)

    def z(self, stream: str, index: int = 0) -> np.ndarray:
        return rng.normal(self.seed, rng.stream_id(stream), self.s.person_ids, self.key, index)

    def employer_entity(self, emp: np.ndarray) -> np.ndarray:
        ids = self.s.employer_ids
        return np.where(emp >= 0, ids[np.maximum(emp, 0)] if len(ids) else -1, -1)

    def set_income(self, who: np.ndarray, income: np.ndarray) -> None:
        """Income, and salary for the salaried (they are kept equal)."""
        self.a.monthly_income_paise[who] = income
        self.s.person_salary[who] = np.where(self.p.life_stage[who] == c.SALARIED, income, 0)

    # -- the month ---------------------------------------------------------------------------------
    def run(self, log: EventLog) -> None:
        s, p, life, params = self.s, self.p, self.life, self.params
        n = len(p)
        T = life.targets

        # 1. Ageing.
        bday = life.birth_month == self.month.month
        p.age[bday] += 1
        p.age_band[:] = np.searchsorted(np.asarray(c.AGE_EDGES[1:-1]), p.age, side="right")

        # 2. Targets for every (district, sex, age group) cell, and each person's share row.
        cell = np.zeros(n, dtype=np.int64)
        targets = np.zeros((T.n_cells, 9), dtype=np.int64)
        for d in range(T.n_districts):
            for x in (c.F, c.M):
                m = (p.district == d) & (p.sex == x)
                if m.any():
                    cell[m], t = T.counts(self.month, d, x, p.age[m])
                    targets += t
        shares = T.for_persons(self.month, p.district, p.sex, p.age)

        # 3. Transition probabilities.
        stage = p.life_stage.copy()
        emp = s.person_employer
        study_hazard, study_dest = np.zeros(n), np.zeros((n, 9))
        for d in range(T.n_districts):
            for x in (c.F, c.M):
                m = (stage == c.STUDYING) & (p.district == d) & (p.sex == x)
                if m.any():
                    study_hazard[m], study_dest[m] = study_exit(T.columns(d, x, self.month), p.age[m])
        sal = emp >= 0
        shock = np.ones(n)
        if len(s.employer_ids):
            shock[sal] = firm_shock(s, self.seed, self.key)[emp[sal]]
        sup_age = params.get("life.retire.superannuation_age")
        e_sector = self.pop.orgs.employer_sector[np.maximum(emp, 0)] if len(s.employer_ids) else np.zeros(n, int)
        retire_at = np.where(e_sector == c.PUBLIC_ADMIN, sup_age["public_admin"], sup_age["private"])
        inputs = RateInputs(
            stage=stage, helper=life.helper, sex=p.sex, age=p.age, education=p.education,
            has_child=self.pop.households.dependants[self.hh] > 0, months_in_stage=life.months_in_stage,
            last_stage=life.last_stage.astype(np.int64), months_since_left=life.months_since_left, shares=shares,
            study_hazard=study_hazard, study_dest=study_dest, firm_shock=shock,
            superannuation=sal & bday & (p.age == retire_at))
        prob = person_probs(inputs, T.src, params)

        # 4. Alignment: every cell lands exactly on its targets.
        allowed = np.ones((T.n_cells, 9, 9), dtype=bool)
        group_start = np.asarray(c.AGE_GROUP_EDGES)[np.arange(T.n_cells) % c.N_AGE_GROUPS]
        allowed[group_start >= int(params.get("life.study.max_age")), :, c.STUDYING] = False
        u_align = np.stack([self.u("life.align", d) for d in range(9)], axis=1)
        new = align(stage, prob, cell, targets, allowed, u_align, float(params.get("life.rake.floor")))

        # 5. Movers.
        moved = new != stage
        self.movers(log, stage, new, moved)

        # 6. Helpers without a family business become own-account; flips between helper and own-account.
        self.helpers(log, moved)

        # 7. Job switches for salaried stayers.
        self.switches(log, moved)

        # 8. Voluntary account opening.
        unbanked = np.flatnonzero(s.person_deposit < 0)
        go = unbanked[self.u("life.open")[unbanked] < float(params.get("life.account.open_monthly_prob"))]
        self.open(log, go, pick_banks(self.u("life.open", 1)[go], self.is_metro[go], params, self.n_banks))

        # 9. Raises, payroll and durations.
        self.raises(log)
        recompute_payroll(s)
        life.months_in_stage[:] = np.where(moved, 1, life.months_in_stage + 1)
        stayed_since = ~moved & (life.last_stage >= 0)
        life.months_since_left[stayed_since] += 1

    def movers(self, log: EventLog, stage: np.ndarray, new: np.ndarray, moved: np.ndarray) -> None:
        s, p, a, life, params = self.s, self.p, self.a, self.life, self.params
        emp = s.person_employer
        mv = np.flatnonzero(moved)
        if mv.size == 0:
            return
        window = int(params.get("life.return.window_months"))
        old_income, old_emp = a.monthly_income_paise[mv].copy(), emp[mv].copy()
        old_sector = a.sector[mv].astype(np.int64)
        recent = (life.last_stage[mv] >= 0) & (life.months_since_left[mv] <= window)
        last_stage, last_income = life.last_stage[mv].astype(np.int64), life.last_income[mv].copy()
        last_sector = life.last_sector[mv].astype(np.int64)
        src, dst = stage[mv], new[mv]

        # Leaving.
        life.last_stage[mv] = src
        life.months_since_left[mv] = 0
        life.last_income[mv] = old_income
        left_job = src == c.SALARIED
        life.last_sector[mv[left_job]] = old_sector[left_job]
        emp[mv] = -1
        p.life_stage[mv] = dst

        # Entering: sector, employer, helper status, income.
        drawn = draw_sector(dst, self.is_metro[mv], self.u("life.sector")[mv], params)
        reuse = recent & (last_sector >= 1) & np.isin(dst, (c.SALARIED, c.SELF_EMPLOYED, c.GIG, c.CASUAL))
        sector = np.where(reuse, last_sector, drawn)
        to_sal = dst == c.SALARIED
        if to_sal.any():
            who = mv[to_sal]
            emp[who] = choose_employers(s, who, sector[to_sal], self.u("life.employer")[who])
            sector[to_sal] = self.pop.orgs.employer_sector[emp[who]]
            life.pay_set[who] = self.m
        a.sector[mv] = sector

        candidate = np.zeros(len(p), dtype=bool)
        entering = mv[np.isin(dst, HELPER_STAGES)]
        candidate[entering] = self.u("life.helper")[entering] < life.targets.helper_share(
            p.district[entering], p.sex[entering], p.age[entering], p.life_stage[entering])
        stayed_helper = life.helper & ~moved
        assigned = assign_helpers(p.life_stage, self.hh, candidate | stayed_helper)
        life.helper[mv] = False
        life.helper[entering] = assigned[entering]

        back = (dst == last_stage) & recent & (last_income > 0)
        entry = entry_income(s, params, mv, dst, sector, self.z("life.pay")[mv])
        income = np.where(life.helper[mv], 0, np.where(back, last_income, entry))
        self.set_income(mv, income)

        events = np.array([STAGE_EVENT[i][j] for i, j in zip(src.tolist(), dst.tolist())], dtype=object)
        log.add(s.person_ids[mv], events, from_stage=src, to_stage=dst, employer_from=self.employer_entity(old_emp),
                employer_to=self.employer_entity(emp[mv]), income_before=old_income, income_after=income)

        # A new hire without an account opens a salary account that month.
        unbanked = mv[to_sal][s.person_deposit[mv[to_sal]] < 0]
        if unbanked.size:
            at_employer = self.u("life.bank")[unbanked] < float(params.get("inclusion.salary_account_at_employer_bank"))
            banks = np.where(at_employer, s.employer_bank[emp[unbanked]],
                             pick_banks(self.u("life.bank", 1)[unbanked], self.is_metro[unbanked], params, self.n_banks))
            self.open(log, unbanked, banks)

    def helpers(self, log: EventLog, moved: np.ndarray) -> None:
        p, a, life, params = self.p, self.a, self.life, self.params
        stage = p.life_stage
        orphan = np.flatnonzero(orphaned(stage, self.hh, life.helper))
        if orphan.size:
            life.helper[orphan] = False
            income = entry_income(self.s, params, orphan, stage[orphan], a.sector[orphan].astype(np.int64),
                                  self.z("life.own_pay")[orphan])
            self.set_income(orphan, income)
            log.add(self.s.person_ids[orphan], "BECAME_OWN_ACCOUNT", income_before=np.zeros(orphan.size),
                    income_after=income)

        stay = ~moved & np.isin(stage, HELPER_STAGES)
        stay[orphan] = False
        flip = self.u("life.flip")
        to_own = np.flatnonzero(stay & life.helper & (flip < float(params.get("life.within.helper_to_own"))))
        if to_own.size:
            life.helper[to_own] = False
            income = entry_income(self.s, params, to_own, stage[to_own], a.sector[to_own].astype(np.int64),
                                  self.z("life.own_pay", 1)[to_own])
            self.set_income(to_own, income)
            log.add(self.s.person_ids[to_own], "BECAME_OWN_ACCOUNT", income_before=np.zeros(to_own.size),
                    income_after=income)

        # An own-account worker becomes a helper only if the household keeps another own-account member.
        # Its own draw, and not for anyone who became own-account this month.
        owner = np.isin(stage, HELPER_STAGES) & ~life.helper
        key = self.hh * 9 + stage
        owners = np.bincount(key[owner], minlength=int(key.max()) + 1)
        stay[to_own] = False
        back = self.u("life.flip", 1)
        cand = stay & owner & (back < float(params.get("life.within.own_to_helper"))) & (owners[key] >= 2)
        flips = np.bincount(key[cand], minlength=owners.size)
        cand &= flips[key] < owners[key]
        to_helper = np.flatnonzero(cand)
        if to_helper.size:
            before = a.monthly_income_paise[to_helper].copy()
            life.helper[to_helper] = True
            self.set_income(to_helper, np.zeros(to_helper.size, dtype=np.int64))
            log.add(self.s.person_ids[to_helper], "BECAME_HELPER", income_before=before, income_after=0)

    def switches(self, log: EventLog, moved: np.ndarray) -> None:
        s, p, a, params = self.s, self.p, self.a, self.params
        emp = s.person_employer
        young = params.get("life.switch.young")
        prob = float(params.get("life.switch.monthly_prob")) * np.where(p.age < young["age"], young["multiplier"], 1.0)
        who = np.flatnonzero(~moved & (p.life_stage == c.SALARIED) & (self.u("life.switch") < prob))
        if who.size == 0:
            return
        same = self.u("life.switch_sector")[who] < float(params.get("life.switch.same_sector_prob"))
        drawn = draw_sector(np.full(who.size, c.SALARIED), self.is_metro[who], self.u("life.switch_sector", 1)[who],
                            params)
        sector = np.where(same, a.sector[who].astype(np.int64), drawn)
        u = self.u("life.switch_employer")[who]
        new_emp = choose_employers(s, who, sector, u)
        clash = new_emp == emp[who]
        if clash.any():
            new_emp[clash] = choose_employers(s, who[clash], sector[clash], (u[clash] + 0.5) % 1.0)
        ok = new_emp != emp[who]
        who, new_emp = who[ok], new_emp[ok]
        if who.size == 0:
            return
        old_emp, old_pay = emp[who].copy(), s.person_salary[who].copy()
        pay = switch_pay(old_pay, self.z("life.switch_pay")[who], params)
        emp[who] = new_emp
        a.sector[who] = self.pop.orgs.employer_sector[new_emp]
        self.life.pay_set[who] = self.m
        self.set_income(who, pay)
        log.add(s.person_ids[who], "JOB_SWITCH", employer_from=self.employer_entity(old_emp),
                employer_to=self.employer_entity(new_emp), income_before=old_pay, income_after=pay)

    def open(self, log: EventLog, who: np.ndarray, banks: np.ndarray) -> None:
        if who.size == 0:
            return
        ids = open_accounts(self.s, self.params, who, banks, self.month, self.seed)
        income = self.a.monthly_income_paise[who]
        log.add(self.s.person_ids[who], "ACCOUNT_OPENED", income_before=income, income_after=income, account_id=ids)

    def raises(self, log: EventLog) -> None:
        """Raises in the employer's raise month, at most once in 12 months, and only after
        `life.raise.min_tenure_months` since the pay was set by a hire or a switch."""
        s, life = self.s, self.life
        due = raise_due(s, self.month)
        tenure = int(self.params.get("life.raise.min_tenure_months"))
        due = due[(self.m - life.last_raise[due] >= 12) & (self.m - life.pay_set[due] >= tenure)]
        if due.size == 0:
            return
        life.last_raise[due] = self.m
        old = s.person_salary[due].copy()
        pay = raised_pay(old, self.z("life.raise")[due], self.params)
        self.set_income(due, pay)
        log.add(s.person_ids[due], "RAISE", employer_from=self.employer_entity(s.person_employer[due]),
                employer_to=self.employer_entity(s.person_employer[due]), income_before=old, income_after=pay)
