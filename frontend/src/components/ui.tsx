import type { ReactNode } from "react";

export function EvidenceChip({ kind }: { kind: string | null | undefined }) {
  if (!kind) return null;
  const cls = `ev-${kind.split(" ")[0]}`;
  return <span className={`chip ${cls}`}>{kind}</span>;
}

export function Section({ title, right, children, className }: { title: string; right?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`panel p-4 ${className ?? ""}`}>
      <div className="flex items-center justify-between mb-3">
        <h3 className="panel-h">{title}</h3>
        {right}
      </div>
      {children}
    </section>
  );
}

export function Stat({ label, value, sub, accent }: { label: string; value: ReactNode; sub?: ReactNode; accent?: string }) {
  return (
    <div className="panel px-4 py-3">
      <div className="panel-h">{label}</div>
      <div className="mt-1 text-2xl font-semibold num" style={accent ? { color: accent } : undefined}>{value}</div>
      {sub && <div className="text-xs text-fg-muted mt-0.5">{sub}</div>}
    </div>
  );
}

export function Loading({ label = "Loading" }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 text-sm text-fg-muted p-4">
      <span className="h-3 w-3 rounded-full border-2 border-accent border-t-transparent animate-spin" />
      {label}…
    </div>
  );
}

export function ErrorState({ error }: { error: unknown }) {
  const msg = error instanceof Error ? error.message : String(error);
  return (
    <div className="panel p-4 border-vuln/40 text-sm">
      <div className="text-vuln font-medium">Could not load data</div>
      <div className="text-fg-muted mt-1">{msg}</div>
      <div className="text-fg-dim mt-2 text-xs">Is the API running? <code className="num">python -m uvicorn backend.app.main:app --port 8000</code></div>
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="text-sm text-fg-dim p-4 border border-dashed border-ink-700 rounded-lg">{children}</div>;
}

export function PageHeader({ title, kicker, children }: { title: string; kicker?: string; children?: ReactNode }) {
  return (
    <header className="mb-6">
      {kicker && <div className="panel-h text-accent">{kicker}</div>}
      <h1 className="text-2xl font-semibold mt-1">{title}</h1>
      {children && <div className="text-sm text-fg-muted mt-2 max-w-3xl leading-relaxed">{children}</div>}
    </header>
  );
}

export function Bar({ value, max = 1, color = "#5eb1bf" }: { value: number | null | undefined; max?: number; color?: string }) {
  const w = value === null || value === undefined ? 0 : Math.max(0, Math.min(1, value / max)) * 100;
  return (
    <div className="h-1.5 rounded bg-ink-700 overflow-hidden">
      <div className="h-full rounded" style={{ width: `${w}%`, background: color }} />
    </div>
  );
}
