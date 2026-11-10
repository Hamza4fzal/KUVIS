-- Discretized items of each cell per association-mining experiment, so rules can be matched to a location.
SET search_path = kuvis, public;
CREATE TABLE cell_transactions (
    grid_id       text REFERENCES spatial_cells(grid_id) ON DELETE CASCADE,
    experiment_id text REFERENCES mining_experiments(experiment_id) ON DELETE CASCADE,
    items         text[] NOT NULL,
    PRIMARY KEY (grid_id, experiment_id)
);
CREATE INDEX ON cell_transactions USING gin (items);
CREATE INDEX ON association_rules USING gin (antecedents);
