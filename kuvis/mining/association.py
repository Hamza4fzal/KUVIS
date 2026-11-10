"""Association rule mining (FP-Growth via mlxtend) on discretized cell attributes.

Continuous variables are discretized into labelled tertiles/quantile bins (or documented physical
thresholds). Rules are kept when they pass support/confidence/lift thresholds and are then pruned
for redundancy: a rule is dropped if a more general rule (antecedent subset, same consequent) has
lift at least as high (within 2 %). Rules describe co-occurrence — never causation.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from mlxtend.frequent_patterns import association_rules, fpgrowth


def qbin(s: pd.Series, labels=("Low", "Medium", "High"), q=None) -> pd.Series:
    q = q or np.linspace(0, 1, len(labels) + 1)
    edges = np.unique(s.quantile(q).values)
    if len(edges) - 1 != len(labels):
        return pd.Series(pd.NA, index=s.index, dtype="object")
    return pd.cut(s, edges, labels=list(labels), include_lowest=True).astype("object")


def transactions(df: pd.DataFrame) -> pd.DataFrame:
    """One-hot boolean matrix of "var=Level" items; missing values contribute no item."""
    cols = {}
    for c in df.columns:
        for lvl in df[c].dropna().unique():
            cols[f"{c}={lvl}"] = (df[c] == lvl).fillna(False).astype(bool).values
    return pd.DataFrame(cols, index=df.index)


def mine(onehot: pd.DataFrame, consequents: list[str], min_support: float, min_confidence: float,
         min_lift: float, max_len: int = 4) -> pd.DataFrame:
    fi = fpgrowth(onehot, min_support=min_support, use_colnames=True, max_len=max_len)
    if fi.empty:
        return pd.DataFrame()
    rules = association_rules(fi, metric="confidence", min_threshold=min_confidence)
    rules = rules[rules["lift"] >= min_lift]
    cons = set(consequents)
    rules = rules[rules["consequents"].apply(lambda s: len(s) == 1 and next(iter(s)) in cons)]
    # no antecedent may contain another level of the consequent's own variable
    rules = rules[rules.apply(lambda r: not any(a.split("=")[0] == next(iter(r.consequents)).split("=")[0]
                                                    for a in r.antecedents), axis=1)]
    rules = prune_redundant(rules)
    rules = rules.sort_values(["lift", "confidence"], ascending=False).reset_index(drop=True)
    out = pd.DataFrame({
        "antecedents": rules["antecedents"].apply(sorted),
        "consequent": rules["consequents"].apply(lambda s: next(iter(s))),
        "support": rules["support"], "confidence": rules["confidence"], "lift": rules["lift"],
        "leverage": rules["leverage"], "conviction": rules["conviction"],
        "antecedent_support": rules["antecedent support"], "consequent_support": rules["consequent support"],
    })
    out["n_items"] = out["antecedents"].apply(len)
    return out


def prune_redundant(rules: pd.DataFrame, tol: float = 0.02) -> pd.DataFrame:
    keep = []
    rs = rules.reset_index(drop=True)
    for i, r in rs.iterrows():
        redundant = False
        for j, o in rs.iterrows():
            if i == j or o.consequents != r.consequents:
                continue
            if o.antecedents < r.antecedents and o.lift >= r.lift * (1 - tol):
                redundant = True
                break
        if not redundant:
            keep.append(i)
    return rs.loc[keep]


def rule_matches(row_items: set[str], antecedents: list[str]) -> bool:
    return set(antecedents) <= row_items
