"""calibrate (plan 1e): free parameters, scores, the Optuna loop and the result."""
import pytest

from arthasim import Config, calibration
from arthasim.calibration import CalibrationResult, Free
from helpers import P


def test_overrides_compose_key_and_scale():
    frees = [Free("earn.stage_multiplier", 0.2, 1.5, key="casual"),
             Free("earn.stage_multiplier", 0.2, 1.5, key="farm"),
             Free("consumption.purchases_per_month", 0.5, 3.0, scale=True),
             Free("earn.base_paise", 300_000, 1_500_000, log=True),
             Free("earn.sigma", 0.2, 0.9)]
    got = calibration.overrides(P, frees, [0.7, 0.3, 2.0, 600_000.4, 0.35])
    assert got["earn.stage_multiplier"] == {"salaried": 1.0, "self_employed": 0.9, "gig": 0.6, "farm": 0.3,
                                            "casual": 0.7}
    assert got["consumption.purchases_per_month"] == [24, 16, 6, 3.0, 1.4, 0.3, 20, 4, 6]
    assert got["earn.base_paise"] == 600_000 and isinstance(got["earn.base_paise"], int)
    assert got["earn.sigma"] == 0.35
    assert P.get("earn.stage_multiplier")["casual"] == 0.4          # the registry itself is untouched


def test_scores_and_loss():
    assert calibration.score(110.0, 100.0, "relative", 0.10) == pytest.approx(1.0)
    assert calibration.score(0.47, 0.50, "absolute", 0.03) == pytest.approx(-1.0)
    assert calibration.loss({"a": {"x": 1.0, "y": -3.0}, "b": {"all": 0.0}}) == pytest.approx((1 + 9 + 0) / 3)


def test_default_space_names_registry_rows_and_suite_checks():
    frees, targets = calibration.load_space()
    assert len(frees) == 14 and len(targets) == 11
    for f in frees:
        assert f.id in P and f.low < f.high
    with pytest.raises(ValueError, match="nope"):
        calibration.resolve_params(["nope"])
    with pytest.raises(ValueError, match="bounds"):
        calibration.resolve_params([Free("earn.sigma", 0.9, 0.2)])


def _tiny(tmp_path, workers):
    config = Config.tier("S", persons=1_000, out_dir=str(tmp_path / f"w{workers}"))
    return calibration.calibrate(config, params=[Free("earn.base_paise", 400_000, 1_400_000, log=True)],
                                 targets=["pay.regular_monthly"], trials=2, seeds=(1, 2), months=2,
                                 workers=workers, sampler_seed=3)


def test_two_trials_are_the_same_with_one_or_two_workers(tmp_path):
    one, two = _tiny(tmp_path, 1), _tiny(tmp_path, 2)
    assert one.best == two.best and one.loss == two.loss
    assert one.trials.equals(two.trials)
    assert one.trials.height == 2 and set(one.best) == {"earn.base_paise"}
    assert one.loss == min(one.trials["loss"].to_list())
    assert not list((tmp_path / "w1").rglob("*.parquet"))            # trial runs are removed after scoring


def test_save_load_apply_and_report(tmp_path):
    result = _tiny(tmp_path, 1)
    result.save(tmp_path / "fit.yaml")
    back = CalibrationResult.load(tmp_path / "fit.yaml")
    assert back.best == result.best and back.loss == result.loss and back.trials.equals(result.trials)
    assert back.registry_version == P.version() and back.seeds == (1, 2) and back.months == 2
    config = back.apply(Config.tier("S"))
    assert config.param_overrides == result.best
    result.report(tmp_path / "fit.md")
    text = (tmp_path / "fit.md").read_text()
    assert "earn.base_paise" in text and "pay.regular_monthly" in text


def test_narrowed_space_and_start_values(tmp_path):
    frees = [Free("earn.base_paise", 300_000, 1_500_000, log=True), Free("earn.sigma", 0.2, 0.9)]
    narrow = calibration.narrow(frees, {"earn.base_paise": 600_000.0, "earn.sigma": 0.85}, width=0.25)
    assert narrow[0].low == pytest.approx(600_000 / 1.5) and narrow[0].high == pytest.approx(600_000 * 1.5)
    assert narrow[1].low == pytest.approx(0.85 - 0.175) and narrow[1].high == 0.9          # clipped at the bound
    config = Config.tier("S", persons=1_000, out_dir=str(tmp_path))
    result = calibration.calibrate(config, params=[narrow[0]], targets=["pay.regular_monthly"], trials=1,
                                   seeds=(1,), months=2, start={"earn.base_paise": 600_000.0})
    assert result.trials["free:earn.base_paise"].to_list() == [600_000.0]
