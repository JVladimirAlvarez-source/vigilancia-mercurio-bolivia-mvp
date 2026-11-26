"""Proyección común del registro crudo y transformaciones ajustadas en train."""
import numpy as np
import pandas as pd

from .contracts import CLINICAL, FEATURES, LAB, PRELAB, SCHEMA
from .derived_features import AXES, AXIS_EXPOSURE, BOUNDED_DERIVED, PHENOTYPES, TEMPORAL, derive
from .normative_engine import (EXPOSURE_TYPES, ROUTES, day, indicator, measurements,
                               missing, number)

CATEGORICAL = SCHEMA["categorical"]
DATES = [col for col in SCHEMA["dates"] if col in PRELAB]
BLOCKS = {
    "clinica": [*CLINICAL, *(f"eje_{key}" for key in AXES), "flag_convulsiones", "flag_hepatomegalia", *PHENOTYPES],
    "exposicion": [key for key in FEATURES["blocks"]["exposicion"] if key not in {
        "ocupacion", "ocupacion_momento_exposicion"}] + list(AXIS_EXPOSURE[:2]) + list(AXIS_EXPOSURE[5:]),
    "temporalidad": [*FEATURES["blocks"]["temporalidad"], *TEMPORAL, *AXIS_EXPOSURE[2:5]],
}
BOUNDED = (set(SCHEMA["binary"]) | BOUNDED_DERIVED |
           {"proporcion_sintomas_evaluados", "indice_sindromico", "exposicion_activa"})
SIGNED = {"contraste_exposicion", "D_clin"}
DISCORDANCE = (
    "ratio_hg_cabello_vs_exposicion_dietetica", "ratio_hg_orina_vs_exposicion_inhalatoria",
    "indice_discordancia_asintomatico_extremo", "flag_incoherencia_matriz_via",
)
DERIVED = list(derive({}, dict.fromkeys(PRELAB, np.nan), FEATURES["half_lives"]))
NATIVE_FEATURES = PRELAB + DERIVED
M1_REPRESENTATION = [key for key in NATIVE_FEATURES if key not in
                      (set(PHENOTYPES) | set(AXIS_EXPOSURE) | {f"eje_{key}" for key in AXES})]
M3A_FEATURES = [key for block in BLOCKS.values() for key in block]


def project_record(record):
    """Reconstruye las matrices de referencia con nulos y columnas explícitas."""
    values = {}
    for key in PRELAB:
        value = record.get(key)
        if key in ROUTES:
            value = indicator(record, key, "via_exposicion", ROUTES)
        elif key in EXPOSURE_TYPES:
            value = indicator(record, key, "tipo_exposicion", EXPOSURE_TYPES)
        elif key in DATES:
            parsed = day(value)
            value = parsed.isoformat() if parsed else None
        elif key in CATEGORICAL:
            value = None if missing(value) else str(value)
        else:
            value = number(value)
            if key in SCHEMA["binary"] and value not in (0, 1):
                value = None
        values[key] = np.nan if value is None else value
    labs = measurements(record)
    return {
        "m1": values,
        "m3a": dict(values),
        "m3b": values | {key: labs.get(key, np.nan) for key in LAB},
    }


def _prelab(record, projected):
    features = dict(projected)
    for key in DATES:
        event = day(projected[key])
        reference = day(record.get("fecha_notificacion"))
        elapsed = (reference - event).days if reference and event else -1
        features[key] = elapsed if elapsed >= 0 else np.nan
    features.update(derive(record, projected, FEATURES["half_lives"]))
    return features



def exposure_group(row):
    occupational = row["tipo_ocupacional"] == 1 or row["via_respiratoria"] == 1
    diet = row["consumo_pescado_rio"] == 1
    return ("mixta" if occupational and diet else "ocupacional" if occupational
            else "dietaria" if diet else "otra")


def _lab_row(row, projected, record):
    result = row | {key: projected[key] for key in LAB}
    segment = number(record.get("EXT_67d_longitud_segmento_cabello_cm"))
    result["segmento_cabello_cm"] = segment if segment is not None and segment >= 0 else np.nan
    sample, sent = day(record.get("fecha_toma_muestra")), day(record.get("fecha_envio_lab"))
    result["dias_envio_lab"] = (sent - sample).days if sample and sent and sent >= sample else np.nan
    return result


def _lab_features(row, baseline):
    group = exposure_group(row)
    result = dict(row)
    for key in LAB:
        measurement = row[key]
        # Zero denotes a measured result. The log floor is half the simulation resolution.
        logged = np.log(max(measurement, .005)) if not pd.isna(measurement) else np.nan
        center, scale = baseline[key].get(group, baseline[key]["all"])
        result[key] = logged
        result[f"{key}_residual"] = (logged - center) / scale
        result[f"{key}_medido"] = int(not pd.isna(measurement))
    hair, urine, blood = (row[key] for key in LAB)
    diet = row["EXT_32c_frecuencia_piscivoros_30d"]
    inhaled = row["eje_inhalatorio_ocupacional"]
    completeness = row["proporcion_sintomas_evaluados"]
    symptoms = row["indice_sindromico"]
    severe = max((value / cutoff for value, cutoff in zip((hair, urine, blood), (10, 100, 40))
                  if not pd.isna(value)), default=np.nan)
    mismatch = np.nan
    if not pd.isna(diet + inhaled):
        if diet == 0 and inhaled > 0:
            mismatch = float(not pd.isna(hair) and pd.isna(urine) and pd.isna(blood))
        elif diet > 0 and inhaled == 0:
            mismatch = float(not pd.isna(urine) and pd.isna(hair) and pd.isna(blood))
        else:
            mismatch = 0.
    result.update(dict(zip(DISCORDANCE, (
        hair / (1 + diet), urine / (1 + 10 * inhaled),
        max(severe - 1, 0) * (1 - symptoms) if completeness >= .70 and symptoms <= .10 else 0.,
        mismatch,
    ), strict=True)))
    return result


def fit_transformers(train_records):
    """Ajusta vocabularios, cuantiles y estadísticas condicionales de train."""
    records = list(train_records)
    projected = [project_record(row) for row in records]
    native_rows = [_prelab(row, item["m1"]) for row, item in zip(records, projected, strict=True)]
    m1 = pd.DataFrame(native_rows, columns=NATIVE_FEATURES)
    categories = {key: sorted(m1[key].dropna().unique()) for key in CATEGORICAL}
    continuous = [key for key in m1 if key not in CATEGORICAL and key not in BOUNDED]
    quantiles = {key: tuple(np.log1p(m1[key].dropna().clip(lower=0)).quantile([.05, .95]))
                 for key in continuous if m1[key].notna().any()}

    eligible = [_lab_row(row, item["m3b"], record)
                for row, item, record in zip(native_rows, projected, records, strict=True)
                if any(not pd.isna(item["m3b"][key]) for key in LAB)]
    if not eligible:
        raise ValueError("Train carece de registros elegibles para M3B")
    b = pd.DataFrame(eligible)
    groups = b.apply(exposure_group, axis=1)
    baseline = {}
    for key in LAB:
        logged = np.log(b[key].clip(lower=.005))
        stats = {}
        for group, samples in [("all", logged), *logged.groupby(groups)]:
            samples = samples.dropna()
            if not samples.empty:
                spread = (samples.quantile(.75) - samples.quantile(.25)) / 1.349
                stats[group] = (samples.median(), spread if spread > 1e-9 else 1.0)
        stats.setdefault("all", (0.0, 1.0))
        baseline[key] = stats
    expanded = pd.DataFrame([_lab_features(row, baseline) for row in eligible])
    b_categories = {key: sorted(expanded[key].dropna().unique()) for key in CATEGORICAL}
    impute = expanded.drop(columns=CATEGORICAL).median().fillna(0).to_dict()
    varying = [key for key in M1_REPRESENTATION if m1[key].nunique(dropna=True) > 1]
    return {"m1": categories, "m1_columns": varying, "m3a": quantiles,
            "m3b": {"baseline": baseline, "categories": b_categories, "impute": impute}}


def transform_record(record, artifacts):
    """Aplica los tres transformadores a un registro crudo. Sin artefactos, proyecta el esquema de referencia."""
    raw = project_record(record)
    if artifacts is None:
        return raw
    native = _prelab(record, raw["m1"])
    m1 = dict(native)
    for key, vocabulary in artifacts["m1"].items():
        value = m1[key]
        m1[key] = vocabulary.index(value) if value in vocabulary else np.nan

    m3a = {key: native[key] for key in M3A_FEATURES}
    for key, value in list(m3a.items()):
        if key in CATEGORICAL or pd.isna(value):
            continue
        if key in BOUNDED:
            m3a[key] = float(np.clip((value + 1) / 2 if key in SIGNED else value, 0, 1))
            continue
        if key not in artifacts["m3a"]:
            m3a[key] = np.nan
            continue
        low, high = artifacts["m3a"][key]
        scaled = (np.log1p(max(value, 0)) - low) / (high - low) if high > low else 0.0
        m3a[key] = float(np.clip(scaled, 0, 1))

    m3b = None
    if any(not pd.isna(raw["m3b"][key]) for key in LAB):
        plan = artifacts["m3b"]
        expanded = _lab_features(_lab_row(native, raw["m3b"], record), plan["baseline"])
        m3b = {key: replacement if pd.isna(expanded[key]) else expanded[key]
               for key, replacement in plan["impute"].items()}
        for key, vocabulary in plan["categories"].items():
            value = expanded[key]
            m3b.update({f"{key}={category}": int(value == category) for category in vocabulary})
            m3b[f"{key}__desconocido"] = int(value not in vocabulary)
    return {"m1": m1, "m3a": m3a, "m3b": m3b}
