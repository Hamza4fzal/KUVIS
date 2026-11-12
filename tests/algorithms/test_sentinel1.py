"""SAR flood detection: only pixels that became dark open water count; missing data never becomes 'dry' or 'wet'."""

import numpy as np

from kuvis.acquisition.sentinel1 import _median3, detect


def test_detect_requires_both_dark_and_drop():
    ref = np.array([-8.0, -8.0, -19.0, -8.0])   # land, land, already-water, land
    vv = np.array([-21.0, -10.0, -22.0, -17.0])  # flooded, wet soil, still water, dark-ish but above threshold
    valid = np.ones(4, dtype=bool)
    assert detect(vv, ref, valid).tolist() == [True, False, False, False]


def test_detect_respects_mask_and_nan():
    ref = np.array([-8.0, np.nan, -8.0])
    vv = np.array([-21.0, -21.0, np.nan])
    valid = np.array([False, True, True])
    assert not detect(vv, ref, valid).any()


def test_median3_ignores_nan_and_keeps_holes():
    a = np.full((5, 5), -10.0, dtype="float32")
    a[2, 2] = -30.0          # isolated speckle spike is removed
    a[0, 0] = np.nan         # missing pixel stays missing
    m = _median3(a)
    assert m[2, 2] == -10.0
    assert np.isnan(m[0, 0])
    assert np.isfinite(m[1:, 1:]).all()
