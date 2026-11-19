import pathlib
import polars as pl
import pytest
from arthasim import ParamRegistry

PATH = pathlib.Path(__file__).parents[1] / "params" / "registry.yaml"


def test_load_get_table():
    r = ParamRegistry.load(PATH)
    assert r.get("spike.purchases_per_day") == 1.2
    assert r.get("spike.bank_shares") == [0.5, 0.3, 0.2]
    t = r.table()
    assert t.columns == ["id", "value", "unit", "as_of", "source", "status", "role"]
    assert t.schema["value"] == pl.String and t.height >= 17
    assert set(t["status"]) <= {"verified", "unverified", "assumption"}
    assert set(t["role"]) <= {"input", "target", "holdout"}


def test_override_and_version():
    r = ParamRegistry.load(PATH)
    s = r.override("spike.purchases_per_day", 2.0)
    assert s.get("spike.purchases_per_day") == 2.0 and r.get("spike.purchases_per_day") == 1.2
    assert s.version() != r.version() == ParamRegistry.load(PATH).version()
    assert ParamRegistry.load(PATH, overrides={"spike.purchases_per_day": 2.0}).version() == s.version()


def test_errors(tmp_path):
    r = ParamRegistry.load(PATH)
    with pytest.raises(KeyError):
        r.get("nope")
    with pytest.raises(KeyError):
        r.override("nope", 1)
    bad = tmp_path / "bad.yaml"
    bad.write_text("- {id: a, value: 1, status: guess, role: input}\n")
    with pytest.raises(ValueError):
        ParamRegistry.load(bad)
    bad.write_text("- {id: a, value: 1, status: assumption, role: input}\n" * 2)
    with pytest.raises(ValueError):
        ParamRegistry.load(bad)
