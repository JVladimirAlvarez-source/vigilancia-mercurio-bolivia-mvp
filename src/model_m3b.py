"""Auditoría preanalítica con Isolation Forest."""
import numpy as np
from joblib import dump
from sklearn.ensemble import IsolationForest
from sklearn.metrics import average_precision_score, confusion_matrix, precision_score, recall_score

from .features_pipeline import DISCORDANCE
from .model_m1 import select_threshold

from .contracts import LAB, RANDOM_STATE, write_json

# Focus the forest on preanalytical discordance and exposure-adjusted lab values.
FEATURE_COLUMNS = [*LAB, *(f"{key}_residual" for key in LAB), *DISCORDANCE,
                   "segmento_cabello_cm", "dias_envio_lab"]


def _metrics(labels, scores, threshold):
    alerts = scores >= threshold
    tn, fp, fn, tp = confusion_matrix(labels, alerts, labels=[0, 1]).ravel()
    return {
        "precision": float(precision_score(labels, alerts, zero_division=0)),
        "recall": float(recall_score(labels, alerts, zero_division=0)),
        "pr_auc": float(average_precision_score(labels, scores)) if labels.sum() else None,
        "specificity": float(tn / (tn + fp)) if tn + fp else None,
        "confusion_matrix": [[int(tn), int(fp)], [int(fn), int(tp)]],
        "alert_rate": float(alerts.mean()),
    }


def train_m3b(frame, split, external_labels, models_dir, reports_dir):
    models_dir.mkdir(parents=True, exist_ok=True)
    split = split.reindex(frame.index)
    train, val, test = (frame.loc[split.eq(name), FEATURE_COLUMNS]
                        for name in ("train", "validation", "test"))
    if any(part.empty for part in (train, val, test)):
        raise ValueError("M3B requiere mediciones elegibles en cada partición")
    model = IsolationForest(random_state=RANDOM_STATE, contamination="auto", n_jobs=1)
    model.fit(train)
    val_scores = -model.score_samples(val)
    val_labels = external_labels.loc[val.index].to_numpy()
    threshold = (select_threshold(val_labels, val_scores) if np.unique(val_labels).size == 2
                 else float(np.quantile(val_scores, .92)))
    test_scores = -model.score_samples(test)
    test_labels = external_labels.loc[test.index].to_numpy()
    report = {
        "validation": _metrics(val_labels, val_scores, threshold),
        "test": _metrics(test_labels, test_scores, threshold),
        "umbral": threshold, "n_train": len(train), "n_validation": len(val), "n_test": len(test),
        "features": FEATURE_COLUMNS,
    }
    dump({"model": model, "threshold": threshold}, models_dir / "isolation_forest.joblib")
    write_json(reports_dir / "metrics_m3b.json", report)
    return report
