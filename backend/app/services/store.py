"""In-process cache of per-cell features loaded from PostGIS (≈15 k rows), used for percentiles,
neighbour statistics and subdivision comparisons. Loaded lazily from the database on first use."""

from __future__ import annotations

import threading

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from ..core.db import fetch_all


class Store:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._loaded = False

    def _load(self) -> None:
        rows = fetch_all("""SELECT c.grid_id, c.lon, c.lat, c.x_utm, c.y_utm, c.subdivision, c.is_land_cell,
                                   c.frac_inside, c.dominant_cover, c.data_quality_score, f.features
                            FROM kuvis.spatial_cells c LEFT JOIN kuvis.cell_features f USING (grid_id)""")
        base = pd.DataFrame([{k: v for k, v in r.items() if k != "features"} for r in rows])
        feats = pd.DataFrame([r["features"] or {} for r in rows])
        feats = feats.drop(columns=[c for c in feats.columns if c in base.columns], errors="ignore")
        self.df = pd.concat([base, feats], axis=1).set_index("grid_id")
        self.tree = cKDTree(self.df[["x_utm", "y_utm"]].values)
        self.dictionary = {r["feature"]: r for r in fetch_all("SELECT * FROM kuvis.feature_dictionary")}
        self._loaded = True

    def ensure(self) -> "Store":
        if not self._loaded:
            with self._lock:
                if not self._loaded:
                    self._load()
        return self

    def reload(self) -> None:
        with self._lock:
            self._loaded = False
            self._load()

    def numeric(self, col: str) -> pd.Series:
        s = pd.to_numeric(self.df[col], errors="coerce") if col in self.df else pd.Series(dtype=float)
        return s

    def land(self) -> pd.Series:
        return self.df["is_land_cell"].fillna(False).astype(bool)

    def neighbours(self, grid_id: str, radius: float = 1500) -> list[str]:
        r = self.df.loc[grid_id]
        idx = self.tree.query_ball_point([r.x_utm, r.y_utm], r=radius)
        ids = self.df.index[idx]
        return [i for i in ids if i != grid_id]

    def percentile(self, col: str, value: float, land_only: bool = True) -> float | None:
        s = self.numeric(col)
        if land_only:
            s = s[self.land()]
        s = s.dropna()
        if s.empty or value is None or not np.isfinite(value):
            return None
        return float((s < value).mean() * 100)


store = Store()
