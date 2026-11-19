import numpy as np
import pytest
from arthasim.build import categories as c
from arthasim.build.marginals import load_district, load_priors


def test_categories():
    assert len(c.AGE_BANDS) == 5 and len(c.LIFE_STAGE) == 9 and len(c.SECTORS) == 10
    assert c.LIFE_STAGE[c.SALARIED] == "salaried" and c.LIFE_STAGE[c.RETIRED] == "retired"
    assert [c.LIFE_STAGE[i] for i in c.EARNING] == ["salaried", "self_employed", "gig", "farm", "casual"]
    assert c.MERCHANT_CATEGORIES[c.GROCERY] == "grocery" and c.AGE_EDGES == [18, 25, 35, 45, 60, 85]


def test_district_files_load_and_sum_to_one():
    metro, rural = load_district("metro_archetype"), load_district("rural_archetype")
    assert (metro.kind, rural.kind) == ("metro", "rural") and metro.adult_population == 3_000_000
    for d in (metro, rural):
        assert d.status == "assumption" and d.district_code is None
        for shares in (d.age_band, d.sex, d.education, d.household_adults, *d.life_stage):
            assert abs(sum(shares) - 1.0) < 1e-6
    assert metro.life_stage[c.F][c.FARM] == 0.0 and metro.life_stage[c.M][c.HOMEMAKER] == 0.0


def test_priors_and_errors(tmp_path):
    pr = load_priors()
    assert np.asarray(pr.age_life_stage).shape == (5, 9) and np.asarray(pr.age_education).shape == (5, 5)
    assert pr.age_life_stage[2][c.STUDYING] == 0.0 and pr.age_life_stage[0][c.RETIRED] == 0.0
    with pytest.raises(FileNotFoundError):
        load_district("nowhere")
    text = open("params/population/metro_archetype.yaml").read().replace("[0.48, 0.52]", "[0.48, 0.62]")
    (tmp_path / "bad.yaml").write_text(text)
    with pytest.raises(ValueError):
        load_district("bad", root=tmp_path)
