"""Generate research/RESULTS.md from machine-written experiment records and discoveries.

Every number in the output is copied from research/experiments/*.json or datasets/processed/mining/discoveries.json.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from kuvis.mining.experiment import load_all  # noqa: E402


def f(v, d=3):
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:.{d}f}"
    return str(v)


def main():
    exps = {e["experiment_id"]: e for e in load_all()}
    L = [f"# KUVIS — Results\n\n_Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC by `scripts/generate_results.py` "
         "from `research/experiments/*.json`. Do not edit by hand._\n"]
    for mod in ["heat", "flood", "urban", "infra", "vulnerability"]:
        es = [e for e in exps.values() if e["module"] == mod]
        if not es:
            continue
        L.append(f"\n## Module: {mod}\n")
        for e in es:
            m = e["metrics"]
            L.append(f"\n### {e['algorithm']} — `{e['experiment_id']}`\n\n*{e['purpose']}* · n = {e['n_samples']:,} · "
                     f"run {e['run_utc']} · code {e['code_version']}\n")
            if "chosen" in m:
                c = m["chosen"]
                L.append(f"\n- Selected: {e['parameters'].get('selection')}\n- Silhouette {f(c['silhouette'])}, "
                         f"Davies–Bouldin {f(c['davies_bouldin'])}, Calinski–Harabasz {f(c['calinski_harabasz'], 0)}\n")
                L.append("\n| K | inertia | silhouette | Davies–Bouldin |\n|---|---|---|---|\n")
                for s in m["sweep"]:
                    L.append(f"| {s['k']} | {f(s['inertia'], 0)} | {f(s['silhouette'])} | {f(s['davies_bouldin'])} |\n")
                profs = e["results"].get("profiles", [])
                if profs:
                    L.append("\n| cluster | cells | generated name |\n|---|---|---|\n")
                    for p in profs:
                        L.append(f"| {p['cluster']} | {p['n_cells']} | {p['name']} |\n")
            for key in ("n_clusters", "noise_share", "ari_vs_kmeans_non_noise", "n_hotspots", "n_hot", "n_cold", "n_hot_fdr",
                        "n_flagged", "n_warmer", "n_cooler", "n_rules", "base_rate", "ols_r2", "balanced_accuracy", "roc_auc",
                        "precision", "recall", "f1", "best_depth", "n_scored", "top_quintile_stable_share",
                        "median_rank_range_width", "median_persistence_flagged", "median_persistence_unflagged"):
                if key in m and not isinstance(m[key], (list, dict)):
                    L.append(f"- {key.replace('_', ' ')}: **{f(m[key])}**\n")
            if "moran" in m:
                L.append(f"- Moran's I = **{f(m['moran']['I'])}** (pseudo-p {f(m['moran']['p_sim'])})\n")
            if "if_vs_lof" in m:
                L.append(f"- Isolation Forest vs LOF Jaccard = {f(m['if_vs_lof']['jaccard'])}\n")
            if "spearman" in m:
                L.append("\n| feature | Spearman ρ | n |\n|---|---|---|\n")
                for s in m["spearman"]:
                    L.append(f"| {s['feature']} | {f(s['spearman_rho'])} | {s['n']} |\n")
            if "ols_std_coefficients" in m:
                L.append("\n| feature | std. β | 95 % CI |\n|---|---|---|\n")
                for c in m["ols_std_coefficients"]:
                    L.append(f"| {c['feature']} | {f(c['std_beta'])} | {f(c['ci_low'])} – {f(c['ci_high'])} |\n")
            if "label_threshold_sensitivity" in m:
                L.append("\n| label threshold | balanced acc. | ROC-AUC | positive rate |\n|---|---|---|---|\n")
                for t, s in m["label_threshold_sensitivity"].items():
                    L.append(f"| {t} | {f(s['balanced_accuracy'])} | {f(s['roc_auc'])} | {f(s['positive_rate'])} |\n")
            if "top_rules" in e["results"]:
                L.append("\n| rule | support | confidence | lift |\n|---|---|---|---|\n")
                for r in e["results"]["top_rules"][:8]:
                    L.append(f"| {' ∧ '.join(r['antecedents'])} ⇒ {r['consequent']} | {f(r['support'])} | {f(r['confidence'])} | {f(r['lift'], 2)} |\n")
            if "epochs" in m:
                L.append("\n| epoch | cells | median LST °C | built − (rel.) | bare (rel.) | vegetated (rel.) |\n|---|---|---|---|---|---|\n")
                for r in m["epochs"]:
                    L.append(f"| {r['epoch']} | {r['n_cells']} | {f(r['lst_median'], 2)} | {f(r['rel_built_dominant'], 2)} | "
                             f"{f(r['rel_bare_dominant'], 2)} | {f(r['rel_veg_dominant'], 2)} |\n")
            if e.get("limitations"):
                L.append("\n_Limitations:_ " + " ".join(e["limitations"]) + "\n")
    dp = ROOT / "datasets" / "processed" / "mining" / "discoveries.json"
    if dp.exists():
        ds = json.loads(dp.read_text(encoding="utf-8"))
        L.append(f"\n## Discovered patterns ({len(ds)})\n")
        for d in sorted(ds, key=lambda d: -(d.get("strength") or 0)):
            L.append(f"\n**{d['title']}** — _{d['category']}, {d['algorithm']}, {d['period']}_  \n{d['description']}\n")
    out = ROOT / "research" / "RESULTS.md"
    out.write_text("".join(L), encoding="utf-8")
    print(f"wrote {out} ({len(exps)} experiments)")


if __name__ == "__main__":
    main()
