import { Bar as RBar, BarChart, CartesianGrid, Cell, ErrorBar, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useExperiment } from "@/services/api";
import type { Experiment } from "@/types/api";
import { fmt } from "@/maps/palettes";
import { useState } from "react";

const AX = { stroke: "#3b4a62", tick: { fill: "#6b788b", fontSize: 10 } };
const TT = { contentStyle: { background: "#0e131b", border: "1px solid #2b384d", fontSize: 11 }, labelStyle: { color: "#9aa7b8" } };

function zColor(z: number) {
  const a = Math.min(1, Math.abs(z) / 2);
  return z >= 0 ? `rgba(232,119,74,${a})` : `rgba(79,143,217,${a})`;
}

export function KMeansView({ e }: { e: Experiment }) {
  const sweep = e.metrics.sweep as any[];
  const profiles = (e.results?.profiles ?? []) as any[];
  const feats = e.input_features;
  return (
    <div className="space-y-4">
      <div className="text-xs text-fg-muted">{String(e.parameters.selection ?? "")}</div>
      <div className="grid grid-cols-2 gap-3">
        <div className="h-40">
          <div className="text-2xs text-fg-dim mb-1">Silhouette (↑) and Davies–Bouldin (↓) by K</div>
          <ResponsiveContainer>
            <LineChart data={sweep} margin={{ left: -20, right: 4 }}>
              <CartesianGrid stroke="#1f2a3c" />
              <XAxis dataKey="k" {...AX} />
              <YAxis {...AX} />
              <Tooltip {...TT} formatter={(v: number) => fmt(v, 3)} />
              <Legend wrapperStyle={{ fontSize: 10 }} />
              <Line dataKey="silhouette" stroke="#5eb1bf" dot />
              <Line dataKey="davies_bouldin" stroke="#d9b44a" dot />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <div className="h-40">
          <div className="text-2xs text-fg-dim mb-1">Elbow: within-cluster inertia by K</div>
          <ResponsiveContainer>
            <LineChart data={sweep} margin={{ left: 0, right: 4 }}>
              <CartesianGrid stroke="#1f2a3c" />
              <XAxis dataKey="k" {...AX} />
              <YAxis {...AX} tickFormatter={(v) => fmt(v / 1000, 0) + "k"} />
              <Tooltip {...TT} formatter={(v: number) => fmt(v, 0)} />
              <Line dataKey="inertia" stroke="#9a8fd1" dot />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
      {profiles.length > 0 && (
        <div className="overflow-x-auto">
          <div className="text-2xs text-fg-dim mb-1">Cluster profiles — cell colour = z-score of the cluster mean vs all analysed cells (orange above, blue below); value = mean in original units</div>
          <table className="w-full text-xs">
            <thead>
              <tr className="text-fg-dim text-2xs">
                <th className="text-left py-1 pr-2">#</th><th className="text-left pr-2">Generated name</th><th className="text-right pr-2">cells</th>
                {feats.map((f) => <th key={f} className="text-right px-1 font-normal">{f.replace(/_/g, " ")}</th>)}
              </tr>
            </thead>
            <tbody>
              {profiles.map((p) => (
                <tr key={p.cluster} className="border-t border-ink-800">
                  <td className="py-1 pr-2 num">{p.cluster}</td>
                  <td className="pr-2 text-fg-muted">{p.name}</td>
                  <td className="pr-2 text-right num">{p.n_cells}</td>
                  {feats.map((f) => (
                    <td key={f} className="px-1 text-right num" style={{ background: zColor(p[`z_${f}`]) }}>{fmt(p[`mean_${f}`])}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function GridTable({ rows, cols }: { rows: any[]; cols: string[] }) {
  return (
    <table className="w-full text-xs">
      <thead><tr className="text-2xs text-fg-dim">{cols.map((c) => <th key={c} className="text-right font-normal px-1 py-1">{c.replace(/_/g, " ")}</th>)}</tr></thead>
      <tbody>
        {rows.map((r, i) => (
          <tr key={i} className="border-t border-ink-800">{cols.map((c) => <td key={c} className="text-right num px-1 py-0.5">{fmt(r[c], 3)}</td>)}</tr>
        ))}
      </tbody>
    </table>
  );
}

function Metric({ k, v }: { k: string; v: any }) {
  return (
    <div className="rounded-md bg-ink-850 border border-ink-700 px-2.5 py-1.5">
      <div className="text-2xs text-fg-dim">{k}</div>
      <div className="num text-sm">{typeof v === "number" ? fmt(v, 3) : String(v ?? "—")}</div>
    </div>
  );
}

function RulesView({ id }: { id: string }) {
  const { data } = useExperiment(id);
  const rules = data?.rules ?? [];
  return (
    <div className="max-h-80 overflow-y-auto scroll-thin">
      <table className="w-full text-xs">
        <thead className="sticky top-0 bg-ink-900"><tr className="text-2xs text-fg-dim"><th className="text-left py-1">antecedents</th><th className="text-left">consequent</th><th className="text-right">support</th><th className="text-right">conf.</th><th className="text-right">lift</th></tr></thead>
        <tbody>
          {rules.map((r) => (
            <tr key={r.rule_id} className="border-t border-ink-800">
              <td className="py-1 pr-2 text-fg-muted">{r.antecedents.join(" ∧ ")}</td>
              <td className="pr-2">{r.consequent}</td>
              <td className="text-right num">{fmt(r.support, 3)}</td>
              <td className="text-right num">{fmt(r.confidence, 2)}</td>
              <td className="text-right num text-accent">{fmt(r.lift, 2)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function ExperimentCard({ e }: { e: Experiment }) {
  const [showRaw, setShowRaw] = useState(false);
  const m = e.metrics ?? {};
  const alg = e.algorithm.toLowerCase();
  let body: React.ReactNode = null;
  if (alg.startsWith("k-means")) body = <KMeansView e={e} />;
  else if (alg.startsWith("dbscan")) {
    body = (
      <div className="space-y-3">
        <div className="grid grid-cols-4 gap-2">
          <Metric k="clusters" v={m.n_clusters ?? m.n_hotspots} />
          {m.noise_share !== undefined && <Metric k="noise share" v={m.noise_share} />}
          {m.ari_vs_kmeans_non_noise !== undefined && <Metric k="ARI vs K-means" v={m.ari_vs_kmeans_non_noise} />}
          {m.agreement_with_gi_star_hot && <Metric k="Jaccard vs Gi* hot" v={m.agreement_with_gi_star_hot.jaccard} />}
        </div>
        <div className="text-2xs text-fg-dim">Parameter sensitivity</div>
        <GridTable rows={m.parameter_grid ?? []} cols={["eps", "min_samples", "n_clusters", "noise_share", "largest_cluster_share", "silhouette_non_noise"]} />
      </div>
    );
  } else if (alg.includes("gi*")) {
    body = (
      <div className="grid grid-cols-3 gap-2">
        <Metric k="Moran's I" v={m.moran?.I} /><Metric k="pseudo-p (Moran)" v={m.moran?.p_sim} /><Metric k="z (Moran)" v={m.moran?.z_norm} />
        <Metric k="hot-spot cells" v={m.n_hot} /><Metric k="cold-spot cells" v={m.n_cold} /><Metric k="hot after FDR" v={m.n_hot_fdr} />
      </div>
    );
  } else if (alg.includes("isolation")) {
    body = (
      <div className="grid grid-cols-3 gap-2">
        <Metric k="flagged" v={m.n_flagged} /><Metric k="warmer / cooler" v={`${m.n_warmer ?? m.n_up ?? "—"} / ${m.n_cooler ?? m.n_down ?? "—"}`} />
        <Metric k="Jaccard IF vs LOF" v={m.if_vs_lof?.jaccard} />
        {m.median_persistence_flagged !== undefined && <Metric k="persistence (flagged)" v={m.median_persistence_flagged} />}
        {m.median_persistence_unflagged !== undefined && <Metric k="persistence (others)" v={m.median_persistence_unflagged} />}
      </div>
    );
  } else if (alg.includes("spearman")) {
    const sp = (m.spearman ?? []) as any[];
    const ols = (m.ols_std_coefficients ?? []) as any[];
    body = (
      <div className="grid grid-cols-2 gap-3">
        <div className="h-48">
          <div className="text-2xs text-fg-dim mb-1">Spearman ρ with LST</div>
          <ResponsiveContainer>
            <BarChart data={sp} layout="vertical" margin={{ left: 40 }}>
              <XAxis type="number" domain={[-1, 1]} {...AX} />
              <YAxis type="category" dataKey="feature" {...AX} width={110} />
              <Tooltip {...TT} formatter={(v: number) => fmt(v, 3)} />
              <RBar dataKey="spearman_rho">{sp.map((d, i) => <Cell key={i} fill={d.spearman_rho >= 0 ? "#e8774a" : "#4f8fd9"} />)}</RBar>
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="h-48">
          <div className="text-2xs text-fg-dim mb-1">Standardized OLS β (95 % CI, HC3) · R² = {fmt(m.ols_r2, 3)}</div>
          <ResponsiveContainer>
            <BarChart data={ols.map((o) => ({ ...o, err: [o.std_beta - o.ci_low, o.ci_high - o.std_beta] }))} layout="vertical" margin={{ left: 40 }}>
              <XAxis type="number" {...AX} />
              <YAxis type="category" dataKey="feature" {...AX} width={110} />
              <Tooltip {...TT} formatter={(v: number) => fmt(v, 3)} />
              <RBar dataKey="std_beta">
                {ols.map((d, i) => <Cell key={i} fill={d.std_beta >= 0 ? "#e8774a" : "#4f8fd9"} />)}
                <ErrorBar dataKey="err" width={4} stroke="#9aa7b8" direction="x" />
              </RBar>
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="col-span-2 text-2xs text-fg-dim">Residual Moran's I = {fmt(m.residual_moran_I?.I, 3)} — neighbouring cells are not independent, so naive p-values overstate certainty.</div>
      </div>
    );
  } else if (alg.includes("fp-growth") || alg.includes("apriori") || alg.includes("association")) {
    body = (
      <div className="space-y-2">
        <div className="grid grid-cols-4 gap-2">
          <Metric k="rules kept" v={m.n_rules} /><Metric k="min support" v={e.parameters.min_support as number} />
          <Metric k="min confidence" v={e.parameters.min_confidence as number} /><Metric k="min lift" v={e.parameters.min_lift as number} />
        </div>
        <RulesView id={e.experiment_id} />
      </div>
    );
  } else if (alg.includes("decision tree")) {
    const cm = m.confusion_matrix ?? {};
    const imp = (e.results?.importance ?? []) as any[];
    body = (
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-2">
          <div className="grid grid-cols-3 gap-2">
            <Metric k="balanced acc." v={m.balanced_accuracy} /><Metric k="ROC AUC" v={m.roc_auc} /><Metric k="F1" v={m.f1} />
            <Metric k="precision" v={m.precision} /><Metric k="recall" v={m.recall} /><Metric k="depth" v={m.best_depth} />
          </div>
          <table className="text-xs num w-full"><tbody>
            <tr><td /><td className="text-2xs text-fg-dim text-center">pred 0</td><td className="text-2xs text-fg-dim text-center">pred 1</td></tr>
            <tr><td className="text-2xs text-fg-dim">obs 0</td><td className="text-center bg-ink-800 py-1">{cm.tn}</td><td className="text-center bg-ink-850">{cm.fp}</td></tr>
            <tr><td className="text-2xs text-fg-dim">obs 1</td><td className="text-center bg-ink-850 py-1">{cm.fn}</td><td className="text-center bg-ink-800">{cm.tp}</td></tr>
          </tbody></table>
          <div className="text-2xs text-fg-dim">{m.cv}</div>
        </div>
        <div className="h-48">
          <div className="text-2xs text-fg-dim mb-1">Feature importance (Gini)</div>
          <ResponsiveContainer>
            <BarChart data={imp.slice(0, 8)} layout="vertical" margin={{ left: 40 }}>
              <XAxis type="number" {...AX} />
              <YAxis type="category" dataKey="feature" {...AX} width={110} />
              <Tooltip {...TT} formatter={(v: number) => fmt(v, 3)} />
              <RBar dataKey="gini_importance" fill="#9a8fd1" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    );
  } else if (m.epochs) {
    body = (
      <div className="h-48">
        <ResponsiveContainer>
          <LineChart data={m.epochs} margin={{ left: -15, right: 8 }}>
            <CartesianGrid stroke="#1f2a3c" />
            <XAxis dataKey="epoch" {...AX} />
            <YAxis {...AX} />
            <Tooltip {...TT} formatter={(v: number) => fmt(v, 2)} />
            <Legend wrapperStyle={{ fontSize: 10 }} />
            <Line dataKey="rel_built_dominant" name="built-up cells (rel. LST)" stroke="#c9a46b" />
            <Line dataKey="rel_bare_dominant" name="bare cells (rel. LST)" stroke="#e8774a" />
            <Line dataKey="rel_veg_dominant" name="vegetated cells (rel. LST)" stroke="#6bbf8a" />
          </LineChart>
        </ResponsiveContainer>
      </div>
    );
  }
  return (
    <section className="panel p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-2xs text-fg-dim num">{e.experiment_id} · n = {e.n_samples?.toLocaleString()} · run {e.run_utc?.slice(0, 16).replace("T", " ")}{e.code_version ? ` · ${e.code_version}` : ""}</div>
          <h3 className="font-semibold mt-0.5">{e.algorithm}</h3>
          <p className="text-sm text-fg-muted">{e.purpose}</p>
        </div>
        <button className="btn shrink-0" onClick={() => setShowRaw(!showRaw)}>{showRaw ? "Hide" : "Parameters"}</button>
      </div>
      {showRaw && (
        <pre className="mt-3 text-2xs bg-ink-950 border border-ink-700 rounded p-2 overflow-x-auto max-h-64 scroll-thin">{JSON.stringify({ inputs: e.input_features, parameters: e.parameters }, null, 2)}</pre>
      )}
      {body && <div className="mt-4">{body}</div>}
      {(e.interpretation_notes?.length > 0 || e.limitations?.length > 0) && (
        <div className="mt-3 grid grid-cols-2 gap-3 text-2xs">
          {e.interpretation_notes?.length > 0 && <ul className="list-disc pl-4 text-fg-muted space-y-0.5">{e.interpretation_notes.map((n, i) => <li key={i}>{n}</li>)}</ul>}
          {e.limitations?.length > 0 && <ul className="list-disc pl-4 text-fg-dim space-y-0.5">{e.limitations.map((n, i) => <li key={i}>{n}</li>)}</ul>}
        </div>
      )}
    </section>
  );
}
