"""Genera los artefactos reproducibles de las tres ramas."""
import argparse
import hashlib
from importlib.metadata import version
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
from joblib import dump

from src.audit_data import ANOMALY, audit, prepare_default_data
from src.contracts import LAB, RANDOM_STATE, ROOT, TARGETS, write_json
from src.features_pipeline import fit_transformers, transform_record
from src.model_m1 import EPA, train_m1
from src.model_m3a import train_m3a
from src.model_m3b import train_m3b


def train(data_dir, models_dir, reports_dir):
    tables, eligible, report = audit(data_dir)
    write_json(reports_dir / "data_audit.json", report)
    raw = tables["raw"]
    split = tables["audit"]["split"]
    transformers = fit_transformers(raw.loc[split.eq("train")].to_dict("records"))
    rows = {key: transform_record(row, transformers)
            for key, row in zip(raw.index, raw.to_dict("records"), strict=True)}
    frames = {
        branch: pd.DataFrame.from_dict({key: item[branch] for key, item in rows.items()
                                        if item[branch] is not None}, orient="index")
        for branch in ("m1", "m3a", "m3b")
    }
    if set(frames["m3b"].index) != set(eligible.index[eligible]):
        raise ValueError("La elegibilidad M3B difiere entre entrenamiento y auditoría")
    models_dir.mkdir(parents=True, exist_ok=True)
    dump(transformers, models_dir / "transformers.joblib")
    labels = tables["y"].copy()
    for target, matrix in zip(TARGETS, [LAB[0], LAB[0], LAB[1], LAB[1]], strict=True):
        labels[target] = labels[target].where(tables["m3b"][matrix].notna())
    hair = tables["m3b"][LAB[0]]
    labels[EPA] = hair.ge(1).astype(float).where(hair.notna())
    metrics = {
        "m1": train_m1(frames["m1"][transformers["m1_columns"]], labels, split,
                       models_dir / "m1", reports_dir),
        "m3a": train_m3a(frames["m3a"], split, tables["m3b"], models_dir / "m3a", reports_dir),
        "m3b": train_m3b(frames["m3b"], split, tables["audit"][ANOMALY],
                         models_dir / "m3b", reports_dir),
    }
    files = [models_dir / "transformers.joblib",
             *sorted((models_dir / "m1").glob("*.joblib")), models_dir / "m1/thresholds.json",
             models_dir / "m3a/medoids.joblib", models_dir / "m3a/hdbscan.joblib",
             models_dir / "m3b/isolation_forest.joblib"]
    digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    write_json(models_dir / "manifest.json", {
        "contract_version": 2, "random_state": RANDOM_STATE, "python": sys.version.split()[0],
        "versions": {name: version(name) for name in
                     ("numpy", "pandas", "scipy", "scikit-learn", "lightgbm", "shap", "hdbscan", "joblib")},
        "data_sha256": report["sha256"],
        "source_sha256": {path.name: digest(path) for path in sorted((ROOT / "src").glob("*.py"))},
        "config_sha256": {path.name: digest(path) for path in sorted((ROOT / "config").glob("*.json"))},
        "artifact_sha256": {str(path.relative_to(models_dir)): digest(path) for path in files},
        "metrics": metrics,
    })


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--models-dir", type=Path, default=ROOT / "models")
    parser.add_argument("--reports-dir", type=Path, default=ROOT / "reports")
    args = parser.parse_args()
    if args.data_dir.resolve() == ROOT / "data":
        prepare_default_data(args.data_dir)
    train(args.data_dir, args.models_dir, args.reports_dir)


if __name__ == "__main__":
    main()
