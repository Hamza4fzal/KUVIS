"""API tests against the loaded KUVIS database. Skipped automatically when the database is not reachable/loaded."""

import pytest

try:
    from fastapi.testclient import TestClient

    from backend.app.main import app

    _client = TestClient(app)
    _client.__enter__()
    _ok = _client.get("/health").status_code == 200 and _client.get("/api/v1/overview").json()["cells"]["n_cells"] > 0
except Exception:  # database down or not loaded
    _ok = False

pytestmark = pytest.mark.skipif(not _ok, reason="KUVIS database not reachable or not loaded")


@pytest.fixture(scope="module")
def client():
    return _client


def test_overview_counts_match_grid(client):
    o = client.get("/api/v1/overview").json()
    assert o["cells"]["n_cells"] > 10_000
    assert o["study_area"]["area_km2"] > 3000


def test_layers_only_published_with_data(client):
    layers = client.get("/api/v1/map/layers").json()
    assert layers, "no layers published"
    for lyr in layers:
        assert 0 < lyr["coverage"] <= 1
        assert lyr["legend"]["min"] is not None


def test_grid_id_validation(client):
    assert client.get("/api/v1/areas/not-a-cell/report").status_code == 422
    assert client.get("/api/v1/areas/KHI_999999/report").status_code == 404


def test_report_structure_and_evidence_kinds(client):
    gid = client.get("/api/v1/areas/at", params={"lon": 67.03, "lat": 24.86}).json()["grid_id"]
    r = client.get(f"/api/v1/areas/{gid}/report").json()
    assert r["grid_id"] == gid and r["identity"]["lat"] > 24
    kinds = {v["kind"] for s in r["profile"] for v in s["values"]}
    assert kinds <= {"observed", "derived", "modelled", "assigned", None}
    # assigned (coarse) values must never carry a neighbour comparison
    for s in r["profile"]:
        for v in s["values"]:
            if v["kind"] == "assigned":
                assert "neighbours_mean" not in v


def test_point_outside_study_area_404(client):
    assert client.get("/api/v1/areas/at", params={"lon": 61.0, "lat": 29.0}).status_code == 404


def test_vector_tile_served(client):
    r = client.get("/api/v1/tiles/cells/10/702/438.pbf")  # tile containing central Karachi (24.9 N, 67.0 E)
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/vnd.mapbox-vector-tile")


def test_compare_requires_two(client):
    assert client.get("/api/v1/compare", params={"ids": "KHI_000001"}).status_code == 422


def test_sources_never_acquired_without_files(client):
    for s in client.get("/api/v1/data/sources").json():
        if s["status"] == "acquired":
            assert s["files"], f"{s['key']} marked acquired without files"
