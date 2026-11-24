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


def run_files(path, skip=()) -> dict:
    """SHA-256 of every Parquet file of a run folder, keyed by relative path; checkpoints are left out."""
    import hashlib
    root = pathlib.Path(path)
    return {str(f.relative_to(root)): hashlib.sha256(f.read_bytes()).hexdigest()
            for f in sorted(root.rglob("*.parquet"))
            if f.relative_to(root).parts[0] != "checkpoints" and f.name not in skip}


def data_files(path) -> dict:
    """`run_files` without the interventions log, for comparing a run that applied interventions with one that did not."""
    return run_files(path, skip=("interventions_log.parquet",))
