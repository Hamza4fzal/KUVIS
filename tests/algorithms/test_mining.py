"""Behavioural tests of the mining library on controlled synthetic inputs (test fixtures only —
never used as Karachi data)."""

import numpy as np
import pandas as pd

from kuvis.acquisition.optical import nd
from kuvis.acquisition.satellite import ST_OFF, ST_SCALE
from kuvis.mining import anomaly, association, clustering, spatial
from kuvis.modules.common import relabel_by

rng = np.random.default_rng(0)


def test_kmeans_sweep_recovers_three_blobs():
    X = np.vstack([rng.normal(c, 0.3, size=(200, 2)) for c in ((0, 0), (5, 0), (0, 5))])
    sweep = clustering.kmeans_sweep(X, (2, 6))
    k, rule = clustering.choose_k(sweep, min_k=2)
    assert k == 3 and "silhouette" in rule
    assert {"inertia", "silhouette", "davies_bouldin", "calinski_harabasz"} <= set(sweep.columns)


def test_profile_names_come_from_zscores():
    df = pd.DataFrame({"t": [10, 11, 30, 31], "v": [0.5, 0.6, 0.1, 0.0]})
    p = clustering.profile(df, np.array([0, 0, 1, 1]), ["t", "v"], {"t": "LST", "v": "NDVI"})
    hot = p[p.cluster == 1].iloc[0]
    assert "high LST" in hot["name"] and "low NDVI" in hot["name"]


def test_dbscan_grid_reports_noise():
    X = np.vstack([rng.normal(0, 0.1, (100, 2)), [[10, 10]]])
    g = clustering.dbscan_grid(X, [0.5], [5])
    assert g.loc[0, "n_clusters"] == 1 and g.loc[0, "noise_share"] > 0


def test_relabel_orders_by_value():
    labels = np.array([2, 2, 0, 0, 1, 1, -1])
    vals = pd.Series([1, 1, 9, 9, 5, 5, 0])
    assert list(relabel_by(labels, vals)) == [0, 0, 2, 2, 1, 1, -1]


def test_isolation_forest_finds_planted_outlier():
    X = np.vstack([rng.normal(0, 1, (500, 3)), [[8, 8, 8]]])
    score, flag = anomaly.isolation_forest(X, 0.01, 200, 0)
    assert flag[-1] and score[-1] == score.max()


def test_robust_z_within_groups():
    s = pd.Series([1, 2, 3, 100, 101, 102])
    g = pd.Series(["a", "a", "a", "b", "b", "b"])
    z = anomaly.robust_z(s, g)
    assert np.isclose(z.iloc[1], 0) and np.isclose(z.iloc[4], 0)


def test_neighbour_residual():
    x = np.array([0, 500, 1000, 5000.0])
    y = np.zeros(4)
    v = np.array([1, 1, 4, 7.0])
    r = anomaly.neighbour_residual(x, y, v, radius=600)
    assert r[2] == 3 and np.isnan(r[3])  # isolated cell has no neighbours


def test_association_rules_metrics_and_pruning():
    n = 1000
    a = rng.random(n) < 0.5
    b = rng.random(n) < 0.5
    y = (a & (rng.random(n) < 0.9)) | (~a & (rng.random(n) < 0.1))  # y depends on a only
    df = pd.DataFrame({"A": np.where(a, "High", "Low"), "B": np.where(b, "High", "Low"), "Y": np.where(y, "Yes", "No")})
    oh = association.transactions(df)
    rules = association.mine(oh, ["Y=Yes"], 0.05, 0.6, 1.2)
    assert len(rules) >= 1
    top = rules.iloc[0]
    assert top["antecedents"] == ["A=High"]
    assert abs(top["lift"] - top["confidence"] / oh["Y=Yes"].mean()) < 1e-9
    # {A=High, B=*} adds nothing over {A=High} → pruned as redundant
    assert not any(set(r) > {"A=High"} for r in rules["antecedents"])


def test_gi_star_detects_hot_block():
    xs, ys = np.meshgrid(np.arange(20) * 500.0, np.arange(20) * 500.0)
    v = np.zeros_like(xs)
    v[:5, :5] = 10
    v += 20 + rng.normal(0, 0.1, v.shape)  # G* needs non-negative values
    g = spatial.gi_star(v.ravel(), xs.ravel(), ys.ravel(), threshold=1000, permutations=99)
    assert (g.gi_class.to_numpy().reshape(20, 20)[1:4, 1:4] == "hot").all()


def test_gi_star_rejects_negative_values():
    # regression: G* on a zero-centred variable silently flips hot/cold spots
    import pytest
    xs, ys = np.meshgrid(np.arange(10) * 500.0, np.arange(10) * 500.0)
    v = rng.normal(0, 1, xs.shape)
    with pytest.raises(ValueError):
        spatial.gi_star(v.ravel(), xs.ravel(), ys.ravel(), threshold=1000, permutations=9)


def test_landsat_st_scaling_matches_usgs():
    # USGS C2 L2: ST(K) = DN*0.00341802 + 149.0 ; DN 44000 → 299.39 K → 26.24 °C
    assert abs((44000 * ST_SCALE + ST_OFF - 273.15) - 26.24) < 0.01


def test_normalized_difference_bounds_and_nan():
    a, b = np.array([0.5, 0.0, np.nan]), np.array([0.1, 0.0, 0.2])
    r = nd(a, b)
    assert np.isclose(r[0], 0.4 / 0.6) and np.isnan(r[1]) and np.isnan(r[2])
