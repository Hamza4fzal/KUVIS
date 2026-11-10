import { useRef, useState } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from "recharts";
import { useReport } from "@/services/api";
import { useMapStore } from "@/store/mapStore";
import type { Report, ValueEntry } from "@/types/api";
import { Bar, EvidenceChip, ErrorState, Loading } from "@/components/ui";
import { fmt } from "@/maps/palettes";
import { exportReportPdf } from "./exportPdf";

const AX = { stroke: "#3b4a62", tick: { fill: "#6b788b", fontSize: 10 } };
const TT = { contentStyle: { background: "#0e131b", border: "1px solid #2b384d", fontSize: 11 }, labelStyle: { color: "#9aa7b8" } };

function ValueRow({ v }: { v: ValueEntry }) {
  const isNum = typeof v.value === "number";
  return (
    <div className="py-2 border-b border-ink-800 last:border-0">
      <div className="flex items-baseline justify-between gap-2">
        <div className="text-sm text-fg-muted leading-tight" title={v.definition ?? undefined}>{v.label}</div>
        <div className="flex items-center gap-1.5 shrink-0">
          <span className="num text-sm">{isNum ? fmt(v.value as number) : (v.value ?? "—")}</span>
          <span className="text-2xs text-fg-dim">{v.unit && v.unit !== "class" ? v.unit : ""}</span>
        </div>
      </div>
      {isNum && v.city_percentile !== undefined && v.city_percentile !== null && (
        <div className="mt-1.5 grid grid-cols-[1fr_auto] items-center gap-2">
          <Bar value={v.city_percentile} max={100} color="#5eb1bf" />
          <span className="text-2xs text-fg-dim num w-[64px] text-right">P{fmt(v.city_percentile, 0)} city</span>
        </div>
      )}
      <div className="flex flex-wrap gap-x-3 gap-y-0.5 mt-1 text-2xs text-fg-dim">
        <EvidenceChip kind={v.kind} />
        {v.city_median != null && <span>city median <span className="num text-fg-muted">{fmt(v.city_median)}</span></span>}
        {v.neighbours_mean != null && <span>1.5 km neighbours <span className="num text-fg-muted">{fmt(v.neighbours_mean)}</span></span>}
        {v.subdivision_mean != null && <span>subdivision <span className="num text-fg-muted">{fmt(v.subdivision_mean)}</span></span>}
        <span>{v.source} · {v.period}</span>
      </div>
    </div>
  );
}

function Collapsible({ title, children, defaultOpen = true, chip }: { title: string; children: React.ReactNode; defaultOpen?: boolean; chip?: string }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="border-t border-ink-700">
      <button className="w-full flex items-center justify-between px-4 py-2.5 hover:bg-ink-850" onClick={() => setOpen(!open)}>
        <span className="panel-h flex items-center gap-2">{title}{chip && <EvidenceChip kind={chip} />}</span>
        <span className="text-fg-dim text-xs">{open ? "−" : "+"}</span>
      </button>
      {open && <div className="px-4 pb-3">{children}</div>}
    </div>
  );
}

function Mining({ r }: { r: Report }) {
  const m = r.mining;
  return (
    <div className="space-y-3 text-sm">
      {m.clusters.length === 0 && <div className="text-fg-dim text-xs">This cell was not part of any clustering experiment (e.g. water or outside analysed land cells).</div>}
      {m.clusters.map((c) => (
        <div key={c.experiment_id} className="rounded-md bg-ink-850 border border-ink-700 p-2.5">
          <div className="flex justify-between items-center">
            <span className="text-2xs text-fg-dim">{c.algorithm} · <span className="num">{c.experiment_id}</span></span>
            <EvidenceChip kind="cluster" />
          </div>
          <div className="mt-1">{c.cluster < 0 ? <span className="text-fg-muted">Noise / not in a dense group</span> : <>Group <span className="num">{c.cluster}</span>{c.name && <> — <span className="text-fg">{c.name}</span></>}</>}</div>
          {c.n_cells != null && <div className="text-2xs text-fg-dim mt-0.5">{c.n_cells} cells{c.share != null ? ` · ${fmt(c.share * 100, 1)} % of analysed cells` : ""}</div>}
        </div>
      ))}
      {m.hotspots.map((h) => (
        <div key={h.experiment_id} className="rounded-md bg-ink-850 border border-ink-700 p-2.5">
          <div className="flex justify-between"><span className="text-2xs text-fg-dim">{h.algorithm}</span><EvidenceChip kind="statistic" /></div>
          <div className="mt-1">{h.gi_class === "not significant" ? "Not part of a significant hot/cold spot" : <>Significant <b className={h.gi_class === "hot" ? "text-heat" : "text-flood"}>{h.gi_class} spot</b> of {h.variable}</>}</div>
          <div className="text-2xs text-fg-dim num mt-0.5">z = {fmt(h.gi_z, 2)} · pseudo-p = {fmt(h.gi_p, 3)} · FDR q = {fmt(h.gi_q_fdr, 3)}</div>
        </div>
      ))}
      {m.anomalies.map((a) => (
        <div key={a.experiment_id} className="rounded-md bg-ink-850 border border-ink-700 p-2.5">
          <div className="flex justify-between"><span className="text-2xs text-fg-dim">{a.algorithm}</span><EvidenceChip kind="anomaly" /></div>
          <div className="mt-1">{a.is_anomaly ? <b className="text-vuln">Anomalous — {a.direction}</b> : "Not anomalous"}{a.lof_flag ? " · also flagged by LOF" : ""}</div>
          <div className="text-2xs text-fg-dim num mt-0.5">
            score {fmt(a.score, 3)}{a.persistence != null && ` · recurs on ${fmt(a.persistence * 100, 0)} % of single dates`}
          </div>
          <div className="text-2xs text-fg-dim mt-0.5">
            {Object.entries(a.context ?? {}).map(([k, v]) => `${k.replace(/^anom_|^chg_/, "")}: ${fmt(v as number, 2)}`).join(" · ")}
          </div>
        </div>
      ))}
      {m.association_rules.length > 0 && (
        <div className="rounded-md bg-ink-850 border border-ink-700 p-2.5">
          <div className="flex justify-between"><span className="text-2xs text-fg-dim">Association rules whose conditions this cell meets</span><EvidenceChip kind="association" /></div>
          <div className="mt-1 space-y-1.5">
            {m.association_rules.slice(0, 6).map((ru) => (
              <div key={ru.rule_id} className="text-xs">
                <span className="text-fg-muted">{ru.antecedents.join(" ∧ ")}</span> <span className="text-accent">⇒</span>{" "}
                <span className={ru.holds_for_cell ? "text-fg" : "text-fg-dim line-through"}>{ru.consequent}</span>
                <span className="num text-2xs text-fg-dim"> · conf {fmt(ru.confidence * 100, 0)} % · lift {fmt(ru.lift, 2)}</span>
              </div>
            ))}
          </div>
          <div className="text-2xs text-fg-dim mt-1.5">Struck-through consequent = rule's conditions hold but the outcome does not here. Rules are co-occurrence, not causation.</div>
        </div>
      )}
      {m.decision_tree.map((t) => (
        <div key={t.experiment_id} className="rounded-md bg-ink-850 border border-ink-700 p-2.5">
          <div className="flex justify-between"><span className="text-2xs text-fg-dim">{t.algorithm}</span><EvidenceChip kind="model prediction" /></div>
          <div className="mt-1">Predicted <b>{t.predicted}</b> (p = {fmt(t.probability, 2)}), observed <b>{t.observed}</b></div>
          <div className="text-2xs text-fg-dim mt-0.5 font-mono break-words">{t.decision_path}</div>
        </div>
      ))}
    </div>
  );
}

function History({ r }: { r: Report }) {
  const ep = r.history.epochs.filter((e) => e.lst_mean != null || e.ndvi != null);
  const sc = r.history.lst_scenes.map((s) => ({ t: new Date(s.obs_date).getTime(), v: s.value, d: s.obs_date }));
  if (!ep.length) return <div className="text-xs text-fg-dim">No historical Landsat observations for this cell.</div>;
  return (
    <div className="space-y-3">
      <div>
        <div className="text-2xs text-fg-dim mb-1">Relative LST (°C vs city median) and NDVI per Landsat epoch (Apr–Jun composites)</div>
        <div className="h-36">
          <ResponsiveContainer>
            <LineChart data={ep} margin={{ left: -18, right: 6, top: 4 }}>
              <CartesianGrid stroke="#1f2a3c" />
              <XAxis dataKey="epoch" {...AX} />
              <YAxis yAxisId="l" {...AX} />
              <YAxis yAxisId="r" orientation="right" {...AX} domain={[-0.1, 0.6]} />
              <Tooltip {...TT} />
              <Line yAxisId="l" dataKey="lst_rel" name="relative LST" stroke="#e8774a" strokeWidth={2} dot />
              <Line yAxisId="r" dataKey="ndvi" name="NDVI" stroke="#6bbf8a" strokeWidth={2} dot />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
      {sc.length > 0 && (
        <div>
          <div className="text-2xs text-fg-dim mb-1">Single-date LST observations of this cell ({sc.length} clear scenes)</div>
          <div className="h-32">
            <ResponsiveContainer>
              <ScatterChart margin={{ left: -18, right: 6, top: 4 }}>
                <CartesianGrid stroke="#1f2a3c" />
                <XAxis dataKey="t" type="number" domain={["dataMin", "dataMax"]} {...AX} tickFormatter={(t) => new Date(t).getFullYear().toString()} />
                <YAxis dataKey="v" {...AX} unit="°" />
                <Tooltip {...TT} formatter={(v: number) => fmt(v)} labelFormatter={() => ""} />
                <Scatter data={sc} fill="#e8774a" />
              </ScatterChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  );
}

export default function ReportPanel() {
  const { selected, select, toggleCompare, compareSet } = useMapStore();
  const { data: r, isLoading, error } = useReport(selected);
  const bodyRef = useRef<HTMLDivElement>(null);
  const [exporting, setExporting] = useState(false);
  if (!selected) return null;
  return (
    <aside className="absolute top-0 right-0 bottom-0 w-[440px] bg-ink-900/97 backdrop-blur border-l border-ink-700 flex flex-col z-20 shadow-2xl">
      <div className="px-4 py-3 border-b border-ink-700 flex items-start justify-between gap-2">
        <div>
          <div className="panel-h text-accent">Location intelligence report</div>
          <div className="num text-lg font-semibold">{selected}</div>
          {r && <div className="text-xs text-fg-muted">{r.identity.subdivision ?? "No subdivision"} · {fmt(r.identity.lat, 4)}°N, {fmt(r.identity.lon, 4)}°E</div>}
        </div>
        <div className="flex gap-1.5">
          <button className="btn" onClick={() => toggleCompare(selected)}>{compareSet.includes(selected) ? "− Compare" : "+ Compare"}</button>
          <button className="btn" disabled={!r || exporting} onClick={async () => { setExporting(true); try { await exportReportPdf(r!, bodyRef.current); } finally { setExporting(false); } }}>
            {exporting ? "Exporting…" : "PDF"}
          </button>
          <button className="btn" onClick={() => select(null)} aria-label="close">✕</button>
        </div>
      </div>
      <div ref={bodyRef} className="flex-1 overflow-y-auto scroll-thin">
        {isLoading && <Loading label="Assembling report" />}
        {error && <div className="p-4"><ErrorState error={error} /></div>}
        {r && (
          <>
            <div className="px-4 py-3 grid grid-cols-3 gap-2 text-center">
              <div className="rounded-md bg-ink-850 py-2"><div className="text-2xs text-fg-dim">Land cover</div><div className="text-sm capitalize">{r.identity.dominant_cover ?? "—"}</div></div>
              <div className="rounded-md bg-ink-850 py-2"><div className="text-2xs text-fg-dim">Inside boundary</div><div className="text-sm num">{fmt(r.identity.frac_inside * 100, 0)} %</div></div>
              <div className="rounded-md bg-ink-850 py-2"><div className="text-2xs text-fg-dim">Data quality</div><div className="text-sm num">{fmt(r.identity.data_quality_score, 2)}</div></div>
            </div>
            <Collapsible title="Explanation">
              <ul className="space-y-2">
                {r.explanation.map((e, i) => (
                  <li key={i} className="text-sm leading-relaxed text-fg/90">
                    <EvidenceChip kind={e.evidence} /> <span className="ml-1">{e.text}</span>
                  </li>
                ))}
                {!r.explanation.length && <li className="text-xs text-fg-dim">No analytical findings available for this cell.</li>}
              </ul>
            </Collapsible>
            <Collapsible title="Data-mining findings"><Mining r={r} /></Collapsible>
            {r.vulnerability.score && (
              <Collapsible title="Composite vulnerability" chip="composite">
                <div className="flex items-baseline gap-2">
                  <span className="text-3xl font-semibold num text-vuln">{fmt(r.vulnerability.score.uvi, 2)}</span>
                  <span className="text-sm text-fg-muted">{r.vulnerability.score.uvi_class} · P{fmt(r.vulnerability.score.uvi_rank_pct, 0)}</span>
                </div>
                <div className="text-2xs text-fg-dim">Rank under 1,000 alternative weightings: P{fmt(r.vulnerability.score.rank_p05, 0)}–P{fmt(r.vulnerability.score.rank_p95, 0)} · evidence quality {fmt(r.vulnerability.score.evidence_quality, 2)}</div>
                <div className="mt-2 space-y-1.5">
                  {r.vulnerability.indicators.map((d) => (
                    <div key={d.dimension} className="grid grid-cols-[110px_1fr_40px] items-center gap-2 text-xs">
                      <span className="capitalize text-fg-muted">{d.dimension}</span>
                      <Bar value={d.value} color="#d65b72" />
                      <span className="num text-right">{fmt(d.value, 2)}</span>
                    </div>
                  ))}
                </div>
              </Collapsible>
            )}
            <Collapsible title="Historical profile"><History r={r} /></Collapsible>
            {r.profile.map((s) => (
              <Collapsible key={s.title} title={s.title} defaultOpen={["Surface heat", "Land cover", "Vegetation & surface indices"].includes(s.title)}>
                {s.values.map((v) => <ValueRow key={v.feature} v={v} />)}
              </Collapsible>
            ))}
            <Collapsible title="Limitations" defaultOpen={false}>
              <ul className="list-disc pl-4 space-y-1 text-xs text-fg-muted">{r.limitations.map((l, i) => <li key={i}>{l}</li>)}</ul>
            </Collapsible>
            <Collapsible title="Sources" defaultOpen={false}>
              <ul className="space-y-1 text-xs">
                {r.sources.map((s) => (
                  <li key={s.key}><a className="link" href={s.url} target="_blank" rel="noreferrer">{s.title}</a> <span className="text-fg-dim">— {s.provider}{s.license ? ` · ${s.license}` : ""}</span></li>
                ))}
              </ul>
            </Collapsible>
            <div className="px-4 py-3 text-2xs text-fg-dim">Generated {new Date(r.generated_utc).toLocaleString()} from the KUVIS database.</div>
          </>
        )}
      </div>
    </aside>
  );
}
