import pathlib
import pytest
from arthasim import Config, ParamRegistry

PATH = pathlib.Path(__file__).parents[1] / "params" / "registry.yaml"


def test_tier_s():
    c = Config.tier("S")
    assert (c.persons, c.banks, c.nbfcs, c.builder) == (100_000, 12, 2, "population")
    assert c.districts == ["metro_archetype", "rural_archetype"]
    assert c.employers is None and c.merchants is None and c.localities_per_district == 20


def test_builder_rules():
    assert Config.tier("XS").builder == "spike"
    for bad in ({"districts": []}, {"employers": 5}, {"localities_per_district": 0}, {"nbfcs": -1}):
        with pytest.raises(ValueError):
            Config.tier("S", **bad)
    with pytest.raises(ValueError):
        Config.tier("XS", employers=None)


def test_registry_has_plan_1a_parameters():
    r = ParamRegistry.load(PATH)
    assert r.table().height >= 61
    assert len(r.get("bank.archetypes")) == 12 and r.get("graph.migrant_share") == 0.15
    for key in ("org.sector_shares.metro", "org.sector_shares.rural", "org.merchant_category_shares"):
        assert abs(sum(r.get(key)) - 1.0) < 1e-9
    for col in (1, 2):
        assert abs(sum(row[col] for row in r.get("bank.archetypes")) - 1.0) < 1e-9
