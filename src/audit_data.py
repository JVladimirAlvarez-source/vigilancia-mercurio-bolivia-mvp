"""Auditoría de identidad, disponibilidad de laboratorio y exclusión de fuga."""
import argparse
import hashlib
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

from src.contracts import FEATURES, ID, LAB, PRELAB, ROOT, SCHEMA, TARGETS, write_json
from src.features_pipeline import transform_record
from src.normative_engine import measurements

FILES = {
    "raw": "ficha_mercurio_bolivia_v2.csv",
    "m1": "X_M1.csv",
    "m3a": "X_M3A.csv",
    "m3b": "X_M3B.csv",
    "y": "Y.csv",
    "audit": "auditoria_latente_NO_ENTRENAR.csv",
}
ANOMALY = "flag_anomalia_real"


def prepare_default_data(data_dir):
    """Materializa desde el generador original; jamás anexa claves a CSV existentes."""
    if any((data_dir / filename).exists() for filename in FILES.values()):
        return
    from mercurio_mvp_v4.generate_synthetic_bolivia import generate

    with TemporaryDirectory() as scratch:
        generated = Path(scratch)
        generate(generated, keyed=True)
        data_dir.mkdir(parents=True, exist_ok=True)
        for name in FILES.values():
            (data_dir / name).write_bytes((generated / name).read_bytes())


def load_inputs(data_dir):
    """Carga columnas autorizadas y alinea todas las fuentes por un ID explícito."""
    paths = {key: data_dir / name for key, name in FILES.items()}
    hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths.values()}
    tables = {}
    for key, path in paths.items():
        cols = [ID, "split", ANOMALY] if key == "audit" else None
        table = pd.read_csv(path, usecols=cols, dtype={ID: "string"})
        if ID not in table or table[ID].isna().any() or not table[ID].is_unique:
            raise ValueError(f"{path.name} requiere ID explícito, único y completo: {ID}")
        tables[key] = table.set_index(ID)
    ids = tables["raw"].index
    for key, table in tables.items():
        if set(table.index) != set(ids):
            raise ValueError(f"Identidades desalineadas: {FILES[key]}")
        tables[key] = table.reindex(ids)
    return tables, hashes


def audit(data_dir):
    tables, hashes = load_inputs(data_dir)
    partitions = tables["audit"]["split"]
    if partitions.value_counts().to_dict() != SCHEMA["partitions"]:
        raise ValueError("Particiones incorrectas")
    if len(tables["raw"]) != sum(SCHEMA["partitions"].values()):
        raise ValueError("Cantidad de registros incorrecta")
    if list(tables["raw"].columns) != SCHEMA["raw_columns"] + LAB:
        raise ValueError("La ficha no coincide con el esquema de captura y sus mediciones")
    if any(key.startswith(("lab_", "EXT_67b", "y_")) or key in FEATURES["forbidden"]
           for key in PRELAB):
        raise ValueError("La lista prelaboratorio contiene columnas prohibidas")
    raw_records = tables["raw"].to_dict("records")
    projected = [transform_record(record, None) for record in raw_records]
    for branch, columns in (("m1", PRELAB), ("m3a", PRELAB), ("m3b", PRELAB + LAB)):
        if list(tables[branch].columns) != columns:
            raise ValueError(f"Columnas fuera del contrato en {branch}")
        pd.testing.assert_frame_equal(
            pd.DataFrame([item[branch] for item in projected], index=partitions.index),
            tables[branch], check_dtype=False, check_exact=True,
        )
    labels = tables["y"]
    if list(labels.columns) != ["clasificacion_guia537", *TARGETS, ANOMALY]:
        raise ValueError("Columnas de Y fuera del contrato")
    if not labels[TARGETS].isin([0, 1]).where(labels[TARGETS].notna(), True).all().all():
        raise ValueError("Los targets deben contener 0, 1 o un valor ausente")
    if not tables["audit"][ANOMALY].isin([0, 1]).all():
        raise ValueError("Etiquetas externas de anomalía inválidas")
    if not tables["audit"][ANOMALY].eq(labels[ANOMALY]).all():
        raise ValueError("Etiqueta externa de anomalía desalineada")
    eligible = pd.Series([bool(measurements(row)) for row in raw_records], index=partitions.index)
    if tables["audit"].loc[~eligible, ANOMALY].any():
        raise ValueError("Hay anomalías de laboratorio sin medición elegible")
    distribution = {}
    for target in TARGETS:
        distribution[target] = {}
        for split in SCHEMA["partitions"]:
            values = labels.loc[partitions.eq(split), target]
            distribution[target][split] = {
                "negativos": int(values.eq(0).sum()), "positivos": int(values.eq(1).sum()),
                "ausentes": int(values.isna().sum()),
            }
    report = {
        "n": len(partitions), "identity_key": ID, "one_to_one": True,
        "partitions": partitions.value_counts().to_dict(),
        "no_prelab_leakage": True, "raw_matrix_parity": True,
        "lab_eligible_total": int(eligible.sum()),
        "lab_eligible_by_split": {split: int((eligible & partitions.eq(split)).sum())
                                  for split in SCHEMA["partitions"]},
        "target_distribution": distribution,
        "target_origin": "Etiquetas sintéticas del simulador; incluyen resultados contrafactuales.",
        "sha256": hashes,
    }
    return tables, eligible, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--reports-dir", type=Path, default=ROOT / "reports")
    args = parser.parse_args()
    if args.data_dir.resolve() == ROOT / "data":
        prepare_default_data(args.data_dir)
    _, _, report = audit(args.data_dir)
    write_json(args.reports_dir / "data_audit.json", report)


if __name__ == "__main__":
    main()
