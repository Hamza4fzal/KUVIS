import type { ExpressionSpecification } from "maplibre-gl";
import type { Layer } from "@/types/api";

// Perceptually ordered ramps (6 stops each), chosen for legibility on a dark basemap.
export const RAMPS: Record<string, string[]> = {
  heat: ["#2b1a4a", "#5b2a7a", "#a33d6f", "#df5f45", "#f59a3b", "#fbe28a"],
  green: ["#2a2216", "#5a4a26", "#8a8a3a", "#6aa64a", "#3fae6a", "#9be3a6"],
  built: ["#1b2230", "#34405a", "#6b6a7a", "#a68d6a", "#d6b27a", "#f3e3b8"],
  purple: ["#1a1b33", "#2e2e5e", "#51468a", "#7d5aa8", "#b072b8", "#eaa6d6"],
  terrain: ["#18324a", "#2f5f6a", "#5a8a6a", "#a6a86a", "#c99a6a", "#ece0cf"],
  grey: ["#1e2633", "#334055", "#526178", "#7c8ba3", "#aab7cc", "#e1e8f2"],
  blue: ["#141f33", "#1f3a66", "#2a5d99", "#3f86c4", "#6fb3e0", "#bfe3f7"],
  uvi: ["#1b2333", "#2f3e57", "#6a4a73", "#a8516f", "#e0645e", "#f8b46a"],
  diverging: ["#2c6fb5", "#6aa6d9", "#b9d6ee", "#f2d0b8", "#e58a63", "#c0392b"],
  diverging_green: ["#8c4a20", "#c88a4a", "#ecd2a6", "#c9e4b4", "#6fb874", "#227a44"],
};

export const CATEGORICAL = ["#5eb1bf", "#e8774a", "#9a8fd1", "#c9a46b", "#6bbf8a", "#d65b72", "#4f8fd9", "#d9b44a",
  "#8fb3a0", "#b5739d", "#7f9fbf", "#c4c46a"];

export const NOISE = "#3b4a62";

function dedupe(stops: number[]): number[] {
  const out: number[] = [];
  for (const s of stops) if (!out.length || s > out[out.length - 1] + 1e-9) out.push(s);
  return out;
}

/** MapLibre colour expression for a layer, using the data-derived legend (quantile breaks). */
export function colorExpression(layer: Layer): ExpressionSpecification {
  const p: ExpressionSpecification = ["get", layer.prop];
  const lg = layer.legend;
  if (layer.scale === "categorical") {
    const cats = lg.categories ?? [];
    const expr: unknown[] = ["match", ["to-number", p]];
    for (const c of cats) {
      expr.push(c.value, categoricalColor(layer, c.value));
    }
    expr.push(NOISE);
    return expr as ExpressionSpecification;
  }
  const ramp = RAMPS[layer.palette ?? "grey"] ?? RAMPS.grey;
  if (layer.scale === "diverging") {
    const m = Math.max(Math.abs(lg.quantiles[0]), Math.abs(lg.quantiles[lg.quantiles.length - 1])) || 1;
    const stops = [-m, -m * 0.5, -m * 0.15, m * 0.15, m * 0.5, m];
    return ["interpolate", ["linear"], p, ...stops.flatMap((s, i) => [s, ramp[i]])] as ExpressionSpecification;
  }
  const q = dedupe(lg.quantiles);
  if (q.length < 2) return ramp[3] as unknown as ExpressionSpecification;
  const n = q.length;
  return ["interpolate", ["linear"], p, ...q.flatMap((s, i) => [s, ramp[Math.round((i * (ramp.length - 1)) / (n - 1))]])] as ExpressionSpecification;
}

export function categoricalColor(layer: Layer, v: number): string {
  if (layer.prop === "gi_class_code" || layer.prop === "if_flag_code") {
    return v > 0 ? "#e2553f" : v < 0 ? "#3f86c4" : "rgba(0,0,0,0)";
  }
  if (v < 0) return NOISE;
  return CATEGORICAL[v % CATEGORICAL.length];
}

export function legendStops(layer: Layer): { color: string; label: string }[] {
  const lg = layer.legend;
  if (layer.scale === "categorical") {
    return (lg.categories ?? [])
      .filter((c) => !(layer.prop.endsWith("_code") && c.value === 0))
      .map((c) => ({ color: categoricalColor(layer, c.value), label: c.label ?? (c.value < 0 ? "Noise / none" : `Group ${c.value}`) }));
  }
  const ramp = RAMPS[layer.palette ?? "grey"] ?? RAMPS.grey;
  if (layer.scale === "diverging") {
    const m = Math.max(Math.abs(lg.quantiles[0]), Math.abs(lg.quantiles[lg.quantiles.length - 1])) || 1;
    return [-m, -m * 0.5, 0, m * 0.5, m].map((s, i) => ({ color: ramp[[0, 1, 2, 4, 5][i]], label: fmt(s) }));
  }
  return lg.quantiles.map((s, i) => ({ color: ramp[i] ?? ramp[ramp.length - 1], label: fmt(s) }));
}

export function fmt(v: number | null | undefined, digits?: number): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  const a = Math.abs(v);
  const d = digits ?? (a >= 1000 ? 0 : a >= 100 ? 0 : a >= 10 ? 1 : a >= 1 ? 2 : 3);
  return v.toLocaleString("en-US", { maximumFractionDigits: d, minimumFractionDigits: 0 });
}
