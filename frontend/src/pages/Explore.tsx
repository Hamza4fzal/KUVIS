import { useEffect } from "react";
import { Link } from "react-router-dom";
import MapView from "@/maps/MapView";
import LayerPanel from "@/maps/LayerPanel";
import ReportPanel from "@/reports/ReportPanel";
import { useLayers } from "@/services/api";
import { useMapStore } from "@/store/mapStore";

export default function Explore() {
  const { data: layers } = useLayers();
  const { activeLayers, setLayers, compareSet, clearCompare } = useMapStore();
  useEffect(() => {
    if (layers?.length && activeLayers.length === 0) {
      const pref = ["uvi", "lst_2024", "built"].find((id) => layers.some((l) => l.id === id));
      if (pref) setLayers([pref]);
    }
  }, [layers, activeLayers.length, setLayers]);
  return (
    <div className="absolute inset-0">
      <MapView />
      <div className="absolute top-3 left-3 bottom-10 z-10 flex flex-col gap-2 pointer-events-none">
        <div className="pointer-events-auto max-h-full flex"><LayerPanel /></div>
      </div>
      {compareSet.length > 0 && (
        <div className="absolute bottom-10 left-1/2 -translate-x-1/2 z-10 panel px-3 py-2 flex items-center gap-3 shadow-xl">
          <span className="text-xs text-fg-muted">Compare set:</span>
          <span className="num text-xs">{compareSet.join(", ")}</span>
          <Link className="btn-primary" to="/compare">Compare {compareSet.length}</Link>
          <button className="btn" onClick={clearCompare}>Clear</button>
        </div>
      )}
      <ReportPanel />
    </div>
  );
}
