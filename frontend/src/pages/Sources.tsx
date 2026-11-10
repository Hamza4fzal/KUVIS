import { useState } from "react";
import { useSources } from "@/services/api";
import { ErrorState, Loading, PageHeader } from "@/components/ui";

const STATUS: Record<string, [string, string]> = {
  acquired: ["Acquired", "#6bbf8a"],
  alternative_selected: ["Verified · extension pending / alternative used", "#5eb1bf"],
  requires_authentication: ["Requires authentication", "#d9b44a"],
  requires_manual_request: ["Requires manual request", "#d9b44a"],
  requires_payment: ["Requires payment", "#d65b72"],
  unavailable: ["Temporarily unavailable", "#6b788b"],
  failed: ["Failed", "#d65b72"],
};

export default function Sources() {
  const { data, isLoading, error } = useSources();
  const [q, setQ] = useState("");
  const rows = (data ?? []).filter((d) => !q || `${d.title} ${d.provider} ${d.key}`.toLowerCase().includes(q.toLowerCase()));
  return (
    <div className="h-full overflow-y-auto scroll-thin">
      <div className="max-w-[1300px] mx-auto p-6 space-y-4">
        <PageHeader kicker="Data sources" title="Dataset catalogue and provenance">
          Generated from the pipeline's provenance registry: a dataset is listed as acquired only when its files exist and were checksummed.
          Investigated sources that were not acquired are listed with the verified reason.
        </PageHeader>
        <input className="input w-80" placeholder="Search datasets or providers" value={q} onChange={(e) => setQ(e.target.value)} />
        {isLoading && <Loading />}
        {error && <ErrorState error={error} />}
        <div className="space-y-3">
          {rows.map((d) => {
            const [label, color] = STATUS[d.status] ?? [d.status, "#6b788b"];
            return (
              <article key={d.key} className="panel p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h3 className="font-semibold">{d.title}</h3>
                    <div className="text-xs text-fg-muted">{d.provider} · <a className="link" href={d.url} target="_blank" rel="noreferrer">{d.url}</a></div>
                  </div>
                  <span className="chip shrink-0" style={{ color, borderColor: color + "66" }}>{label}</span>
                </div>
                <dl className="grid grid-cols-[150px_1fr] gap-x-4 gap-y-1 text-xs mt-3">
                  {d.method && (<><dt className="text-fg-dim">Method</dt><dd>{d.method}</dd></>)}
                  {d.spatial_resolution && (<><dt className="text-fg-dim">Spatial resolution</dt><dd>{d.spatial_resolution}</dd></>)}
                  {d.temporal_coverage && (<><dt className="text-fg-dim">Temporal coverage</dt><dd>{d.temporal_coverage}</dd></>)}
                  {d.crs && (<><dt className="text-fg-dim">CRS</dt><dd className="num">{d.crs}</dd></>)}
                  {d.license && (<><dt className="text-fg-dim">License</dt><dd>{d.license}</dd></>)}
                  {d.variables && (<><dt className="text-fg-dim">Variables</dt><dd>{Array.isArray(d.variables) ? d.variables.join(", ") : String(d.variables)}</dd></>)}
                  <dt className="text-fg-dim">Accessed</dt><dd className="num">{d.accessed_utc ? new Date(d.accessed_utc).toLocaleString() : "—"}</dd>
                  {d.limitations && (<><dt className="text-fg-dim">Limitations</dt><dd className="text-fg-muted">{d.limitations}</dd></>)}
                  {d.files && d.files.length > 0 && (<><dt className="text-fg-dim">Files</dt><dd className="num text-2xs text-fg-muted">{d.files.map((f) => `${f.path} (${(f.bytes / 1e6).toFixed(1)} MB)`).join(" · ")}</dd></>)}
                </dl>
              </article>
            );
          })}
        </div>
      </div>
    </div>
  );
}
