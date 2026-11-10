import { create } from "zustand";

export type Basemap = "dark" | "light" | "satellite";

interface MapState {
  activeLayers: string[]; // ordered, last = top
  opacity: Record<string, number>;
  basemap: Basemap;
  selected: string | null;
  compareSet: string[];
  flyTo: { lon: number; lat: number; zoom?: number; bbox?: number[] } | null;
  showSubdivisions: boolean;
  toggleLayer: (id: string, exclusive?: boolean) => void;
  setLayers: (ids: string[]) => void;
  setOpacity: (id: string, v: number) => void;
  setBasemap: (b: Basemap) => void;
  select: (id: string | null) => void;
  toggleCompare: (id: string) => void;
  clearCompare: () => void;
  setFlyTo: (f: MapState["flyTo"]) => void;
  setShowSubdivisions: (v: boolean) => void;
}

export const useMapStore = create<MapState>((set) => ({
  activeLayers: [],
  opacity: {},
  basemap: "dark",
  selected: null,
  compareSet: [],
  flyTo: null,
  showSubdivisions: true,
  toggleLayer: (id, exclusive) =>
    set((s) => {
      if (s.activeLayers.includes(id)) return { activeLayers: s.activeLayers.filter((l) => l !== id) };
      return { activeLayers: exclusive ? [id] : [...s.activeLayers, id].slice(-3) };
    }),
  setLayers: (ids) => set({ activeLayers: ids }),
  setOpacity: (id, v) => set((s) => ({ opacity: { ...s.opacity, [id]: v } })),
  setBasemap: (basemap) => set({ basemap }),
  select: (selected) => set({ selected }),
  toggleCompare: (id) =>
    set((s) => ({
      compareSet: s.compareSet.includes(id) ? s.compareSet.filter((x) => x !== id) : [...s.compareSet, id].slice(-6),
    })),
  clearCompare: () => set({ compareSet: [] }),
  setFlyTo: (flyTo) => set({ flyTo }),
  setShowSubdivisions: (showSubdivisions) => set({ showSubdivisions }),
}));
