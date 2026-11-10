-- KUVIS schema v1. Applied by kuvis/db/migrate.py; recorded in kuvis.schema_migrations.
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE SCHEMA IF NOT EXISTS kuvis;
SET search_path = kuvis, public;

-- ------------------------------------------------------------------ geography
CREATE TABLE study_areas (
    id          serial PRIMARY KEY,
    name        text NOT NULL,
    source_id   text,
    area_km2    double precision,
    geom        geometry(MultiPolygon, 4326) NOT NULL
);
CREATE TABLE administrative_boundaries (
    id          serial PRIMARY KEY,
    name        text NOT NULL,
    level       text NOT NULL,
    source_id   text,
    area_km2    double precision,
    geom        geometry(MultiPolygon, 4326) NOT NULL
);
CREATE INDEX ON administrative_boundaries USING gist (geom);

CREATE TABLE spatial_cells (
    grid_id       text PRIMARY KEY,
    row_idx       int NOT NULL,
    col_idx       int NOT NULL,
    lon           double precision NOT NULL,
    lat           double precision NOT NULL,
    x_utm         double precision NOT NULL,
    y_utm         double precision NOT NULL,
    area_m2       double precision NOT NULL,
    frac_inside   double precision NOT NULL,
    subdivision   text,
    is_land_cell  boolean,
    dominant_cover text,
    data_quality_score double precision,
    geom          geometry(Polygon, 4326) NOT NULL,
    geom_3857     geometry(Polygon, 3857) NOT NULL
);
CREATE INDEX ON spatial_cells USING gist (geom);
CREATE INDEX ON spatial_cells USING gist (geom_3857);
CREATE INDEX ON spatial_cells (subdivision);

CREATE TABLE roads (
    osm_id   bigint,
    highway  text,
    major    boolean,
    geom     geometry(LineString, 4326)
);
CREATE INDEX ON roads USING gist (geom);
CREATE TABLE waterways (
    osm_id   bigint,
    waterway text,
    name     text,
    geom     geometry(LineString, 4326)
);
CREATE INDEX ON waterways USING gist (geom);

-- ------------------------------------------------------------------ observations (one table per evidence family)
-- Wide-but-typed per-cell feature store; every column is described in feature_dictionary.
CREATE TABLE cell_features (
    grid_id  text PRIMARY KEY REFERENCES spatial_cells(grid_id) ON DELETE CASCADE,
    features jsonb NOT NULL
);
CREATE TABLE feature_dictionary (
    feature     text PRIMARY KEY,
    label       text, unit text, source text, period text, kind text, definition text
);
CREATE TABLE temperature_observations (          -- epoch composites
    grid_id     text REFERENCES spatial_cells(grid_id) ON DELETE CASCADE,
    epoch       int NOT NULL,
    lst_mean    double precision, lst_rel double precision, lst_p90 double precision,
    lst_cov     double precision, lst_nobs double precision,
    ndvi        double precision, ndbi double precision, mndwi double precision,
    PRIMARY KEY (grid_id, epoch)
);
CREATE TABLE temperature_scene_observations (    -- dated single-scene cell means
    grid_id        text REFERENCES spatial_cells(grid_id) ON DELETE CASCADE,
    scene_id       text NOT NULL,
    obs_date       date NOT NULL,
    platform       text,
    variable       text NOT NULL,
    value          double precision,
    valid_fraction double precision
);
CREATE INDEX ON temperature_scene_observations (grid_id, variable);
CREATE TABLE rainfall_pixels (
    pixel_id text PRIMARY KEY,
    lon double precision, lat double precision,
    geom geometry(Polygon, 4326)
);
CREATE TABLE rainfall_observations (
    pixel_id  text REFERENCES rainfall_pixels(pixel_id) ON DELETE CASCADE,
    year      int NOT NULL, month int NOT NULL,
    precip_mm double precision,           -- NULL = missing, never 0
    PRIMARY KEY (pixel_id, year, month)
);

-- ------------------------------------------------------------------ data mining
CREATE TABLE mining_experiments (
    experiment_id text PRIMARY KEY,
    module        text NOT NULL,
    algorithm     text NOT NULL,
    purpose       text,
    input_features jsonb, n_samples int, parameters jsonb, metrics jsonb, results jsonb,
    interpretation_notes jsonb, limitations jsonb,
    run_utc       timestamptz, code_version text
);
CREATE TABLE model_evaluation_metrics (
    experiment_id text REFERENCES mining_experiments(experiment_id) ON DELETE CASCADE,
    metric text, value double precision,
    PRIMARY KEY (experiment_id, metric)
);
CREATE TABLE cluster_profiles (
    experiment_id text REFERENCES mining_experiments(experiment_id) ON DELETE CASCADE,
    cluster  int, name text, n_cells int, share double precision, profile jsonb,
    PRIMARY KEY (experiment_id, cluster)
);
CREATE TABLE cluster_memberships (
    grid_id       text REFERENCES spatial_cells(grid_id) ON DELETE CASCADE,
    experiment_id text REFERENCES mining_experiments(experiment_id) ON DELETE CASCADE,
    cluster       int NOT NULL,              -- -1 = DBSCAN noise
    PRIMARY KEY (grid_id, experiment_id)
);
CREATE TABLE anomaly_observations (
    grid_id       text REFERENCES spatial_cells(grid_id) ON DELETE CASCADE,
    experiment_id text REFERENCES mining_experiments(experiment_id) ON DELETE CASCADE,
    score double precision, is_anomaly boolean, lof_flag boolean, direction text,
    persistence double precision, context jsonb,
    PRIMARY KEY (grid_id, experiment_id)
);
CREATE TABLE hotspot_statistics (
    grid_id       text REFERENCES spatial_cells(grid_id) ON DELETE CASCADE,
    experiment_id text REFERENCES mining_experiments(experiment_id) ON DELETE CASCADE,
    variable text, gi_z double precision, gi_p double precision, gi_q_fdr double precision,
    gi_class text, gi_class_fdr text,
    PRIMARY KEY (grid_id, experiment_id, variable)
);
CREATE TABLE association_rules (
    rule_id       serial PRIMARY KEY,
    experiment_id text REFERENCES mining_experiments(experiment_id) ON DELETE CASCADE,
    antecedents text[] NOT NULL, consequent text NOT NULL,
    support double precision, confidence double precision, lift double precision,
    leverage double precision, conviction double precision, n_items int
);
CREATE TABLE decision_tree_results (
    grid_id       text REFERENCES spatial_cells(grid_id) ON DELETE CASCADE,
    experiment_id text REFERENCES mining_experiments(experiment_id) ON DELETE CASCADE,
    observed int, predicted int, probability double precision, decision_path text,
    PRIMARY KEY (grid_id, experiment_id)
);

-- ------------------------------------------------------------------ vulnerability
CREATE TABLE vulnerability_weights (
    scheme text, dimension text, weight double precision,
    PRIMARY KEY (scheme, dimension)
);
CREATE TABLE vulnerability_indicators (
    grid_id   text REFERENCES spatial_cells(grid_id) ON DELETE CASCADE,
    dimension text, value double precision, n_inputs int, n_available int,
    PRIMARY KEY (grid_id, dimension)
);
CREATE TABLE vulnerability_scores (
    grid_id text PRIMARY KEY REFERENCES spatial_cells(grid_id) ON DELETE CASCADE,
    uvi double precision, uvi_rank_pct double precision, uvi_class text,
    evidence_quality double precision, dimensions_available int,
    rank_p05 double precision, rank_p95 double precision,
    combined_kmeans int, explanation text, factors jsonb
);

-- ------------------------------------------------------------------ application
CREATE TABLE discovery_reports (
    discovery_id text PRIMARY KEY,
    category text, title text, description text,
    period text, algorithm text, experiment_id text,
    variables jsonb, evidence jsonb, sources jsonb, grid_ids text[],
    lon double precision, lat double precision, zoom double precision,
    strength double precision,
    geom geometry(Geometry, 4326)
);
CREATE TABLE data_sources (
    key text PRIMARY KEY,
    title text, provider text, url text, method text, status text,
    accessed_utc timestamptz, license text, crs text, spatial_resolution text,
    temporal_coverage text, variables jsonb, limitations text, files jsonb, extra jsonb
);
CREATE TABLE processing_logs (
    id serial PRIMARY KEY, step text, started_utc timestamptz, finished_utc timestamptz,
    status text, message text
);
CREATE TABLE dataset_versions (
    key text, version text, sha256 text, loaded_utc timestamptz DEFAULT now(),
    PRIMARY KEY (key, version)
);
