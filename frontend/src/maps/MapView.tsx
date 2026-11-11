import maplibregl, { type Map as MLMap, type MapGeoJSONFeature } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef, useState } from "react";
import { useBoundaries, useLayers, useMapMeta } from "@/services/api";
import { useMapStore, type Basemap } from "@/store/mapStore";
import type { Layer } from "@/types/api";
import { colorExpression, fmt } from "./palettes";

const KARACHI: [number, number] = [67.08, 24.95];

// Keyless Esri basemaps (CARTO raster tiles now require an API key). Canvas maps have a separate label layer.
const ESRI = (svc: string) => `https://server.arcgisonline.com/ArcGIS/rest/services/${svc}/MapServer/tile/{z}/{y}/{x}`;
const BASEMAPS: Record<Basemap, { tiles: string[]; labels?: string[]; attribution: string }> = {
  dark: {
    tiles: [ESRI("Canvas/World_Dark_Gray_Base")],
    labels: [ESRI("Canvas/World_Dark_Gray_Reference")],
    attribution: "Basemap © Esri, HERE, Garmin, © OpenStreetMap contributors",
  },
  light: {
    tiles: [ESRI("Canvas/World_Light_Gray_Base")],
    labels: [ESRI("Canvas/World_Light_Gray_Reference")],
    attribution: "Basemap © Esri, HERE, Garmin, © OpenStreetMap contributors",
  },
  satellite: {
    tiles: [ESRI("World_Imagery")],
    attribution: "Imagery © Esri, Maxar, Earthstar Geographics",
  },
};

interface Props {
  /** override the global active layers (e.g. historical side-by-side maps) */
  layerIds?: string[];
  interactive?: boolean;
  onMapReady?: (m: MLMap) => void;
  className?: string;
  showHover?: boolean;
  extraGeoJSON?: GeoJSON.FeatureCollection | null;
}

export default function MapView({ layerIds, interactive = true, onMapReady, className, showHover = true, extraGeoJSON }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MLMap | null>(null);
  const [ready, setReady] = useState(false);
  const { data: layers } = useLayers();
  const { data: bounds } = useBoundaries();
  const { data: meta } = useMapMeta();
  const store = useMapStore();
  const active = layerIds ?? store.activeLayers;
  const layerById = new Map((layers ?? []).map((l) => [l.id, l] as const));
  const activeRef = useRef<Layer[]>([]);
  activeRef.current = active.map((id) => layerById.get(id)).filter(Boolean) as Layer[];

  // --- create map
  useEffect(() => {
    if (!ref.current) return;
    const m = new maplibregl.Map({
      container: ref.current,
      center: KARACHI,
      zoom: 9.3,
      minZoom: 7,
      maxZoom: 16,
      attributionControl: false,
      preserveDrawingBuffer: true, // needed for the PDF map snapshot
      style: {
        version: 8,
        glyphs: "https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf",
        sources: Object.fromEntries(
          Object.entries(BASEMAPS).flatMap(([k, v]) => [
            [`bm-${k}`, { type: "raster", tiles: v.tiles, tileSize: 256, attribution: v.attribution, maxzoom: 16 }],
            ...(v.labels ? [[`bm-${k}-labels`, { type: "raster", tiles: v.labels, tileSize: 256, maxzoom: 16 }]] : []),
          ]),
        ),
        layers: [
          { id: "bg", type: "background", paint: { "background-color": "#0a0e14" } },
          ...Object.keys(BASEMAPS).map((k) => ({
            id: `bm-${k}`, type: "raster" as const, source: `bm-${k}`,
            layout: { visibility: (k === "dark" ? "visible" : "none") as "visible" | "none" },
            paint: { "raster-opacity": k === "satellite" ? 0.85 : 1 },
          })),
        ],
      },
    });
    m.addControl(new maplibregl.AttributionControl({ compact: true }), "bottom-right");
    m.addControl(new maplibregl.NavigationControl({ showCompass: false }), "bottom-right");
    m.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-left");
    m.on("load", () => {
      // Basemap place-name labels go above the data layers so they stay readable.
      (Object.keys(BASEMAPS) as Basemap[]).forEach((k) => {
        if (BASEMAPS[k].labels) {
          m.addLayer({
            id: `bm-${k}-labels`, type: "raster", source: `bm-${k}-labels`,
            layout: { visibility: k === "dark" ? "visible" : "none" }, paint: { "raster-opacity": 0.9 },
          });
        }
      });
      setReady(true);
      onMapReady?.(m);
    });
    mapRef.current = m;
    if (import.meta.env.DEV) ((window as unknown as { __kuvisMaps: MLMap[] }).__kuvisMaps ??= []).push(m);
    return () => m.remove();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // --- fit to study area
  useEffect(() => {
    if (ready && meta?.bounds && !layerIds) {
      mapRef.current!.fitBounds(meta.bounds as [number, number, number, number], { padding: 40, duration: 0 });
    }
  }, [ready, meta, layerIds]);

  // --- boundaries
  useEffect(() => {
    const m = mapRef.current;
    if (!ready || !m || !bounds) return;
    if (!m.getSource("study")) {
      m.addSource("study", { type: "geojson", data: bounds.study_area });
      m.addSource("subs", { type: "geojson", data: bounds.subdivisions });
      m.addLayer({ id: "subs-line", type: "line", source: "subs", paint: { "line-color": "#9aa7b8", "line-opacity": 0.35, "line-width": 0.8, "line-dasharray": [3, 2] } });
      m.addLayer({ id: "study-line", type: "line", source: "study", paint: { "line-color": "#5eb1bf", "line-width": 1.6, "line-opacity": 0.9 } });
      m.addLayer({
        id: "subs-label", type: "symbol", source: "subs", minzoom: 10,
        layout: { "text-field": ["get", "name"], "text-size": 11, "text-font": ["Open Sans Regular"] },
        paint: { "text-color": "#c6d0dc", "text-halo-color": "#0a0e14", "text-halo-width": 1.4, "text-opacity": 0.8 },
      });
    }
  }, [ready, bounds]);

  useEffect(() => {
    const m = mapRef.current;
    if (!ready || !m || !m.getLayer("subs-line")) return;
    const v = store.showSubdivisions ? "visible" : "none";
    m.setLayoutProperty("subs-line", "visibility", v);
    m.setLayoutProperty("subs-label", "visibility", v);
  }, [ready, store.showSubdivisions, bounds]);

  // --- basemap
  useEffect(() => {
    const m = mapRef.current;
    if (!ready || !m) return;
    (Object.keys(BASEMAPS) as Basemap[]).forEach((k) => {
      const v = k === store.basemap ? "visible" : "none";
      m.setLayoutProperty(`bm-${k}`, "visibility", v);
      if (m.getLayer(`bm-${k}-labels`)) m.setLayoutProperty(`bm-${k}-labels`, "visibility", v);
    });
  }, [ready, store.basemap]);

  // --- data layers
  // Tiles carry only the properties of the layers on screen. When that set changes, the "cells" source and every
  // layer on it are rebuilt with the new URL — source.setTiles() does not reliably reload already-loaded tiles.
  const cellsProps = useRef<string | null>(null);
  const [cellsVersion, setCellsVersion] = useState(0);
  const activeKey = active.join("|") + "|" + (layers ? layers.length : 0) + JSON.stringify(store.opacity);
  useEffect(() => {
    const m = mapRef.current;
    if (!ready || !m || !layers) return;
    const props = Array.from(new Set(activeRef.current.map((l) => l.prop))).sort().join(",");
    const before = m.getLayer(`bm-dark-labels`) ? "bm-dark-labels" : undefined; // keep labels on top
    if (cellsProps.current !== props || !m.getSource("cells")) {
      for (const l of m.getStyle().layers ?? []) if ((l as { source?: string }).source === "cells") m.removeLayer(l.id);
      if (m.getSource("cells")) m.removeSource("cells");
      m.addSource("cells", {
        type: "vector",
        tiles: [`${window.location.origin}/api/v1/tiles/cells/{z}/{x}/{y}.pbf${props ? `?props=${props}` : ""}`],
        minzoom: 8,
        maxzoom: 14,
      });
      m.addLayer({ id: "cells-hit", type: "fill", source: "cells", "source-layer": "cells", paint: { "fill-color": "#000", "fill-opacity": 0 } }, before);
      m.addLayer({ id: "cells-grid", type: "line", source: "cells", "source-layer": "cells", minzoom: 12,
        paint: { "line-color": "#ffffff", "line-opacity": 0.06, "line-width": 0.5 } }, before);
      m.addLayer({ id: "cells-compare", type: "line", source: "cells", "source-layer": "cells",
        filter: ["in", ["get", "grid_id"], ["literal", useMapStore.getState().compareSet]],
        paint: { "line-color": "#d9b44a", "line-width": 2 } }, before);
      m.addLayer({ id: "cells-selected", type: "line", source: "cells", "source-layer": "cells",
        filter: ["==", ["get", "grid_id"], useMapStore.getState().selected ?? ""],
        paint: { "line-color": "#ffffff", "line-width": 2.2 } }, before);
      cellsProps.current = props;
      setCellsVersion((v) => v + 1);
    }
    for (const l of m.getStyle().layers ?? []) if (l.id.startsWith("data-")) m.removeLayer(l.id);
    activeRef.current.forEach((lyr) => {
      const isCode = lyr.prop.endsWith("_code");
      m.addLayer(
        {
          id: `data-${lyr.id}`, type: "fill", source: "cells", "source-layer": "cells",
          filter: isCode ? ["all", ["has", lyr.prop], ["!=", ["get", lyr.prop], 0]] : ["has", lyr.prop],
          paint: { "fill-color": colorExpression(lyr), "fill-opacity": store.opacity[lyr.id] ?? 0.78, "fill-antialias": false },
        },
        "cells-grid",
      );
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, activeKey]);

  // --- selection + compare outlines
  useEffect(() => {
    const m = mapRef.current;
    if (!ready || !m || !m.getLayer("cells-selected")) return;
    m.setFilter("cells-selected", ["==", ["get", "grid_id"], store.selected ?? ""]);
    m.setFilter("cells-compare", ["in", ["get", "grid_id"], ["literal", store.compareSet]]);
  }, [ready, store.selected, store.compareSet, cellsVersion]);

  // --- fly to
  useEffect(() => {
    const m = mapRef.current;
    const f = store.flyTo;
    if (!ready || !m || !f) return;
    if (f.bbox) m.fitBounds(f.bbox as [number, number, number, number], { padding: 60, maxZoom: 13 });
    else m.flyTo({ center: [f.lon, f.lat], zoom: f.zoom ?? 13 });
    store.setFlyTo(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, store.flyTo]);

  // --- extra overlay (e.g. discovery geometry)
  useEffect(() => {
    const m = mapRef.current;
    if (!ready || !m) return;
    const src = m.getSource("extra") as maplibregl.GeoJSONSource | undefined;
    const data = extraGeoJSON ?? { type: "FeatureCollection", features: [] };
    if (src) src.setData(data);
    else {
      m.addSource("extra", { type: "geojson", data });
      m.addLayer({ id: "extra-line", type: "line", source: "extra", paint: { "line-color": "#f8d36a", "line-width": 2, "line-dasharray": [2, 1] } });
    }
  }, [ready, extraGeoJSON]);

  // --- interaction
  useEffect(() => {
    const m = mapRef.current;
    if (!ready || !m || !interactive || !cellsVersion) return;
    const popup = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 8, maxWidth: "280px" });
    const onMove = (e: maplibregl.MapMouseEvent & { features?: MapGeoJSONFeature[] }) => {
      const f = e.features?.[0];
      if (!f) return;
      m.getCanvas().style.cursor = "pointer";
      if (!showHover) return;
      const p = f.properties as Record<string, number | string>;
      const rows = activeRef.current
        .map((l) => {
          const v = p[l.prop];
          if (v === undefined || v === null) return "";
          const label = l.scale === "categorical"
            ? (l.legend.categories?.find((c) => c.value === Number(v))?.label ?? (Number(v) < 0 ? "noise" : `group ${v}`))
            : `${fmt(Number(v))} ${l.unit}`;
          return `<div style="display:flex;justify-content:space-between;gap:12px"><span style="color:#9aa7b8">${l.title}</span><span style="font-family:JetBrains Mono,monospace">${label}</span></div>`;
        })
        .join("");
      popup.setLngLat(e.lngLat).setHTML(`<div style="font-family:JetBrains Mono,monospace;color:#5eb1bf;margin-bottom:4px">${p.grid_id}</div>${rows || '<span style="color:#6b788b">click for report</span>'}`).addTo(m);
    };
    const onLeave = () => {
      m.getCanvas().style.cursor = "";
      popup.remove();
    };
    const onClick = (e: maplibregl.MapMouseEvent & { features?: MapGeoJSONFeature[] }) => {
      const id = e.features?.[0]?.properties?.grid_id as string | undefined;
      if (!id) return;
      if (e.originalEvent.shiftKey) store.toggleCompare(id);
      else store.select(id);
    };
    m.on("mousemove", "cells-hit", onMove);
    m.on("mouseleave", "cells-hit", onLeave);
    m.on("click", "cells-hit", onClick);
    return () => {
      m.off("mousemove", "cells-hit", onMove);
      m.off("mouseleave", "cells-hit", onLeave);
      m.off("click", "cells-hit", onClick);
      popup.remove();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, interactive, showHover, cellsVersion > 0]);

  return <div ref={ref} className={className ?? "absolute inset-0"} />;
}
