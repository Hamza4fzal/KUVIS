"""Sentinel-1 SAR flood extent after the heaviest 2020 and 2022 monsoon rain days (independent inundation evidence).

Why: every other water variable in KUVIS (JRC GSW, WorldCover water, NDWI/MNDWI) comes from cloud-free optical
imagery, which almost never sees a monsoon flood. C-band radar sees through cloud, so open water standing on the
ground shortly after a storm can be mapped. This gives Module A an *event* label that is independent of the
intermittent-water proxy its models were trained on.

Method (documented, deterministic)
----------------------------------
1. Event days are chosen from data, not from memory: CHIRPS v3 daily (`sat`, IMERG-disaggregated) rainfall is read
   for June–September; an event day is one whose study-area mean rainfall is ≥ EVENT_RAIN_MM.
2. Post-event scenes: Sentinel-1 RTC (Planetary Computer `sentinel-1-rtc`, γ0 terrain-corrected) acquired within
   POST_WINDOW_H hours after the end of an event day (CHIRPS day D covers ≈ 00–24 UTC).
3. Reference: per relative orbit, MAX_REF dry-season passes (January–May of the same year), so the look geometry
   of reference and post-event images is identical. The reference is the per-pixel MINIMUM of those passes.
4. A pixel is flagged as newly flooded when VV_post < WATER_DB **and** VV_post is more than |DROP_DB| darker than
   EVERY dry-season pass. A median reference was tried first and rejected: leave-one-out tests on dry passes gave
   up to 43 km² of false "floods" on low coastal ground (tidal flats, salt pans) that is dark in some dry-season
   passes; the minimum reference removes those pixels by construction. Pixels that are normally water (JRC occurrence > 50 %) or on slopes > 5°
   (radar shadow/layover) are excluded. A 3 × 3 median filter suppresses speckle.
5. Images are read from the COG overview at 40 m (16-look averaging of the 10 m product) onto a fixed UTM grid;
   the share of flagged pixels per 500 m cell is the cell's flood fraction for that scene.

Limits (stated with the data): radar cannot see water under/between buildings (double-bounce and shadow make dense
urban floods nearly invisible), shallow water on rough surfaces, or floods that drained before the overpass.
A zero therefore means "no open water detected at the overpass", NOT "did not flood".
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone

import geopandas as gpd
import numpy as np
import pandas as pd
import planetary_computer
from rasterio.warp import Resampling
from scipy import ndimage

from .. import provenance
from ..config import get_logger, path
from ..preprocessing import zonal
from . import stac
from .chirps import _read as chirps_read
from .optical import TargetGrid, read_asset, write_tif
from .terrain import horn_slope_deg

log = get_logger("kuvis.sentinel1")

CHIRPS_DAILY = "https://data.chc.ucsb.edu/products/CHIRPS/v3.0/daily/final/sat/{y}/chirps-v3.0.sat.{y}.{m:02d}.{d:02d}.tif"
YEARS = (2020, 2022)
EVENT_RAIN_MM = 20.0
POST_WINDOW_H = 48
WATER_DB, DROP_DB = -18.0, -3.0
SENSITIVITY = [(-16.0, -2.0), (-18.0, -3.0), (-20.0, -4.0)]
RES = 40
OVR = 1  # COG overview level 1 of the 10 m RTC product ≈ 40 m
MAX_REF = 4
EDGE_PX = 8  # 320 m swath-edge trim
WORKERS = 3


def daily_rain(year: int, bbox) -> pd.DataFrame:
    """Study-area mean and max CHIRPS daily rainfall, 1 June – 30 September."""
    cache = path("raw", "chirps_daily", "x").parent
    days = pd.date_range(f"{year}-06-01", f"{year}-09-30", freq="D")
    from concurrent.futures import ThreadPoolExecutor
    def one(d):
        a, *_ = chirps_read("/vsicurl/" + CHIRPS_DAILY.format(y=d.year, m=d.month, d=d.day), bbox, cache)
        a = np.where(a < 0, np.nan, a.astype("float32"))
        return {"date": d, "mean_mm": float(np.nanmean(a)), "max_mm": float(np.nanmax(a))}
    with ThreadPoolExecutor(max_workers=2) as ex:  # CHC answers bursts with HTTP 429
        rows = list(ex.map(one, days))
    return pd.DataFrame(rows)


def _db(lin: np.ndarray) -> np.ndarray:
    with np.errstate(all="ignore"):
        out = 10 * np.log10(lin)
    out[~np.isfinite(out)] = np.nan
    return out


def _cache_file(d, orbit):
    return path("interim", "scene_cache", "x").parent / f"S1_{d:%Y%m%d}_o{int(orbit)}_vv{RES}.npz"


def _read_date(d, orbit, items: list, tg: TargetGrid) -> np.ndarray | None:
    """VV γ0 in dB for one pass (its frames mosaicked). Returns None — and caches nothing — unless every frame was
    read, so a network failure can never masquerade as 'no backscatter'. Each href is re-signed just before the read
    because Planetary Computer SAS tokens expire after roughly an hour."""
    cf = _cache_file(d, orbit)
    if cf.exists():
        return np.load(cf)["vv"].astype("float32")
    acc = np.full((tg.height, tg.width), np.nan, dtype="float32")
    for it in items:
        for attempt in range(4):
            try:
                href = planetary_computer.sign(it.assets["vv"].href.split("?")[0])
                a = read_asset(href, tg, resampling=Resampling.average, overview_level=OVR)
                break
            except Exception as exc:
                log.warning("%s attempt %d failed: %s", it.id, attempt + 1, str(exc)[:160])
                time.sleep(10 * (attempt + 1))
        else:
            log.warning("pass %s orbit %s skipped: frame %s unreadable", d, orbit, it.id)
            return None
        a[a <= 0] = np.nan
        acc = np.where(np.isfinite(acc), acc, a)
    if np.isfinite(acc).mean() < 0.05:
        log.warning("pass %s orbit %s skipped: <5 %% of the grid covered", d, orbit)
        return None
    db = _median3(_db(acc))
    np.savez_compressed(cf, vv=db.astype("float16"))
    log.info("read pass %s orbit %s (%d frames)", d, orbit, len(items))
    return db


def _median3(a: np.ndarray) -> np.ndarray:
    """3 × 3 median that ignores NaN without the cost of generic_filter: fill NaN with a sentinel far below any
    real backscatter, take the median, and restore NaN where the centre was NaN."""
    f = np.where(np.isfinite(a), a, -999.0)
    m = ndimage.median_filter(f, size=3, mode="nearest")
    m[(~np.isfinite(a)) | (m <= -900)] = np.nan
    return m.astype("float32")


def detect(vv: np.ndarray, ref: np.ndarray, valid: np.ndarray, water_db: float = WATER_DB,
           drop_db: float = DROP_DB) -> np.ndarray:
    """New open water: dark now (vv < water_db) AND darker than the dry-season reference (per-pixel minimum of the
    dry passes) by more than |drop_db|."""
    with np.errstate(invalid="ignore"):
        return valid & (vv < water_db) & (vv - ref < drop_db)


def _group_by_pass(items: list) -> dict:
    g: dict = {}
    for it in items:
        g.setdefault((it.datetime.date(), it.properties["sat:relative_orbit"]), []).append(it)
    return g


def _masks(tg: TargetGrid) -> tuple[np.ndarray, np.ndarray]:
    """(excluded, low_ground): excluded = steep terrain or normally-water pixels, where detection is not attempted;
    low_ground = elevation < 10 m, reported separately because tide and salt pans dominate false alarms there."""
    bad = np.zeros((tg.height, tg.width), dtype=bool)
    dem = read_asset(str(path("interim", "dem_utm30.tif")), tg, resampling=Resampling.average)
    bad |= horn_slope_deg(dem, RES) > 5
    occ = read_asset(str(path("interim", "jrc_occurrence.tif")), tg, resampling=Resampling.nearest)
    occ[occ > 100] = np.nan
    bad |= np.nan_to_num(occ, nan=0) > 50
    return bad, dem < 10


def run(grid: gpd.GeoDataFrame, study: gpd.GeoDataFrame) -> pd.DataFrame:
    bbox = stac.study_bbox_ll(study, 1000)
    tg = TargetGrid.around(study, RES, snap=RES)
    labels = zonal.label_raster(grid, tg.crs, tg.transform, (tg.height, tg.width))
    n = len(grid)
    excluded, low = _masks(tg)
    km2 = RES * RES / 1e6
    out = pd.DataFrame({"grid_id": grid["grid_id"].values})
    scene_rows, rain_tables, sens_rows, qc_rows = [], {}, [], []
    plans = {}
    for year in YEARS:  # 1) plan: event days → post-event passes → same-orbit dry-season reference passes
        rain = daily_rain(year, stac.study_bbox_ll(study, 6000))
        rain_tables[year] = rain
        events = rain[rain.mean_mm >= EVENT_RAIN_MM]
        log.info("%d: %d event days (study mean >= %.0f mm): %s", year, len(events), EVENT_RAIN_MM,
                 ", ".join(f"{d:%m-%d} {v:.0f}" for d, v in zip(events.date, events.mean_mm)))
        mon = _group_by_pass(stac.search("sentinel-1-rtc", bbox, f"{year}-06-01/{year}-10-05"))
        post = {}
        for (d, orbit), its in mon.items():
            t = its[0].datetime.astimezone(timezone.utc)
            for ed in events.date:
                end = datetime(ed.year, ed.month, ed.day, tzinfo=timezone.utc) + timedelta(days=1)
                if timedelta(0) <= t - end <= timedelta(hours=POST_WINDOW_H):
                    post[(d, orbit)] = (its, ed)
        log.info("%d: %d post-event passes: %s", year, len(post), sorted(f"{d} o{o}" for d, o in post))
        dry = _group_by_pass(stac.search("sentinel-1-rtc", bbox, f"{year}-01-01/{year}-05-31"))
        ref_keys = {}
        for orbit in {o for _, o in post}:
            passes = sorted(k for k in dry if k[1] == orbit)
            step = max(1, len(passes) // MAX_REF)
            ref_keys[orbit] = passes[::step][:MAX_REF]
        plans[year] = (rain, post, dry, ref_keys)
    # 2) fetch every needed pass, a few at a time (each 40 m pass read takes minutes on a slow link)
    jobs = {}
    for rain, post, dry, ref_keys in plans.values():
        jobs.update({k: its for k, (its, _) in post.items()})
        jobs.update({k: dry[k] for ks in ref_keys.values() for k in ks})
    log.info("Sentinel-1: %d passes needed, %d already cached", len(jobs), sum(_cache_file(*k).exists() for k in jobs))
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {k: ex.submit(lambda k, its: _read_date(k[0], k[1], its, tg) is not None, k, its) for k, its in jobs.items()}
        ok = {k: f.result() for k, f in futs.items()}
    log.info("Sentinel-1: %d/%d passes readable", sum(ok.values()), len(ok))
    # 3) detect
    for year, (rain, post, dry, ref_keys) in plans.items():
        if not post:
            continue
        refs = {}
        for orbit, ks in ref_keys.items():
            got = [(k, a) for k, a in ((k, _read_date(k[0], k[1], dry[k], tg)) for k in ks if ok[k]) if a is not None]
            if len(got) < 3:
                log.info("%d orbit %d: only %d dry-season passes, orbit not used", year, orbit, len(got))
                continue
            stack = np.stack([a for _, a in got])
            with np.errstate(all="ignore"):
                refs[orbit] = np.nanmin(stack, axis=0)
            # QC: leave-one-out — detect "floods" in each dry pass against the other dry passes. Rain-free passes
            # should give ~0 km²; this is the empirical false-alarm level of the method on this orbit.
            for i, (k, a) in enumerate(got):
                with np.errstate(all="ignore"):
                    r = np.nanmin(np.delete(stack, i, axis=0), axis=0)
                fl = detect(a, r, ndimage.binary_erosion(np.isfinite(a) & np.isfinite(r), iterations=EDGE_PX) & ~excluded)
                qc_rows.append({"year": year, "orbit": int(orbit), "dry_pass": str(k[0]),
                                "false_alarm_km2": float(fl.sum() * km2), "below_10m_km2": float((fl & low).sum() * km2)})
            log.info("%d orbit %d reference: %d dry-season passes; leave-one-out false alarms %s km²", year, orbit,
                     len(got), [round(q["false_alarm_km2"], 1) for q in qc_rows[-len(got):]])
        post = {k: v for k, v in post.items() if ok[k] and k[1] in refs}
        if not post:
            log.warning("%d: no usable post-event pass with a reference", year)
            continue
        year_frac = np.full(n, np.nan)
        year_any = np.zeros((tg.height, tg.width), dtype=bool)
        for (d, orbit), (its, ed) in sorted(post.items()):
            vv = _read_date(d, orbit, its, tg)
            ref = refs[orbit]
            # trim EDGE_PX pixels inside every swath edge: border pixels of a pass are partially filled by the
            # overview averaging and come out dark, which would otherwise show up as straight 'flood' stripes
            valid = ndimage.binary_erosion(np.isfinite(vv) & np.isfinite(ref), iterations=EDGE_PX) & ~excluded
            for wdb, ddb in SENSITIVITY:
                fl = detect(vv, ref, valid, wdb, ddb)
                sens_rows.append({"year": year, "date": str(d), "orbit": int(orbit), "water_db": wdb, "drop_db": ddb,
                                  "flooded_km2": float(fl.sum() * RES * RES / 1e6)})
            fl = detect(vv, ref, valid)
            year_any |= fl
            st = zonal.stats(labels, np.where(valid, fl.astype("float32"), np.nan), n, prefix="f", which=("mean",))
            frac = st["f_mean"].where(st["f_cov"] >= 0.5).values
            year_frac = np.where(np.isnan(year_frac), frac, np.fmax(year_frac, frac))
            scene_rows.append({"year": year, "date": str(d), "orbit": int(orbit), "event_day": f"{ed:%Y-%m-%d}",
                               "event_rain_mm": float(rain.loc[rain.date == ed, "mean_mm"].iloc[0]),
                               "scene_ids": [i.id for i in its], "flooded_km2": float(fl.sum() * km2),
                               "flooded_below_10m_km2": float((fl & low).sum() * km2),
                               "valid_km2": float(valid.sum() * RES * RES / 1e6)})
            log.info("%d %s orbit %d: %.1f km² newly dark water", year, d, orbit, scene_rows[-1]["flooded_km2"])
        out[f"s1_flood_frac_{year}"] = year_frac
        write_tif(np.where(np.isfinite(refs[next(iter(refs))]), year_any.astype("float32"), np.nan), tg,
                  path("interim", f"s1_flood_{year}.tif"))
    fr = [c for c in out.columns if c.startswith("s1_flood_frac_")]
    out["s1_flood_frac_max"] = out[fr].max(axis=1, skipna=True).where(out[fr].notna().any(axis=1))
    out.to_parquet(path("interim", "features_sentinel1.parquet"))
    meta = {"scenes": scene_rows, "sensitivity": sens_rows, "false_alarm_qc": qc_rows,
            "params": {"event_rain_mm": EVENT_RAIN_MM, "post_window_h": POST_WINDOW_H, "water_db": WATER_DB,
                       "drop_db": DROP_DB, "res_m": RES, "max_ref_passes": MAX_REF, "edge_trim_px": EDGE_PX,
                       "masks": "slope > 5° (NASADEM); JRC occurrence > 50 %",
                       "reference": "per-pixel minimum of the dry-season passes of the same orbit"},
            "daily_rain": {str(y): [{"date": f"{r.date:%Y-%m-%d}", "mean_mm": round(r.mean_mm, 1),
                                     "max_mm": round(r.max_mm, 1)} for r in t.itertuples()]
                           for y, t in rain_tables.items()}}
    path("processed", "sentinel1_events.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    provenance.record(
        "sentinel1",
        status="acquired",
        title="Sentinel-1 RTC (VV) post-monsoon-event open-water change detection, 2020 and 2022",
        provider="ESA Copernicus Sentinel-1; RTC processing by Microsoft Planetary Computer; event days from CHIRPS v3 daily (UCSB CHC)",
        url="https://planetarycomputer.microsoft.com/dataset/sentinel-1-rtc",
        method=f"Post-event VV < {WATER_DB} dB and drop > {-DROP_DB} dB versus same-orbit dry-season median; "
               f"scenes within {POST_WINDOW_H} h after CHIRPS event days (study mean >= {EVENT_RAIN_MM} mm)",
        files=[path("interim", f"s1_flood_{y}.tif") for y in YEARS],
        license="Copernicus Sentinel data (free, full and open); RTC product CC BY 4.0",
        crs=tg.crs,
        spatial_resolution=f"{RES} m (COG overview of 10 m RTC)",
        temporal_coverage="; ".join(f"{s['date']} (after {s['event_day']})" for s in scene_rows),
        variables=["s1_flood_frac_2020", "s1_flood_frac_2022", "s1_flood_frac_max"],
        limitations="Open-water detection only: dense urban flooding (double bounce, shadow), shallow water on rough "
                    "surfaces and water that drained before the overpass are missed. Zero = not detected.",
    )
    log.info("Sentinel-1: cells with detected flooding (>= 2 %%): %d", int((out.s1_flood_frac_max >= 0.02).sum()))
    return out
