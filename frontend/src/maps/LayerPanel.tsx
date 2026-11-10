import { useState } from "react";
import { useLayers } from "@/services/api";
import { useMapStore, type Basemap } from "@/store/mapStore";
import type { Layer } from "@/types/api";
import { EvidenceChip } from "@/components/ui";
import { legendStops } from "./palettes";

export function Legend({ layer }: { layer: Layer }) {
  const stops = legendStops(layer);
  if (layer.scale === "categorical") {
    return (
      <div className="grid grid-cols-1 gap-1 mt-2">
        {stops.slice(0, 12).map((s, i) => (
          <div key={i} className="flex items-center gap-2 text-2xs text-fg-muted">
            <span className="h-2.5 w-2.5 rounded-sm shrink-0" style={{ background: s.color }} />
            <span className="truncate">{s.label}</span>
          </div>
        ))}
      </div>
    );
  }
  return (
    <div className="mt-2">
      <div className="h-2 rounded" style={{ background: `linear-gradient(90deg, ${stops.map((s) => s.color).join(",")})` }} />
      <div className="flex justify-between text-2xs text-fg-dim num mt-1">
        {stops.filter((_, i) => i === 0 || i === Math.floor(stops.length / 2) || i === stops.length - 1).map((s, i) => <span key={i}>{s.label}</span>)}
      </div>
      <div className="text-2xs text-fg-dim mt-0.5">{layer.unit}{layer.scale === "sequential" ? " · 2nd–98th pct. range" : ""}</div>
    </div>
  );
}

export default function LayerPanel({ groups }: { groups?: string[] }) {
  const { data: layers, isLoading, error } = useLayers();
  const { activeLayers, toggleLayer, opacity, setOpacity, basemap, setBasemap, showSubdivisions, setShowSubdivisions } = useMapStore();
  const [open, setOpen] = useState<string | null>(null);
  const shown = (layers ?? []).filter((l) => !groups || groups.includes(l.group));
  const byGroup = shown.reduce<Record<string, Layer[]>>((a, l) => ((a[l.group] ??= []).push(l), a), {});
  return (
    <div className="panel w-[300px] max-h-full overflow-y-auto scroll-thin shadow-2xl">
      <div className="px-3 py-2.5 border-b border-ink-700 flex items-center justify-between">
        <span className="panel-h">Layers</span>
        <div className="flex gap-1">
          {(["dark", "light", "satellite"] as Basemap[]).map((b) => (
            <button key={b} onClick={() => setBasemap(b)} className={`chip ${basemap === b ? "border-accent text-accent" : "border-ink-600 text-fg-dim"}`}>{b}</button>
          ))}
        </div>
      </div>
      <label className="flex items-center gap-2 px-3 py-2 text-xs text-fg-muted border-b border-ink-800">
        <input type="checkbox" checked={showSubdivisions} onChange={(e) => setShowSubdivisions(e.target.checked)} className="accent-[#5eb1bf]" />
        Census-2017 subdivisions (geoBoundaries ADM3)
      </label>
      {isLoading && <div className="p-3 text-xs text-fg-dim">Loading layer catalogue…</div>}
      {error && <div className="p-3 text-xs text-vuln">Layer catalogue unavailable</div>}
      {Object.entries(byGroup).map(([g, ls]) => (
        <div key={g} className="py-1.5 border-b border-ink-800 last:border-0">
          <div className="panel-h px-3 py-1">{g}</div>
          {ls.map((l) => {
            const on = activeLayers.includes(l.id);
            return (
              <div key={l.id} className={`mx-1.5 rounded-md ${on ? "bg-ink-800/80" : ""}`}>
                <div className="flex items-center gap-2 px-1.5 py-1">
                  <input type="checkbox" checked={on} onChange={() => toggleLayer(l.id)} className="accent-[#5eb1bf]" />
                  <button className="flex-1 text-left text-sm leading-tight" onClick={() => setOpen(open === l.id ? null : l.id)}>{l.title}</button>
                  <EvidenceChip kind={l.kind} />
                </div>
                {(on || open === l.id) && (
                  <div className="px-2 pb-2 pl-7">
                    <p className="text-2xs text-fg-muted leading-relaxed">{l.description}</p>
                    <div className="text-2xs text-fg-dim mt-1">
                      {l.source} · {l.period} · coverage {(l.coverage * 100).toFixed(0)} % of cells
                    </div>
                    {on && (
                      <>
                        <Legend layer={l} />
                        <input type="range" min={0.1} max={1} step={0.05} value={opacity[l.id] ?? 0.78}
                          onChange={(e) => setOpacity(l.id, Number(e.target.value))} className="w-full mt-2 accent-[#5eb1bf]" />
                      </>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      ))}
      <div className="px-3 py-2 text-2xs text-fg-dim">Up to 3 layers at once. Shift-click cells to add them to Compare.</div>
    </div>
  );
}
