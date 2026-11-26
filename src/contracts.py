"""Contratos compartidos por auditoría, entrenamiento e inferencia."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RANDOM_STATE = 42


def read_config(name):
    return json.loads((ROOT / "config" / f"{name}.json").read_text(encoding="utf-8"))


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                    encoding="utf-8")


SCHEMA = read_config("schema")
FEATURES = read_config("feature_config")
RULES = read_config("normative_rules")
ID = SCHEMA["id"]
PRELAB = FEATURES["PRELAB_ALLOWLIST"]
LAB = SCHEMA["lab_columns"]
TARGETS = SCHEMA["targets"]
CLINICAL = FEATURES["clinical"]
