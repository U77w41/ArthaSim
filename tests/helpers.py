# tests/helpers.py
import pathlib
import numpy as np
from arthasim import ParamRegistry
from arthasim.build.marginals import load_district, load_priors

D = [load_district("metro_archetype"), load_district("rural_archetype")]
PR = load_priors()
P = ParamRegistry.load(pathlib.Path(__file__).parents[1] / "params" / "registry.yaml")


def l1(counts, target):
    counts = np.asarray(counts, dtype=float)
    return float(np.abs(counts / counts.sum() - np.asarray(target, dtype=float)).sum())
