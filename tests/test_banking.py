import re
import numpy as np
from arthasim import Config
from arthasim.build import categories as c
from arthasim.build.attributes import attach_attributes
from arthasim.build.banking import assign_banking
from arthasim.build.identifiers import REAL_FORMATS, branch_code, pan_like, token, vpa
from arthasim.build.orgs import build_orgs
from arthasim.build.population import synthesise_persons
from helpers import D, PR, P, l1

CFG = Config.tier("S", persons=20_000)
p = synthesise_persons(D, PR, 20_000, seed=7)
a = attach_attributes(p, D, P, seed=7)
o = build_orgs(p, a, D, 20, P, seed=7)
b = assign_banking(p, a, o, D, CFG, P, seed=7)
SAL = p.life_stage == c.SALARIED


def test_bank_codes_and_market_shares():
    assert b.bank_codes.tolist() == [f"SYNB{i:02d}" for i in range(1, 13)] + ["SYNX00"]
    assert b.nbfc_codes.tolist() == ["SYNN01", "SYNN02"] and len(b.bank_archetype) == 12
    for d, col in ((0, 1), (1, 2)):
        s = (p.district == d) & b.person_has_account & ~SAL
        target = [row[col] for row in P.get("bank.archetypes")]
        assert l1(np.bincount(b.person_primary_bank[s], minlength=12), target) < 0.05


def test_ownership_rules():
    assert b.person_has_account[SAL].all()
    for d, kind in ((0, "metro"), (1, "rural")):
        s = (p.district == d) & ~SAL
        assert abs(b.person_has_account[s].mean() - P.get("inclusion.account_ownership")[kind]) < 0.03
    none = ~b.person_has_account
    assert none.any() and (b.person_primary_bank[none] == -1).all() and (b.opening_deposit[none] == 0).all()
    assert not b.person_upi[none].any() and not b.person_has_card[none].any()
    assert (b.opening_deposit[~none] >= 100).all() and (b.opening_cash >= 100).all()
    two = b.person_second_bank >= 0
    assert two.any() and (b.person_second_bank[two] != b.person_primary_bank[two]).all() and not two[none].any()
    assert (b.person_primary_bank[SAL] == b.employer_bank[o.person_employer[SAL]]).mean() > 0.55
    assert b.person_has_pan[SAL].mean() > 0.9 > b.person_has_pan[~SAL].mean()
    assert not (b.person_upi & ~b.person_has_mobile).any()
    assert (a.digital_literacy[b.person_upi] > 0.45).all()
    assert b.person_basic_account[~none & (a.monthly_income_paise < 1_000_000)].all()


def test_identifiers_cannot_be_real():
    ids = np.arange(5000)
    samples = {"pan": pan_like(ids, ids % 26), "aadhaar": token("u", 7, 1, ids),
               "mobile": token("m", 7, 2, ids), "ifsc": branch_code(ids % 12, ids % 2, ids % 20)}
    for name, values in samples.items():
        assert not any(REAL_FORMATS[name].match(v) for v in values)
        assert len(set(values)) == (5000 if name != "ifsc" else 60)
    assert all(re.match(r"^SY[0-9]{2}0[0-9]{6}$", v) for v in samples["ifsc"])
    assert all(re.match(r"^SY[0-9]P[A-Z][0-9]{4}[A-Z]$", v) for v in samples["pan"])
    assert all(v == f"p{i}@syn{(i % 12) + 1:02d}" for i, v in zip(ids.tolist(), vpa(ids, ids % 12)))


def test_deterministic():
    again = assign_banking(p, a, o, D, CFG, P, seed=7)
    assert np.array_equal(again.person_primary_bank, b.person_primary_bank)
    assert np.array_equal(again.opening_deposit, b.opening_deposit)
