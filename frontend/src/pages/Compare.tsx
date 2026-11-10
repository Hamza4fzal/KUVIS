import { useState } from "react";
import { Link } from "react-router-dom";
import { Bar as RBar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useCompare } from "@/services/api";
import { useMapStore } from "@/store/mapStore";
import { CATEGORICAL, fmt } from "@/maps/palettes";
import { Empty, ErrorState, EvidenceChip, Loading, PageHeader, Section } from "@/components/ui";

const AX = { stroke: "#3b4a62", tick: { fill: "#6b788b", fontSize: 10 } };

export default function Compare() {
  const { compareSet, toggleCompare, clearCompare } = useMapStore();
  const [input, setInput] = useState("");
  const { data, isLoading, error } = useCompare(compareSet);
  const feats: string[] = data?.features ?? [];
  const cells: any[] = data?.cells ?? [];
  const chart = feats.map((f) => {
    const row: any = { feature: cells[0]?.values.find((v: any) => v.feature === f)?.label ?? f };
    cells.forEach((c) => { row[c.grid_id] = c.values.find((v: any) => v.feature === f)?.city_percentile ?? null; });
    return row;
  });
  return (
    <div className="h-full overflow-y-auto scroll-thin">
      <div className="max-w-[1300px] mx-auto p-6 space-y-4">
        <PageHeader kicker="Compare locations" title="Side-by-side cell comparison">
          Add cells by Shift-clicking on the Explore map or by entering grid IDs. Values are compared on identical spatial support (500 m cells) and periods;
          the chart shows each value's percentile among Karachi land cells so that different units are comparable.
        </PageHeader>
        <div className="flex items-center gap-2">
          <input className="input w-56" placeholder="KHI_000123" value={input} onChange={(e) => setInput(e.target.value.toUpperCase())}
            onKeyDown={(e) => { if (e.key === "Enter" && /^KHI_\d{6}$/.test(input)) { toggleCompare(input); setInput(""); } }} />
          <button className="btn" onClick={() => { if (/^KHI_\d{6}$/.test(input)) { toggleCompare(input); setInput(""); } }}>Add</button>
          {compareSet.map((id, i) => (
            <span key={id} className="chip border-ink-600" style={{ color: CATEGORICAL[i] }}>
              {id} <button onClick={() => toggleCompare(id)} className="ml-1 text-fg-dim">✕</button>
            </span>
          ))}
          {compareSet.length > 0 && <button className="btn" onClick={clearCompare}>Clear</button>}
        </div>
        {compareSet.length < 2 && <Empty>Select at least two cells. <Link className="link" to="/explore">Open the map →</Link></Empty>}
        {isLoading && <Loading />}
        {error && <ErrorState error={error} />}
        {cells.length >= 2 && (
          <>
            <Section title="Percentile among Karachi land cells">
              <div className="h-80">
                <ResponsiveContainer>
                  <BarChart data={chart} margin={{ left: 0, right: 10, bottom: 40 }}>
                    <CartesianGrid stroke="#1f2a3c" />
                    <XAxis dataKey="feature" {...AX} angle={-25} textAnchor="end" interval={0} height={70} />
                    <YAxis {...AX} domain={[0, 100]} />
                    <Tooltip contentStyle={{ background: "#0e131b", border: "1px solid #2b384d", fontSize: 11 }} formatter={(v: number) => `P${fmt(v, 0)}`} />
                    <Legend wrapperStyle={{ fontSize: 10 }} />
                    {cells.map((c, i) => <RBar key={c.grid_id} dataKey={c.grid_id} fill={CATEGORICAL[i]} />)}
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Section>
            <Section title="Values">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-2xs text-fg-dim">
                    <th className="text-left py-1">Indicator</th><th className="text-left">Evidence</th>
                    {cells.map((c, i) => <th key={c.grid_id} className="text-right num" style={{ color: CATEGORICAL[i] }}>{c.grid_id}<div className="text-fg-dim font-normal">{c.subdivision}</div></th>)}
                    <th className="text-right text-fg-dim">city median</th>
                  </tr>
                </thead>
                <tbody>
                  {feats.map((f) => {
                    const ref = cells[0].values.find((v: any) => v.feature === f);
                    if (!ref) return null;
                    return (
                      <tr key={f} className="border-t border-ink-800">
                        <td className="py-1.5">{ref.label} <span className="text-2xs text-fg-dim">{ref.unit}</span></td>
                        <td><EvidenceChip kind={ref.kind} /></td>
                        {cells.map((c) => <td key={c.grid_id} className="text-right num">{fmt(c.values.find((v: any) => v.feature === f)?.value)}</td>)}
                        <td className="text-right num text-fg-dim">{fmt(ref.city_median)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </Section>
          </>
        )}
      </div>
    </div>
  );
}
