export type EvidenceKind =
  | "observed" | "derived" | "modelled" | "assigned"
  | "cluster" | "statistic" | "anomaly" | "association" | "model prediction" | "composite";

export interface Legend {
  min: number;
  max: number;
  quantiles: number[];
  categories?: { value: number; n: number; label: string | null }[];
}

export interface Layer {
  id: string;
  prop: string;
  group: string;
  title: string;
  unit: string;
  scale: "sequential" | "diverging" | "categorical";
  palette?: string;
  kind: string;
  source: string;
  period: string;
  description: string;
  legend: Legend;
  coverage: number;
  categories?: Record<string, string>;
}

export interface ValueEntry {
  feature: string;
  label: string;
  unit: string | null;
  kind: string | null;
  source: string | null;
  period: string | null;
  definition: string | null;
  value: number | string | null;
  city_median?: number | null;
  city_percentile?: number | null;
  subdivision_mean?: number | null;
  subdivision_n?: number;
  neighbours_mean?: number | null;
  neighbours_n?: number;
}

export interface ClusterRow {
  experiment_id: string;
  algorithm: string;
  module: string;
  cluster: number;
  name: string | null;
  n_cells: number | null;
  share: number | null;
  profile: Record<string, unknown> | null;
}

export interface AnomalyRow {
  experiment_id: string;
  algorithm: string;
  module: string;
  score: number;
  is_anomaly: boolean;
  lof_flag: boolean;
  direction: string | null;
  persistence: number | null;
  context: Record<string, number | null>;
}

export interface HotspotRow {
  experiment_id: string;
  algorithm: string;
  variable: string;
  gi_z: number;
  gi_p: number;
  gi_q_fdr: number;
  gi_class: string;
  gi_class_fdr: string;
}

export interface RuleRow {
  rule_id: number;
  experiment_id: string;
  antecedents: string[];
  consequent: string;
  support: number;
  confidence: number;
  lift: number;
  holds_for_cell?: boolean;
}

export interface TreeRow {
  experiment_id: string;
  algorithm: string;
  observed: number;
  predicted: number;
  probability: number;
  decision_path: string;
  cv_balanced_accuracy: string | null;
}

export interface Report {
  grid_id: string;
  generated_utc: string;
  identity: {
    grid_id: string; lat: number; lon: number; subdivision: string | null; frac_inside: number;
    is_land_cell: boolean | null; dominant_cover: string | null; data_quality_score: number | null; n_neighbours_1500m: number;
  };
  profile: { title: string; values: ValueEntry[] }[];
  mining: {
    clusters: ClusterRow[]; anomalies: AnomalyRow[]; hotspots: HotspotRow[];
    association_rules: RuleRow[]; cell_items: { experiment_id: string; items: string[] }[]; decision_tree: TreeRow[];
  };
  history: {
    epochs: { epoch: number; lst_mean: number | null; lst_rel: number | null; ndvi: number | null; ndbi: number | null; lst_cov: number | null }[];
    lst_scenes: { obs_date: string; platform: string; value: number; valid_fraction: number }[];
  };
  vulnerability: {
    score: null | {
      uvi: number | null; uvi_rank_pct: number | null; uvi_class: string | null; evidence_quality: number | null;
      dimensions_available: number | null; rank_p05: number | null; rank_p95: number | null; explanation: string | null;
      factors: Record<string, unknown> | null;
    };
    indicators: { dimension: string; value: number | null; n_inputs: number; n_available: number }[];
  };
  explanation: { text: string; evidence: EvidenceKind }[];
  sources: { key: string; title: string; provider: string; url: string; license: string | null }[];
  sources_used: string[];
  limitations: string[];
}

export interface Experiment {
  experiment_id: string;
  module: string;
  algorithm: string;
  purpose: string;
  input_features: string[];
  n_samples: number;
  parameters: Record<string, unknown>;
  metrics: Record<string, any>;
  results?: Record<string, any>;
  interpretation_notes: string[];
  limitations: string[];
  run_utc: string;
  code_version: string | null;
  cluster_profiles?: any[];
  rules?: RuleRow[];
}

export interface Discovery {
  discovery_id: string;
  category: string;
  title: string;
  description: string;
  period: string;
  algorithm: string;
  experiment_id: string;
  variables: string[];
  evidence: Record<string, any>;
  sources: string[];
  lon: number | null;
  lat: number | null;
  zoom: number | null;
  strength: number | null;
  n_cells: number;
  geometry: GeoJSON.Geometry | null;
}

export interface DataSource {
  key: string;
  title: string;
  provider: string;
  url: string;
  method: string | null;
  status: string;
  accessed_utc: string;
  license: string | null;
  crs: string | null;
  spatial_resolution: string | null;
  temporal_coverage: string | null;
  variables: string[] | null;
  limitations: string | null;
  files: { path: string; bytes: number; sha256: string | null }[] | null;
  extra: Record<string, unknown> | null;
}
