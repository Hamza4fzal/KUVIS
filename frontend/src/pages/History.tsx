import { useEffect, useRef, useState } from "react";
import type { Map as MLMap } from "maplibre-gl";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis, Bar as RBar, BarChart } from "recharts";
import MapView from "@/maps/MapView";
import { Legend as MapLegend } from "@/maps/LayerPanel";
import { useEpochHistory, useLayers, useRainHistory } from "@/services/api";
import { Empty, PageHeader, Section } from "@/components/ui";
import { fmt } from "@/maps/palettes";

const AX = { stroke: "#3b4a62", tick: { fill: "#6b788b", fontSize: 10 } };
const TT = { contentStyle: { background: "#0e131b", border: "1px solid #2b384d", fontSize: 11 }, labelStyle: { color: "#9aa7b8" } };

const VARIABLES = [
  { key: "lst_rel", label: "Relative surface heat", layer: (e: string) => `hist_lst_rel_${e}` },
  { key: "ndvi", label: "Landsat NDVI", layer: (e: string) => `hist_ls_ndvi_${e}` },
];

export default function History() {
  const { data: layers } = useLayers();
  const { data: epochs } = useEpochHistory();
  const { data: rain } = useRainHistory();
  const [variable, setVariable] = useState(VARIABLES[0]);
  const available = (layers ?? []).filter((l) => l.group === "History");
  const epochList = Array.from(new Set(available.map((l) => l.id.split("_").pop()!))).sort();
  const [a, setA] = useState<string>("");
  const [b, setB] = useState<string>("");
  const [mode, setMode] = useState<"side" | "swipe">("side");
  const [swipe, setSwipe] = useState(50);
  useEffect(() => {
    if (epochList.length >= 2 && !a) { setA(epochList[0]); setB(epochList[epochList.length - 1]); }
  }, [epochList, a]);
  const maps = useRef<MLMap[]>([]);
  const syncing = useRef(false);
  const register = (m: MLMap) => {
    maps.current.push(m);
    m.on("move", () => {
      if (syncing.current) return;
      syncing.current = true;
      maps.current.filter((o) => o !== m).forEach((o) => o.jumpTo({ center: m.getCenter(), zoom: m.getZoom() }));
      syncing.current = false;
    });
  };
  const layerA = available.find((l) => l.id === variable.layer(a));
  const layerB = available.find((l) => l.id === variable.layer(b));
  return (
    <div className="h-full overflow-y-auto scroll-thin">
      <div className="max-w-[1500px] mx-auto p-6 space-y-4">
        <PageHeader kicker="Historical analysis" title="How Karachi's surface has changed">
          Landsat epochs are pre-monsoon (Apr–Jun) composites. Absolute LST depends on weather on the acquisition days, so maps compare
          <i> relative</i> LST (cell minus the city-wide median of the same epoch). Only epochs with processed observations appear.
        </PageHeader>
        {epochList.length < 2 ? <Empty>Fewer than two processed Landsat epochs are in the database.</Empty> : (
          <Section title="Map comparison" right={
            <div className="flex items-center gap-2">
              {VARIABLES.map((v) => <button key={v.key} className={`chip ${variable.key === v.key ? "border-accent text-accent" : "border-ink-600 text-fg-muted"}`} onClick={() => setVariable(v)}>{v.label}</button>)}
              <span className="w-px h-4 bg-ink-600" />
              <select className="input py-0.5 text-xs" value={a} onChange={(e) => setA(e.target.value)}>{epochList.map((e) => <option key={e}>{e}</option>)}</select>
              <span className="text-fg-dim text-xs">vs</span>
              <select className="input py-0.5 text-xs" value={b} onChange={(e) => setB(e.target.value)}>{epochList.map((e) => <option key={e}>{e}</option>)}</select>
              <button className="btn" onClick={() => { maps.current = []; setMode(mode === "side" ? "swipe" : "side"); }}>{mode === "side" ? "Swipe view" : "Side by side"}</button>
            </div>
          }>
            {mode === "side" ? (
              <div className="grid grid-cols-2 gap-2 h-[520px]" key={`side-${variable.key}-${a}-${b}`}>
                {[[a, layerA], [b, layerB]].map(([ep, l]) => (
                  <div key={ep as string} className="relative rounded-md overflow-hidden border border-ink-700">
                    {l ? <MapView layerIds={[(l as any).id]} onMapReady={register} showHover /> : <Empty>No {variable.label} layer for {ep as string}</Empty>}
                    <div className="absolute top-2 left-2 panel px-2.5 py-1.5 w-56">
                      <div className="text-sm font-medium">{variable.label} · {ep as string}</div>
                      {l && <MapLegend layer={l as any} />}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="relative h-[560px] rounded-md overflow-hidden border border-ink-700" key={`swipe-${variable.key}-${a}-${b}`}>
                {layerB && <MapView layerIds={[layerB.id]} onMapReady={register} />}
                <div className="absolute inset-0" style={{ clipPath: `inset(0 ${100 - swipe}% 0 0)` }}>
                  {layerA && <MapView layerIds={[layerA.id]} onMapReady={register} interactive={false} />}
                </div>
                <div className="absolute top-0 bottom-0 w-0.5 bg-white/80 pointer-events-none" style={{ left: `${swipe}%` }} />
                <input type="range" min={0} max={100} value={swipe} onChange={(e) => setSwipe(Number(e.target.value))}
                  className="absolute bottom-4 left-1/2 -translate-x-1/2 w-1/2 accent-[#5eb1bf]" />
                <div className="absolute top-2 left-2 panel px-2 py-1 text-xs">◀ {a}</div>
                <div className="absolute top-2 right-14 panel px-2 py-1 text-xs">{b} ▶</div>
              </div>
            )}
          </Section>
        )}
        <div className="grid grid-cols-2 gap-4">
          <Section title="City-wide Landsat statistics per epoch (land cells)">
            {epochs?.length ? (
              <div className="h-56">
                <ResponsiveContainer>
                  <LineChart data={epochs} margin={{ left: -10, right: 10 }}>
                    <CartesianGrid stroke="#1f2a3c" />
                    <XAxis dataKey="epoch" {...AX} />
                    <YAxis yAxisId="l" {...AX} unit="°" />
                    <YAxis yAxisId="r" orientation="right" {...AX} />
                    <Tooltip {...TT} formatter={(v: number) => fmt(v, 3)} />
                    <Legend wrapperStyle={{ fontSize: 10 }} />
                    <Line yAxisId="l" dataKey="lst_median" name="median LST (°C)" stroke="#e8774a" dot />
                    <Line yAxisId="r" dataKey="ndvi_median" name="median NDVI" stroke="#6bbf8a" dot />
                    <Line yAxisId="r" dataKey="ndbi_median" name="median NDBI" stroke="#c9a46b" dot />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            ) : <Empty>No epoch statistics.</Empty>}
            <div className="text-2xs text-fg-dim mt-2">Median LST differences between epochs mix real change with acquisition-day weather; see relative-LST maps above.</div>
          </Section>
          <Section title="Rainfall over Karachi — CHIRPS v3 (mean of native ≈5.5 km pixels)">
            {rain?.length ? (
              <div className="h-56">
                <ResponsiveContainer>
                  <BarChart data={rain} margin={{ left: -10, right: 10 }}>
                    <CartesianGrid stroke="#1f2a3c" />
                    <XAxis dataKey="year" {...AX} interval={4} />
                    <YAxis {...AX} unit=" mm" />
                    <Tooltip {...TT} formatter={(v: number) => fmt(v, 0) + " mm"} />
                    <Legend wrapperStyle={{ fontSize: 10 }} />
                    <RBar dataKey="jjas_mm" name="Jun–Sep (monsoon)" fill="#4f8fd9" />
                    <RBar dataKey="annual_mm" name="annual" fill="#2b384d" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : <Empty>No rainfall series loaded.</Empty>}
            <div className="text-2xs text-fg-dim mt-2">Satellite–gauge blended estimate; not a station record and not resolvable to neighbourhoods.</div>
          </Section>
        </div>
      </div>
    </div>
  );
}
