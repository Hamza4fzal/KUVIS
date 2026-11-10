import { jsPDF } from "jspdf";
import html2canvas from "html2canvas";
import type { Report } from "@/types/api";
import { fmt } from "@/maps/palettes";

/** Structured PDF: identity, map snapshot, explanation, key values, mining findings, history, sources, limitations. */
export async function exportReportPdf(r: Report, body: HTMLElement | null) {
  const pdf = new jsPDF({ unit: "mm", format: "a4" });
  const W = 210, M = 14;
  let y = 16;
  const line = (txt: string, size = 10, color: [number, number, number] = [30, 36, 46], bold = false) => {
    pdf.setFont("helvetica", bold ? "bold" : "normal");
    pdf.setFontSize(size);
    pdf.setTextColor(...color);
    const lines = pdf.splitTextToSize(txt, W - 2 * M);
    for (const l of lines) {
      if (y > 282) { pdf.addPage(); y = 16; }
      pdf.text(l, M, y);
      y += size * 0.45;
    }
    y += 1.2;
  };
  pdf.setFillColor(14, 19, 27);
  pdf.rect(0, 0, W, 26, "F");
  pdf.setTextColor(94, 177, 191); pdf.setFontSize(9); pdf.text("KUVIS — Karachi Urban Vulnerability Intelligence System", M, 10);
  pdf.setTextColor(230, 235, 242); pdf.setFontSize(16); pdf.setFont("helvetica", "bold"); pdf.text(`Location intelligence report · ${r.grid_id}`, M, 19);
  y = 34;
  line(`Generated ${new Date().toISOString().slice(0, 16).replace("T", " ")} UTC from stored analytical results. Subdivision: ${r.identity.subdivision ?? "—"} · ` +
    `Centroid ${fmt(r.identity.lat, 4)}°N ${fmt(r.identity.lon, 4)}°E · 500 m × 500 m cell · data quality ${fmt(r.identity.data_quality_score, 2)}`, 9, [90, 100, 115]);

  const canvas = document.querySelector<HTMLCanvasElement>(".maplibregl-canvas");
  if (canvas) {
    try {
      const img = canvas.toDataURL("image/jpeg", 0.85);
      const h = ((W - 2 * M) * canvas.height) / canvas.width;
      const hh = Math.min(h, 90);
      pdf.addImage(img, "JPEG", M, y, ((W - 2 * M) * hh) / h, hh);
      y += hh + 3;
      line("Map snapshot at export time (selected cell outlined in white).", 8, [110, 120, 135]);
    } catch { /* tainted canvas — skip snapshot */ }
  }
  line("Explanation", 12, [20, 24, 32], true);
  r.explanation.forEach((e) => line(`[${e.evidence}] ${e.text}`, 9.5));
  line("Data-mining findings", 12, [20, 24, 32], true);
  r.mining.clusters.forEach((c) => line(`[cluster] ${c.algorithm} (${c.experiment_id}): group ${c.cluster}${c.name ? ` — ${c.name}` : ""}`, 9.5));
  r.mining.hotspots.forEach((h) => line(`[statistic] ${h.algorithm}: ${h.gi_class} (z=${fmt(h.gi_z, 2)}, p=${fmt(h.gi_p, 3)})`, 9.5));
  r.mining.anomalies.forEach((a) => line(`[anomaly] ${a.algorithm}: ${a.is_anomaly ? `anomalous, ${a.direction}` : "not anomalous"} (score ${fmt(a.score, 3)})`, 9.5));
  r.mining.association_rules.slice(0, 5).forEach((ru) => line(`[association] ${ru.antecedents.join(" & ")} => ${ru.consequent} (conf ${fmt(ru.confidence * 100, 0)} %, lift ${fmt(ru.lift, 2)})`, 9.5));
  r.mining.decision_tree.forEach((t) => line(`[model prediction] ${t.algorithm}: predicted ${t.predicted} (p=${fmt(t.probability, 2)}), observed ${t.observed}`, 9.5));
  if (r.vulnerability.score) {
    line("Composite vulnerability (not an official risk assessment)", 12, [20, 24, 32], true);
    const s = r.vulnerability.score;
    line(`UVI ${fmt(s.uvi, 2)} (${s.uvi_class}, P${fmt(s.uvi_rank_pct, 0)}; rank range under alternative weights P${fmt(s.rank_p05, 0)}–P${fmt(s.rank_p95, 0)}); evidence quality ${fmt(s.evidence_quality, 2)}`, 9.5);
    r.vulnerability.indicators.forEach((d) => line(`  ${d.dimension}: ${fmt(d.value, 2)} (${d.n_available}/${d.n_inputs} inputs)`, 9));
  }
  line("Environmental profile", 12, [20, 24, 32], true);
  r.profile.forEach((s) => {
    line(s.title, 10, [40, 46, 58], true);
    s.values.forEach((v) => {
      const val = typeof v.value === "number" ? fmt(v.value) : v.value ?? "—";
      const cmp = v.city_percentile != null ? ` · city P${fmt(v.city_percentile, 0)}` : "";
      line(`  ${v.label}: ${val} ${v.unit ?? ""}${cmp}  [${v.kind}; ${v.source}, ${v.period}]`, 8.5);
    });
  });
  const chart = body?.querySelector<HTMLElement>(".recharts-wrapper");
  if (chart) {
    try {
      const c = await html2canvas(chart, { backgroundColor: "#0e131b", scale: 2 });
      if (y > 220) { pdf.addPage(); y = 16; }
      line("Historical profile", 12, [20, 24, 32], true);
      const w = W - 2 * M, h = (w * c.height) / c.width;
      pdf.addImage(c.toDataURL("image/png"), "PNG", M, y, w, h);
      y += h + 4;
    } catch { /* ignore chart capture failure */ }
  }
  line("Limitations", 12, [20, 24, 32], true);
  r.limitations.forEach((l) => line(`• ${l}`, 9));
  line("Sources", 12, [20, 24, 32], true);
  r.sources.forEach((s) => line(`• ${s.title} — ${s.provider}${s.license ? ` (${s.license})` : ""}. ${s.url}`, 8.5));
  pdf.save(`KUVIS_${r.grid_id}_report.pdf`);
}
