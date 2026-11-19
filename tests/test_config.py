import datetime as dt
import pytest
from arthasim import Config


def test_tier_xs_defaults():
    c = Config.tier("XS")
    assert (c.persons, c.employers, c.merchants, c.banks) == (10_000, 100, 300, 3)
    assert c.slots_per_day == 96 and c.start == dt.date(2025, 4, 1)


def test_overrides_yaml_and_hash(tmp_path):
    c = Config.tier("XS", persons=500, start="2025-04-28")
    assert c.persons == 500 and c.start == dt.date(2025, 4, 28)
    c.to_yaml(tmp_path / "c.yaml")
    assert Config.from_yaml(tmp_path / "c.yaml") == c
    assert c.hash() != Config.tier("XS").hash()
    d = c.with_params(**{"spike.purchases_per_day": 2.0})
    assert d.param_overrides == {"spike.purchases_per_day": 2.0} and d.hash() != c.hash()


def test_rejects_bad_input():
    for bad in ({"persons": 0}, {"banks": 0}, {"slots_per_day": 24}, {"employers": -1}):
        with pytest.raises(ValueError):
            Config.tier("XS", **bad)
    with pytest.raises(ValueError):
        Config.tier("XXL")
