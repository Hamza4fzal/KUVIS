"""Interpretable Decision Tree classification with spatially blocked evaluation.

Random train/test splits of neighbouring grid cells leak information through spatial
autocorrelation, so evaluation uses GroupKFold over square spatial blocks. Depth is tuned inside
the blocked CV; the reported scores are out-of-fold. The tree's rules are exported as text.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.inspection import permutation_importance
from sklearn.metrics import (accuracy_score, balanced_accuracy_score, confusion_matrix, f1_score,
                             precision_score, recall_score, roc_auc_score)
from sklearn.model_selection import GroupKFold
from sklearn.tree import DecisionTreeClassifier, export_text


def blocked_cv(X: pd.DataFrame, y: np.ndarray, groups: np.ndarray, depths=(2, 3, 4, 5, 6, 8),
               n_splits: int = 5, random_state: int = 42, min_leaf_frac: float = 0.01) -> dict:
    gkf = GroupKFold(n_splits=n_splits)
    min_leaf = max(5, int(min_leaf_frac * len(y)))
    by_depth = {}
    for d in depths:
        oof = np.zeros(len(y))
        for tr, te in gkf.split(X, y, groups):
            m = DecisionTreeClassifier(max_depth=d, min_samples_leaf=min_leaf, class_weight="balanced",
                                       random_state=random_state).fit(X.iloc[tr], y[tr])
            oof[te] = m.predict_proba(X.iloc[te])[:, 1]
        by_depth[d] = {"balanced_accuracy": balanced_accuracy_score(y, oof >= 0.5),
                       "roc_auc": roc_auc_score(y, oof) if len(set(y)) > 1 else np.nan, "oof": oof}
    best = max(by_depth, key=lambda d: by_depth[d]["balanced_accuracy"])
    oof = by_depth[best]["oof"]
    pred = (oof >= 0.5).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
    metrics = {
        "best_depth": best,
        "accuracy": accuracy_score(y, pred), "balanced_accuracy": balanced_accuracy_score(y, pred),
        "precision": precision_score(y, pred, zero_division=0), "recall": recall_score(y, pred, zero_division=0),
        "f1": f1_score(y, pred, zero_division=0), "roc_auc": by_depth[best]["roc_auc"],
        "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
        "positive_rate": float(np.mean(y)), "n_blocks": int(len(set(groups))), "cv": f"GroupKFold({n_splits}) on spatial blocks",
        "depth_search": {int(d): {"balanced_accuracy": v["balanced_accuracy"], "roc_auc": v["roc_auc"]} for d, v in by_depth.items()},
    }
    final = DecisionTreeClassifier(max_depth=best, min_samples_leaf=min_leaf, class_weight="balanced",
                                   random_state=random_state).fit(X, y)
    pi = permutation_importance(final, X, y, n_repeats=10, random_state=random_state, scoring="balanced_accuracy")
    imp = pd.DataFrame({"feature": X.columns, "gini_importance": final.feature_importances_,
                        "permutation_importance": pi.importances_mean}).sort_values("gini_importance", ascending=False)
    return {"model": final, "metrics": metrics, "importance": imp, "oof_proba": oof,
            "rules_text": export_text(final, feature_names=list(X.columns), decimals=2)}


def decision_paths(model: DecisionTreeClassifier, X: pd.DataFrame) -> list[str]:
    """Human-readable path for each row: 'feat <= t AND feat > t ...'."""
    t = model.tree_
    node_ind = model.decision_path(X)
    leaf = model.apply(X)
    out = []
    for i in range(len(X)):
        nodes = node_ind.indices[node_ind.indptr[i]:node_ind.indptr[i + 1]]
        conds = []
        for n in nodes:
            if leaf[i] == n:
                continue
            f, thr = X.columns[t.feature[n]], t.threshold[n]
            conds.append(f"{f} {'<=' if X.iloc[i, t.feature[n]] <= thr else '>'} {thr:.3g}")
        out.append(" AND ".join(conds))
    return out
