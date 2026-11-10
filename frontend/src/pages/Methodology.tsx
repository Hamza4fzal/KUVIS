import { useState } from "react";
import ExperimentCard from "@/charts/ExperimentCard";
import { useDataStatus, useMethodology } from "@/services/api";
import { ErrorState, EvidenceChip, Loading, PageHeader, Section } from "@/components/ui";

const METHODS: [string, string][] = [
  ["Spatial framework", "Karachi Division boundary (geoBoundaries ADM2). Regular 500 m grid in WGS 84 / UTM 42N (EPSG:32642); cells keep the share of their area inside the boundary. Every raster is summarised on its own native pixel grid by rasterising cell IDs (no resampling of values); sources coarser than a cell (CHIRPS ≈5.5 km) are assigned from the pixel containing the cell centroid and never presented as 500 m measurements."],
  ["Satellite preprocessing", "Landsat Collection-2 Level-2: QA_PIXEL cloud/shadow/cirrus masking, ST_QA uncertainty ≤ 4 K, documented scale/offset to °C, physical-range checks, per-pixel median of the clearest scenes per WRS tile, Apr–Jun of each epoch. Sentinel-2 L2A: SCL masking, removal of the +1000 DN offset for processing baseline ≥ 04.00, dry-season median composite."],
  ["Missing data", "Invalid pixels are excluded, never set to zero. Every cell feature carries a valid-pixel coverage; cells with < 50 % valid LST pixels are excluded from heat analysis. The composite index uses an explicit coverage rule instead of treating missing dimensions as zero risk."],
  ["Clustering", "K-means on z-scored features with K chosen from a 2–10 sweep (silhouette, Davies–Bouldin, Calinski–Harabasz, elbow). DBSCAN in feature space (eps from the k-distance knee) and in geographic space (UTM metres) on the hottest decile of cells, with parameter-sensitivity grids. Cluster names are generated from centroid z-scores."],
  ["Spatial statistics", "Global Moran's I and local Getis–Ord Gi* with a 1 km distance band and permutation inference; Benjamini–Hochberg FDR-adjusted classes reported alongside raw pseudo-p-values."],
  ["Anomaly detection", "Isolation Forest on contextual residuals (vs. land-cover peers, 1.5 km neighbours, the cell's own history), Local Outlier Factor for comparison, and a persistence check against individual satellite dates."],
  ["Association rules", "FP-Growth on discretised (tertile) attributes with support/confidence/lift thresholds and redundancy pruning (a rule is dropped when a more general rule has at least the same lift). Rules describe co-occurrence, not causation."],
  ["Classification", "Decision Trees evaluated with spatially blocked cross-validation (GroupKFold on 5 km blocks) to avoid leakage between neighbouring cells; depth tuned inside CV; permutation importance reported. Trained only where a target independent of the predictors exists."],
  ["Composite vulnerability", "Dimension indicators are percentile-normalised means of their inputs; UVI = Σ wᵢ·Dᵢ / Σ wᵢ over available dimensions, equal weights baseline, computed only when ≥ 75 % of the weight is available. 1,000 Dirichlet-sampled weightings give each cell's plausible rank range. Not an official disaster-risk assessment."],
];

const EVIDENCE = ["observed", "derived", "modelled", "assigned", "cluster", "statistic", "anomaly", "association", "model prediction", "composite"];

export default function Methodology() {
  const { data: exps, isLoading, error } = useMethodology();
  const { data: status } = useDataStatus();
  const [mod, setMod] = useState<string>("all");
  const modules = Array.from(new Set((exps ?? []).map((e) => e.module)));
  return (
    <div className="h-full overflow-y-auto scroll-thin">
      <div className="max-w-[1300px] mx-auto p-6 space-y-4">
        <PageHeader kicker="Research & methodology" title="How every result was produced">
          Experiment records below are written by the pipeline at run time (inputs, parameters, metrics, limitations, code version) and loaded verbatim.
        </PageHeader>
        <Section title="Evidence types used throughout KUVIS">
          <div className="flex flex-wrap gap-1.5">{EVIDENCE.map((e) => <EvidenceChip key={e} kind={e} />)}</div>
          <p className="text-xs text-fg-muted mt-2">Observed = satellite/product values aggregated to the cell · derived = computed indices, distances, changes · modelled = third-party model estimates (WorldPop) · assigned = coarse value assigned from a larger pixel · cluster/statistic/anomaly/association/model prediction = data-mining outputs · composite = the vulnerability index.</p>
        </Section>
        <div className="grid grid-cols-3 gap-3">
          {METHODS.map(([t, d]) => (
            <div key={t} className="panel p-4"><div className="font-medium text-sm">{t}</div><p className="text-xs text-fg-muted mt-1.5 leading-relaxed">{d}</p></div>
          ))}
        </div>
        <div className="flex items-center gap-1.5 pt-2">
          <span className="panel-h mr-2">Experiments</span>
          {["all", ...modules].map((m) => <button key={m} className={`chip ${mod === m ? "border-accent text-accent" : "border-ink-600 text-fg-muted"}`} onClick={() => setMod(m)}>{m}</button>)}
        </div>
        {isLoading && <Loading />}
        {error && <ErrorState error={error} />}
        {(exps ?? []).filter((e) => mod === "all" || e.module === mod).map((e) => <ExperimentCard key={e.experiment_id} e={e} />)}
        {status?.feature_dictionary && (
          <Section title={`Feature dictionary (${status.feature_dictionary.length} features)`}>
            <div className="max-h-96 overflow-y-auto scroll-thin">
              <table className="w-full text-xs">
                <thead className="sticky top-0 bg-ink-900"><tr className="text-2xs text-fg-dim text-left"><th className="py-1">feature</th><th>label</th><th>unit</th><th>kind</th><th>source</th><th>period</th><th>definition</th></tr></thead>
                <tbody>
                  {status.feature_dictionary.map((f: any) => (
                    <tr key={f.feature} className="border-t border-ink-800 align-top">
                      <td className="py-1 num pr-2">{f.feature}</td><td className="pr-2">{f.label}</td><td className="pr-2 text-fg-muted">{f.unit}</td>
                      <td className="pr-2"><EvidenceChip kind={f.kind} /></td><td className="pr-2 text-fg-muted">{f.source}</td><td className="pr-2 text-fg-muted">{f.period}</td>
                      <td className="text-fg-dim">{f.definition}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Section>
        )}
      </div>
    </div>
  );
}
