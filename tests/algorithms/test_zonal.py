"""Zonal statistics must be exact and must never turn missing data into zeros."""

import geopandas as gpd
import numpy as np
from affine import Affine
from shapely.geometry import box

from kuvis.preprocessing import zonal


def _grid():
    # two 20×20 m cells side by side on a 10 m raster → 4 pixels each
    return gpd.GeoDataFrame({"grid_id": ["A", "B"]}, geometry=[box(0, 0, 20, 20), box(20, 0, 40, 20)], crs="EPSG:32642")


TR = Affine(10, 0, 0, 0, -10, 20)


def test_label_raster_assigns_pixel_centres():
    lab = zonal.label_raster(_grid(), "EPSG:32642", TR, (2, 4))
    assert (lab[:, :2] == 1).all() and (lab[:, 2:] == 2).all()


def test_stats_mean_and_coverage_with_missing():
    lab = zonal.label_raster(_grid(), "EPSG:32642", TR, (2, 4))
    v = np.array([[1, 2, np.nan, np.nan], [3, 4, np.nan, np.nan]], dtype=float)
    s = zonal.stats(lab, v, 2, prefix="x", which=("mean", "min", "max", "p90"))
    assert s.loc[0, "x_mean"] == 2.5 and s.loc[0, "x_cov"] == 1.0
    assert s.loc[0, "x_min"] == 1 and s.loc[0, "x_max"] == 4
    # cell B has no valid pixels → NaN, never 0
    assert np.isnan(s.loc[1, "x_mean"]) and s.loc[1, "x_n"] == 0 and s.loc[1, "x_cov"] == 0


def test_class_fractions_ignore_nodata():
    lab = zonal.label_raster(_grid(), "EPSG:32642", TR, (2, 4))
    cls = np.array([[50, 50, 0, 0], [10, 0, 80, 80]])
    f = zonal.class_fractions(lab, cls, 2, {10: "tree", 50: "built", 80: "water"}, nodata=0, prefix="wc")
    assert np.isclose(f.loc[0, "wc_built"], 2 / 3) and np.isclose(f.loc[0, "wc_tree"], 1 / 3)
    assert f.loc[1, "wc_water"] == 1.0


def test_sums_population():
    lab = zonal.label_raster(_grid(), "EPSG:32642", TR, (2, 4))
    p = np.array([[1, 1, 5, 5], [1, 1, 5, 5]], dtype=float)
    s = zonal.sums(lab, p, 2, prefix="pop")
    assert list(s["pop_sum"]) == [4, 20]
