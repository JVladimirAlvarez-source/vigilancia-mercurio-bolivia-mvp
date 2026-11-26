"""Triaje prelaboratorio con cuatro modelos binarios independientes."""
import numpy as np
import pandas as pd
from joblib import dump
from lightgbm import LGBMClassifier, early_stopping
from sklearn.metrics import (average_precision_score, balanced_accuracy_score, brier_score_loss,
                             confusion_matrix, roc_auc_score, roc_curve)

from sklearn.model_selection import StratifiedKFold, cross_val_score

from .contracts import ID, RANDOM_STATE, TARGETS, write_json
from .features_pipeline import CATEGORICAL
from .m1_representation import audit_representation, candidate_columns

EPA = "y_mehg_cabello_epa"
CORD = "y_hg_cordon"
MODEL_TARGETS = (*TARGETS, EPA)
PAIRS = ((EPA, TARGETS[0]), tuple(TARGETS[:2]), tuple(TARGETS[2:]))


def _classifier():
    return LGBMClassifier(
        objective="binary", n_estimators=300, learning_rate=.03, num_leaves=15,
        max_depth=4, min_child_samples=30, colsample_bytree=.8, subsample=.8,
        subsample_freq=1, reg_alpha=.1, reg_lambda=1., random_state=RANDOM_STATE,
        verbosity=-1, n_jobs=1, deterministic=True, force_col_wise=True,
    )



def select_threshold(y, scores, minimum_sensitivity=.90):
    if len(np.unique(y)) != 2:
        raise ValueError("La validación requiere ambas clases para calibrar triaje")
    fpr, sensitivity, thresholds = roc_curve(y, scores, drop_intermediate=False)
    candidates = np.flatnonzero(sensitivity >= minimum_sensitivity)
    best = min(candidates, key=lambda i: (fpr[i], -sensitivity[i], -thresholds[i]))
    return float(thresholds[best])


def score_metrics(y, score, threshold):
    if not len(y):
        return dict.fromkeys(("average_precision", "sensibilidad", "especificidad",
                              "balanced_accuracy", "roc_auc", "brier_score")) | {
            "tn": 0, "fp": 0, "fn": 0, "tp": 0}
    predicted = score >= threshold
    tn, fp, fn, tp = confusion_matrix(y, predicted, labels=[0, 1]).ravel()
    return {
        "average_precision": average_precision_score(y, score) if tp + fn else None,
        "sensibilidad": float(tp / (tp + fn)) if tp + fn else None,
        "especificidad": float(tn / (tn + fp)) if tn + fp else None,
        "balanced_accuracy": balanced_accuracy_score(y, predicted) if len(set(y)) == 2 else None,
        "roc_auc": roc_auc_score(y, score) if len(set(y)) == 2 else None,
        "brier_score": brier_score_loss(y, score),
        "tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp),
    }


def nested_scores(scores):
    ordered = dict(scores)
    for lower, higher in PAIRS:
        ordered[higher] = np.minimum(ordered[higher], ordered[lower])
    return ordered


def train_m1(frame, labels, split, models_dir, reports_dir):
    models_dir.mkdir(parents=True, exist_ok=True)
    representation = audit_representation(frame.loc[split.eq("train")])
    comparisons = {}
    variants = candidate_columns(frame.columns)
    models, prevalence = {}, {}
    probabilities = {name: {} for name in ("validation", "test")}
    for target in MODEL_TARGETS:
        observed = labels[target].notna()
        train = split.eq("train") & observed
        val = split.eq("validation") & observed
        if labels.loc[train, target].nunique() != 2:
            raise ValueError(f"Faltan clases de entrenamiento para {target}")
        if labels.loc[val, target].nunique() != 2:
            raise ValueError(f"Faltan clases de validación para {target}")
        y_train = labels.loc[train, target]
        n_splits = min(3, int(y_train.value_counts().min()))
        folds = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=RANDOM_STATE)
        scores = {}
        for variant, selected in variants.items():
            categorical = [key for key in CATEGORICAL if key in selected]
            scores[variant] = float(cross_val_score(
                _classifier(), frame.loc[train, selected], y_train, scoring="average_precision",
                cv=folds, params={"categorical_feature": categorical}).mean())
        selected_name = max(scores, key=scores.get)
        columns = variants[selected_name]
        comparisons[target] = {"media_pr_auc_train_cv": scores, "seleccion": selected_name,
                               "columnas": columns, "folds": n_splits}
        categorical = [key for key in CATEGORICAL if key in columns]
        model = _classifier()
        model.fit(frame.loc[train, columns], y_train,
                  eval_set=[(frame.loc[val, columns], labels.loc[val, target])],
                  categorical_feature=categorical, callbacks=[early_stopping(25, verbose=False)])
        models[target] = model
        prevalence[target] = float(labels.loc[train, target].mean())
        for name in probabilities:
            probabilities[name][target] = model.predict_proba(frame.loc[split.eq(name), columns])[:, 1]
        dump(model, models_dir / f"{target}.joblib")

    metrics, thresholds, monotonicity, validation_metrics = [], {}, {}, {}
    val_scores, test_scores = (nested_scores(probabilities[name]) for name in ("validation", "test"))
    for name, predictions in probabilities.items():
        monotonicity[name] = {
            higher: int(np.sum(predictions[higher] > predictions[lower]))
            for lower, higher in PAIRS
        }
    predictions = pd.DataFrame(index=frame.index[split.eq("test")])
    for target in MODEL_TARGETS:
        val_y = labels.loc[split.eq("validation"), target]
        val_valid = val_y.notna()
        # Highest-consequence urine endpoint uses full observed sensitivity in validation.
        minimum = 1.0 if target == "y_hg_urinario_guia537" else .90
        thresholds[target] = select_threshold(val_y[val_valid], val_scores[target][val_valid], minimum)
    independent_thresholds = dict(thresholds)
    for lower, higher in reversed(PAIRS):
        thresholds[lower] = min(thresholds[lower], thresholds[higher])
    for target in MODEL_TARGETS:
        val_y = labels.loc[split.eq("validation"), target]
        test_y = labels.loc[split.eq("test"), target]
        val_valid, test_valid = val_y.notna(), test_y.notna()
        threshold = thresholds[target]
        validation_metrics[target] = score_metrics(val_y[val_valid], val_scores[target][val_valid],
                                                   threshold)
        base = prevalence[target]
        baseline = np.full(len(test_y), base)
        # The constant baseline also uses the validation sensitivity rule.
        base_threshold = select_threshold(val_y[val_valid], np.full(int(val_valid.sum()), base))
        for method, scores, cutoff in (("lightgbm", test_scores[target], threshold),
                                       ("prevalencia_train", baseline, base_threshold)):
            result = score_metrics(test_y[test_valid], scores[test_valid], cutoff)
            metrics.append({"target": target, "modelo": method, "umbral": cutoff,
                            "n_test": int(test_valid.sum()), **result})
        predictions[f"{target}_real"] = test_y
        predictions[f"{target}_p_original"] = probabilities["test"][target]
        predictions[f"{target}_p"] = test_scores[target]
        predictions[f"{target}_alerta"] = test_scores[target] >= threshold
    pd.DataFrame(metrics).to_csv(reports_dir / "metrics_m1.csv", index=False)
    predictions.to_csv(reports_dir / "predictions_test.csv", index_label=ID)
    # Report alert inversions separately: each threshold optimizes its own endpoint.
    for name, scores in (("validation", val_scores), ("test", test_scores)):
        monotonicity[f"{name}_alertas_umbrales_independientes"] = {
            higher: int(np.sum((scores[higher] >= independent_thresholds[higher])
                              & (scores[lower] < independent_thresholds[lower])))
            for lower, higher in PAIRS
        }
        monotonicity[f"{name}_alertas"] = {
            higher: int(np.sum((scores[higher] >= thresholds[higher])
                              & (scores[lower] < thresholds[lower])))
            for lower, higher in PAIRS
        }
    write_json(models_dir / "thresholds.json", thresholds)
    write_json(reports_dir / "monotonicity_m1.json", monotonicity)
    write_json(reports_dir / "representation_m1.json", representation | {"comparaciones": comparisons})
    return {"test": metrics, "validation": validation_metrics,
            "monotonicidad_modelos_independientes": monotonicity,
            "representacion": comparisons, "targets_sin_modelo": {CORD: "Sin mediciones de cordón en la cohorte"}}
