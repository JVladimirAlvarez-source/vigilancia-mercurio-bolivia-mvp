"""Inferencia local con artefactos del entrenamiento y explicación SHAP."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from joblib import load
from shap import TreeExplainer

from .contracts import LAB, ROOT, RULES
from .features_pipeline import transform_record
from .m1_representation import SHAP_GROUPS
from .model_m1 import MODEL_TARGETS, nested_scores
from .model_m3a import assign_profiles
from .normative_engine import (RESULT, SAMPLES, UNIT, assess_vulnerability, calculate_edi, classify_case,
                               recommend_biomarker, validate_record)

DISCLAIMER = (
    "Probabilidades experimentales entrenadas con datos sintéticos. "
    "Su uso se limita a investigación y no sustituye la evaluación clínica ni confirma un caso."
)


def load_artifacts(models_dir="models"):
    """Carga una generación íntegra de artefactos locales y prepara SHAP en memoria.

    Los archivos joblib deben provenir siempre de un entrenamiento local de confianza.
    """
    root = Path(models_dir)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if manifest["contract_version"] != 2:
        raise ValueError("Versión de contrato desconocida")
    expected = {
        "transformers.joblib", "m1/thresholds.json", "m3a/medoids.joblib",
        "m3a/hdbscan.joblib", "m3b/isolation_forest.joblib",
        *(f"m1/{target}.joblib" for target in MODEL_TARGETS),
    }
    if set(manifest["artifact_sha256"]) != expected:
        raise ValueError("El manifiesto no describe todos los artefactos requeridos")
    config_paths = sorted((ROOT / "config").glob("*.json"))
    config_hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in config_paths}
    if manifest["config_sha256"] != config_hashes:
        raise ValueError("Cambió el contrato de datos. Vuelve a entrenar los modelos.")
    source_paths = sorted((ROOT / "src").glob("*.py"))
    source_hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in source_paths}
    if manifest["source_sha256"] != source_hashes:
        raise ValueError("Cambió el código del backend. Vuelve a entrenar los modelos.")
    for name, digest in manifest["artifact_sha256"].items():
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != digest:
            raise ValueError(f"Artefacto incongruente con el manifiesto: {name}")

    models = {target: load(root / "m1" / f"{target}.joblib") for target in MODEL_TARGETS}
    return {
        "transformers": load(root / "transformers.joblib"), "m1": models,
        "explainers": {target: TreeExplainer(model) for target, model in models.items()},
        "thresholds": json.loads((root / "m1/thresholds.json").read_text(encoding="utf-8")),
        "m3a": load(root / "m3a/medoids.joblib"),
        "m3b": load(root / "m3b/isolation_forest.joblib"),
    }


def _explain(explainer, frame):
    raw = explainer.shap_values(frame, check_additivity=False)
    if isinstance(raw, list):
        values = np.asarray(raw[1])[0]
    else:
        values = np.asarray(raw)[0]
        if values.ndim == 2:
            values = values[:, 1]
    order = np.argsort(-np.abs(values), kind="stable")[:6]
    grouped = {}
    for field, value in zip(frame.columns, values, strict=True):
        group = SHAP_GROUPS.get(field, field)
        grouped[group] = grouped.get(group, 0.) + float(value)
    top = [{"campo": frame.columns[index], "contribucion_log_odds": float(values[index])}
           for index in order]
    return top, grouped


def predict_patient(record_dict, artifacts):
    """Ejecuta reglas, triaje, fenotipado y revisión de laboratorio para un registro."""
    validation = validate_record(record_dict)
    normative = {
        "validacion": validation, "caso": classify_case(record_dict),
        "edi": calculate_edi(record_dict), "vulnerabilidad": assess_vulnerability(record_dict),
        "biomarcador": recommend_biomarker(record_dict), "alcance_reglas": RULES["status"],
    }

    # Exclude invalid values from modeling while keeping their errors in the normative output.
    clean = dict(record_dict)
    for key in validation["errores"]:
        clean[key] = None
    primary = SAMPLES.get(str(record_dict.get("tipo_muestra", "")).strip().lower())
    errors = validation["errores"]
    if UNIT in errors or (primary in LAB and primary in errors):
        clean[RESULT] = None

    features = transform_record(clean, artifacts["transformers"])
    frames = {target: pd.DataFrame([features["m1"]], columns=model.feature_name_)
              for target, model in artifacts["m1"].items()}
    original = {target: float(model.predict_proba(frames[target])[0, 1])
                for target, model in artifacts["m1"].items()}
    probabilities = nested_scores(original)
    risks = {}
    for target, probability in probabilities.items():
        threshold = artifacts["thresholds"][target]
        top, grouped = _explain(artifacts["explainers"][target], frames[target])
        risks[target] = {
            "probabilidad": float(probability), "probabilidad_modelo_independiente": original[target],
            "umbral": threshold, "alerta_triaje": bool(probability >= threshold),
            "factores_modelo_independiente": top, "shap_por_grupo_log_odds": grouped,
        }

    labels, distances = assign_profiles(pd.DataFrame([features["m3a"]]), artifacts["m3a"])
    label = int(labels[0])
    profile = {"id": label, "perfil": f"Perfil {label}" if label >= 0 else "Atípico / Ruido",
               "distancia": float(distances[0]) if np.isfinite(distances[0]) else None}
    review = {"elegible": features["m3b"] is not None, "alerta_revision": None, "puntaje": None}
    if review["elegible"]:
        saved = artifacts["m3b"]
        frame = pd.DataFrame([features["m3b"]], columns=saved["model"].feature_names_in_)
        score = float(-saved["model"].score_samples(frame)[0])
        review.update(puntaje=score, umbral=saved["threshold"], alerta_revision=score >= saved["threshold"])
    return {"normativo": normative, "m1": risks, "m3a": profile, "m3b": review,
            "aviso_experimental": DISCLAIMER}
