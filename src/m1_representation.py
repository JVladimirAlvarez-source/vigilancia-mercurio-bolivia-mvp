"""Auditoría de redundancia y selección de representación sólo en train."""
from itertools import combinations

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform
from scipy.stats import chi2_contingency
from threadpoolctl import threadpool_limits

from .contracts import CLINICAL
from .derived_features import DOMAINS
from .features_pipeline import CATEGORICAL

INDEX_COLUMNS = {f"indice_{key}" for key in DOMAINS}
SHAP_GROUPS = {CLINICAL[i - 35]: domain for domain, indices in DOMAINS.items() for i in indices}


def candidate_columns(columns):
    return {
        "M1-A": [key for key in columns if key not in INDEX_COLUMNS],
        "M1-B": [key for key in columns if key not in CLINICAL],
        "M1-C": list(columns),
    }


def _cramer_v(left, right):
    table = pd.crosstab(left, right)
    rows, cols = table.shape
    n = table.to_numpy().sum()
    if n <= 1 or min(rows, cols) < 2:
        return 0.
    phi = chi2_contingency(table, correction=False).statistic / n
    corrected = max(0, phi - (rows - 1) * (cols - 1) / (n - 1))
    denominator = min(rows - 1 - (rows - 1) ** 2 / (n - 1),
                      cols - 1 - (cols - 1) ** 2 / (n - 1))
    return float(np.sqrt(corrected / denominator)) if denominator > 0 else 0.


def audit_representation(train):
    categorical = [key for key in CATEGORICAL if key in train]
    numeric = train.drop(columns=categorical)
    correlation = numeric.corr(method="spearman").abs().fillna(0)
    clusters = []
    if len(numeric.columns) > 1:
        distance = 1 - correlation.to_numpy()
        distance = (distance + distance.T) / 2
        np.fill_diagonal(distance, 0)
        groups = fcluster(linkage(squareform(distance), method="complete"), .15, criterion="distance")
        clusters = [numeric.columns[groups == group].tolist() for group in sorted(set(groups))
                    if np.sum(groups == group) > 1]
    complete = numeric.fillna(numeric.median())
    scaled = ((complete - complete.mean()) / complete.std()).fillna(0).to_numpy()
    vif = {}
    with threadpool_limits(limits=1, user_api="blas"):
        for index, key in enumerate(numeric):
            x, y = np.delete(scaled, index, axis=1), scaled[:, index]
            total = float(y @ y)
            if not total:
                continue
            fitted = x @ np.linalg.lstsq(x, y, rcond=None)[0]
            residual = float((y - fitted) @ (y - fitted))
            if residual <= total / 5:
                vif[key] = total / residual if residual > total * 1e-12 else "dependencia exacta"
    return {
        "spearman_abs_ge_085": [[left, right, float(correlation.at[left, right])]
                                 for left, right in combinations(numeric, 2)
                                 if correlation.at[left, right] >= .85],
        "cramer_v_ge_080": [[left, right, value] for left, right in combinations(categorical, 2)
                            if (value := _cramer_v(train[left], train[right])) >= .8],
        "vif_ge_5": vif,
        "complete_linkage": clusters,
        "linaje_sintomas_por_dominio": {key: [CLINICAL[i - 35] for i in indexes]
                                        for key, indexes in DOMAINS.items()},
    }
