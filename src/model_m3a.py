"""Fenotipado con Gower ponderado, HDBSCAN y asignación por medoides."""
from collections import Counter

import hdbscan
import numpy as np
import pandas as pd
from joblib import dump

from .contracts import FEATURES, LAB, write_json
from .features_pipeline import BLOCKS, CATEGORICAL


def gower(left, right, blocks=BLOCKS):
    """Devuelve distancia y cobertura, con peso uniforme dentro de cada bloque."""
    shape = (len(left), len(right))
    numerator, coverage = np.zeros(shape), np.zeros(shape)
    total_weight = sum(FEATURES["block_weights"][key] for key in blocks)
    for block, columns in blocks.items():
        weight = FEATURES["block_weights"][block] / (len(columns) * total_weight)
        for key in columns:
            a, b = left[key], right[key]
            shared = a.notna().to_numpy()[:, None] & b.notna().to_numpy()[None, :]
            if key in CATEGORICAL:
                delta = a.fillna("").to_numpy()[:, None] != b.fillna("").to_numpy()[None, :]
            else:
                delta = np.abs(a.fillna(0).to_numpy()[:, None] - b.fillna(0).to_numpy()[None, :])
            coverage += shared * weight
            numerator += shared * delta * weight
    distances = np.full(shape, np.inf)
    np.divide(numerator, coverage, out=distances,
              where=coverage + 1e-12 >= FEATURES["gower_min_coverage"])
    return distances, coverage


def assign_profiles(frame, artifact):
    medoids = artifact["medoids"]
    if medoids.empty:
        return np.full(len(frame), -1), np.full(len(frame), np.inf)
    distances, _ = gower(frame, medoids, artifact.get("blocks", BLOCKS))
    nearest = np.argmin(distances, axis=1)
    nearest_distance = distances[np.arange(len(frame)), nearest]
    accepted = np.isfinite(nearest_distance) & (nearest_distance <= artifact["radii"][nearest])
    return np.where(accepted, medoids.index.to_numpy()[nearest], -1), nearest_distance


def _fit_profiles(train, blocks):
    distance, coverage = gower(train, train, blocks)
    np.fill_diagonal(distance, 0)
    model = hdbscan.HDBSCAN(metric="precomputed", min_cluster_size=20, min_samples=5,
                            cluster_selection_method="eom", core_dist_n_jobs=1)
    labels = model.fit_predict(distance)
    medoids, radii, cluster_ids = [], [], []
    for label in sorted(set(labels) - {-1}):
        cluster = np.flatnonzero(labels == label)
        within = distance[np.ix_(cluster, cluster)]
        # Choose a medoid with shared coverage to every member whenever possible.
        means = within.mean(axis=1)
        if np.isfinite(means).any():
            best = int(np.argmin(means))
        else:
            counts = np.isfinite(within).sum(axis=1)
            means = np.where(np.isfinite(within), within, 0).sum(axis=1) / counts
            best = int(np.lexsort((means, -counts))[0])
        observed = within[best][np.isfinite(within[best])]
        medoids.append(train.iloc[cluster[best]].to_dict())
        radii.append(float(np.quantile(observed, .9)))
        cluster_ids.append(int(label))
    artifact = {"medoids": pd.DataFrame(medoids, columns=train.columns, index=cluster_ids),
                "radii": np.asarray(radii), "blocks": blocks}
    fit_report = {
        "clusters": len(cluster_ids), "train_counts": dict(Counter(map(int, labels))),
        "insufficient_shared_coverage_pairs_train": int(
            np.sum(np.triu(coverage + 1e-12 < FEATURES["gower_min_coverage"], k=1))),
        "medoid_radii_p90": dict(zip(cluster_ids, radii, strict=True)),
    }
    return model, artifact, fit_report


def train_m3a(frame, split, labs, models_dir, reports_dir):
    models_dir.mkdir(parents=True, exist_ok=True)
    train = frame.loc[split.eq("train")]
    model, artifact, fit_report = _fit_profiles(train, BLOCKS)
    _, clinical, clinical_report = _fit_profiles(train, {"clinica": BLOCKS["clinica"]})
    dump(artifact, models_dir / "medoids.joblib")
    dump(model, models_dir / "hdbscan.joblib")
    external, counts = {}, {}
    for partition in ("validation", "test"):
        held_out = frame.loc[split.eq(partition)]
        assigned, _ = assign_profiles(held_out, artifact)
        counts[partition] = dict(Counter(map(int, assigned)))
        clinical_labels, _ = assign_profiles(held_out, clinical)
        clinical_report[f"{partition}_counts"] = dict(Counter(map(int, clinical_labels)))
        external[partition] = {}
        for label in sorted(set(assigned)):
            group = labs.loc[held_out.index[assigned == label], LAB]
            external[partition][str(label)] = {
                key: {"n": int(group[key].count()),
                      "mediana": float(group[key].median()) if group[key].count() else None}
                for key in LAB
            }
    report = fit_report | {
        "validation_counts": counts["validation"], "test_counts": counts["test"],
        "biomarcadores_externos": external, "comparacion_FEN_A": clinical_report,
        "representacion_publicada": "FEN-B",
    }
    write_json(reports_dir / "metrics_m3a.json", report)
    return report
