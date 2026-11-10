import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useEffect, useRef, useState } from "react";
import { api } from "@/services/api";
import { useMapStore } from "@/store/mapStore";

const NAV: { to: string; label: string; color?: string; group?: string }[] = [
  { to: "/", label: "Intelligence Overview", group: "Platform" },
  { to: "/explore", label: "Explore Karachi" },
  { to: "/flood", label: "Flood Intelligence", color: "#4f8fd9", group: "Modules" },
  { to: "/heat", label: "Heat Intelligence", color: "#e8774a" },
  { to: "/urbanization", label: "Urbanization Intelligence", color: "#c9a46b" },
  { to: "/infrastructure", label: "Infrastructure Intelligence", color: "#9a8fd1" },
  { to: "/vulnerability", label: "Vulnerability Intelligence", color: "#d65b72" },
  { to: "/discoveries", label: "Discovered Patterns", group: "Analysis" },
  { to: "/history", label: "Historical Analysis" },
  { to: "/compare", label: "Compare Locations" },
  { to: "/methodology", label: "Research & Methodology", group: "Transparency" },
  { to: "/sources", label: "Data Sources" },
];

function Search() {
  const [q, setQ] = useState("");
  const [res, setRes] = useState<any[]>([]);
  const [open, setOpen] = useState(false);
  const nav = useNavigate();
  const { select, setFlyTo } = useMapStore();
  const t = useRef<number>();
  useEffect(() => {
    window.clearTimeout(t.current);
    if (!q.trim()) return setRes([]);
    t.current = window.setTimeout(() => {
      api<any[]>(`/areas/search?q=${encodeURIComponent(q)}`).then(setRes).catch(() => setRes([]));
    }, 200);
  }, [q]);
  const choose = (r: any) => {
    nav("/explore");
    if (r.type === "cell") {
      select(r.grid_id);
      setFlyTo({ lon: r.lon, lat: r.lat, zoom: 13.5 });
    } else setFlyTo({ lon: r.lon, lat: r.lat, bbox: r.bbox });
    setOpen(false);
    setQ("");
  };
  return (
    <div className="relative w-[420px]">
      <input
        className="input w-full pl-8"
        placeholder="Search subdivision, grid id (KHI_000123) or “lat, lon”"
        value={q}
        onChange={(e) => { setQ(e.target.value); setOpen(true); }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        onKeyDown={(e) => e.key === "Enter" && res[0] && choose(res[0])}
      />
      <svg className="absolute left-2.5 top-2.5 h-4 w-4 text-fg-dim" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="9" cy="9" r="6" /><path d="M14 14l4 4" /></svg>
      {open && res.length > 0 && (
        <div className="absolute z-50 mt-1 w-full panel py-1 shadow-xl">
          {res.map((r, i) => (
            <button key={i} className="w-full text-left px-3 py-1.5 hover:bg-ink-800 text-sm flex justify-between" onMouseDown={() => choose(r)}>
              <span>{r.label}</span>
              <span className="text-2xs text-fg-dim uppercase">{r.type}{r.subdivision ? ` · ${r.subdivision}` : ""}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export default function AppLayout() {
  return (
    <div className="h-full flex">
      <aside className="w-60 shrink-0 bg-ink-900 border-r border-ink-700/70 flex flex-col">
        <div className="px-4 py-4 border-b border-ink-700/70">
          <div className="flex items-center gap-2">
            <svg viewBox="0 0 32 32" className="h-7 w-7"><rect width="32" height="32" rx="6" fill="#121925" /><path d="M7 7h6v6H7zM14 14h6v6h-6zM21 7h4v4h-4zM7 21h4v4H7zM21 21h4v4h-4z" fill="#5eb1bf" /></svg>
            <div>
              <div className="font-semibold tracking-wide">KUVIS</div>
              <div className="text-2xs text-fg-dim leading-tight">Karachi Urban Vulnerability<br />Intelligence System</div>
            </div>
          </div>
        </div>
        <nav className="flex-1 overflow-y-auto scroll-thin py-2">
          {NAV.map((n) => (
            <div key={n.to}>
              {n.group && <div className="panel-h px-4 pt-4 pb-1.5">{n.group}</div>}
              <NavLink
                to={n.to}
                end={n.to === "/"}
                className={({ isActive }) =>
                  `flex items-center gap-2 mx-2 px-2.5 py-1.5 rounded-md text-sm transition-colors ${isActive ? "bg-ink-800 text-fg" : "text-fg-muted hover:text-fg hover:bg-ink-850"}`
                }
              >
                <span className="h-1.5 w-1.5 rounded-full" style={{ background: n.color ?? "#3b4a62" }} />
                {n.label}
              </NavLink>
            </div>
          ))}
        </nav>
        <div className="px-4 py-3 border-t border-ink-700/70 text-2xs text-fg-dim leading-relaxed">
          Historical satellite & open data — not real-time. Analytical outputs are not an official risk assessment.
        </div>
      </aside>
      <div className="flex-1 flex flex-col min-w-0">
        <header className="h-14 shrink-0 border-b border-ink-700/70 bg-ink-900/60 flex items-center justify-between px-5 gap-4">
          <Search />
          <div className="text-2xs text-fg-dim">Data mining · Geospatial intelligence · Karachi, Sindh</div>
        </header>
        <main className="flex-1 min-h-0 relative">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
