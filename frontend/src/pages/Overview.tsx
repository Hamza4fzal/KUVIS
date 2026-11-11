import { Link, useNavigate } from "react-router-dom";
import MapView from "@/maps/MapView";
import { useOverview } from "@/services/api";
import { useMapStore } from "@/store/mapStore";
import { Empty, ErrorState, Loading, PageHeader, Section, Stat } from "@/components/ui";
import { fmt } from "@/maps/palettes";

const STATUS_COLOR: Record<string, string> = {
  acquired: "#6bbf8a", alternative_selected: "#5eb1bf", requires_authentication: "#d9b44a",
  requires_manual_request: "#d9b44a", requires_payment: "#d65b72", unavailable: "#6b788b", failed: "#d65b72",
};

export default function Overview() {
  const { data: o, isLoading, error } = useOverview();
  const nav = useNavigate();
  const { setLayers } = useMapStore();
  if (isLoading) return <Loading label="Loading overview" />;
  if (error) return <div className="p-6"><ErrorState error={error} /></div>;
  const modules = Array.from(new Set((o.experiments as any[]).map((e) => e.module)));
  return (
    <div className="h-full overflow-y-auto scroll-thin">
      <div className="max-w-[1400px] mx-auto p-6">
        <PageHeader kicker="Urban intelligence overview" title={`${o.study_area?.name ?? "Karachi"} — geospatial data-mining results`}>
          Every number on this page is read from the KUVIS database, produced by the reproducible pipeline from the datasets listed under Data Sources.
          Observations are historical satellite and open data, not real-time measurements.
        </PageHeader>
        <div className="grid grid-cols-6 gap-3">
          <Stat label="Study area" value={`${fmt(o.study_area?.area_km2, 0)} km²`} sub="geoBoundaries ADM2 (2019)" />
          <Stat label="Grid cells (500 m)" value={fmt(o.cells?.n_cells, 0)} sub={`${fmt(o.cells?.n_land, 0)} land cells analysed`} />
          <Stat label="Mining experiments" value={o.experiments.length} sub={`${modules.length} modules`} />
          <Stat label="Cluster groups" value={fmt(o.n_cluster_groups, 0)} sub="K-means + DBSCAN profiles" />
          <Stat label="Anomalous cells" value={fmt(o.n_anomalies, 0)} sub="Isolation Forest, contextual" accent="#d65b72" />
          <Stat label="Association rules" value={fmt(o.n_rules, 0)} sub="after redundancy pruning" />
        </div>
        <div className="grid grid-cols-[1.4fr_1fr] gap-4 mt-4">
          <section className="panel overflow-hidden relative h-[440px]">
            <MapView layerIds={o.vulnerability?.n_scored ? ["uvi"] : ["lst_2024"]} interactive={false} showHover={false} />
            <div className="absolute top-3 left-3 panel px-3 py-2 text-xs">
              <div className="panel-h">{o.vulnerability?.n_scored ? "Composite vulnerability" : "Land surface temperature 2024"}</div>
            </div>
            <button className="btn-primary absolute top-3 right-3" onClick={() => { setLayers([o.vulnerability?.n_scored ? "uvi" : "lst_2024"]); nav("/explore"); }}>Open interactive map →</button>
          </section>
          <div className="space-y-4">
            <Section title="Recently discovered patterns" right={<Link className="link text-xs" to="/discoveries">all →</Link>}>
              {o.top_discoveries?.length ? (
                <ul className="space-y-2">
                  {o.top_discoveries.map((d: any) => (
                    <li key={d.discovery_id}>
                      <Link to={`/discoveries#${d.discovery_id}`} className="block rounded-md bg-ink-850 border border-ink-700 hover:border-ink-500 p-2.5">
                        <div className="text-2xs text-fg-dim uppercase tracking-wide">{d.category}</div>
                        <div className="text-sm">{d.title}</div>
                      </Link>
                    </li>
                  ))}
                </ul>
              ) : <Empty>No discoveries stored yet — run the <code>discoveries</code> pipeline step.</Empty>}
            </Section>
            <Section title="Temporal coverage">
              <div className="flex flex-wrap gap-1.5">
                {(o.landsat_epochs ?? []).map((e: number) => <span key={e} className="chip border-heat/40 text-heat">Landsat {e}</span>)}
              </div>
              <div className="text-2xs text-fg-dim mt-2">Only epochs with processed observations are listed. Data last accessed {o.data_last_accessed ? new Date(o.data_last_accessed).toLocaleDateString() : "—"}.</div>
            </Section>
            <Section title="Dataset availability" right={<Link className="link text-xs" to="/sources">catalogue →</Link>}>
              <div className="space-y-1">
                {(o.source_status ?? []).map((s: any) => (
                  <div key={s.status} className="kv text-sm">
                    <span className="flex items-center gap-2"><span className="h-2 w-2 rounded-full" style={{ background: STATUS_COLOR[s.status] ?? "#6b788b" }} />{s.status.replace(/_/g, " ")}</span>
                    <span className="num">{s.n}</span>
                  </div>
                ))}
              </div>
            </Section>
          </div>
        </div>
        <Section title="Analytical modules" className="mt-4">
          <div className="grid grid-cols-5 gap-3">
            {[["heat", "/heat", "#e8774a", "Heat"], ["flood", "/flood", "#4f8fd9", "Flood"], ["urban", "/urbanization", "#c9a46b", "Urbanization"],
              ["infra", "/infrastructure", "#9a8fd1", "Infrastructure"], ["vulnerability", "/vulnerability", "#d65b72", "Vulnerability"]].map(([k, to, c, label]) => {
              const n = (o.experiments as any[]).filter((e) => e.module === k).length;
              return (
                <Link key={k} to={to} className="rounded-md bg-ink-850 border border-ink-700 hover:border-ink-500 p-3">
                  <div className="h-1 w-8 rounded mb-2" style={{ background: c }} />
                  <div className="font-medium">{label}</div>
                  <div className="text-2xs text-fg-dim">{n ? `${n} experiments stored` : "not yet run"}</div>
                </Link>
              );
            })}
          </div>
        </Section>
      </div>
    </div>
  );
}
