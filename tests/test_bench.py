import argparse
import importlib.util
import pathlib
import pytest

_spec = importlib.util.spec_from_file_location("bench", pathlib.Path(__file__).parents[1] / "scripts" / "bench.py")
bench = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bench)


def test_set_parses_key_and_value():
    assert bench.parse_set("transfer.allowance_margin=0.1") == ("transfer.allowance_margin", 0.1)
    assert bench.parse_set("transfer.allowance_margin=1e-1") == ("transfer.allowance_margin", 0.1)
    assert bench.parse_set("a.b=x=y") == ("a.b", "x=y")


def test_set_without_equals_names_the_argument():
    with pytest.raises(argparse.ArgumentTypeError, match="transfer.allowance_margin"):
        bench.parse_set("transfer.allowance_margin")
