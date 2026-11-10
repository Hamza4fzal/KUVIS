import { useEffect } from "react";
import MapView from "@/maps/MapView";
import LayerPanel from "@/maps/LayerPanel";
import ReportPanel from "@/reports/ReportPanel";
import ExperimentCard from "@/charts/ExperimentCard";
import { useLayers, useMethodology } from "@/services/api";
import { useMapStore } from "@/store/mapStore";
import { Empty, ErrorState, Loading, PageHeader } from "@/components/ui";
import type { ReactNode } from "react";

interface Props {
  module: string;
  title: string;
  color: string;
  groups: string[];
  defaultLayers: string[];
  intro: ReactNode;
  caveat?: ReactNode;
}

export default function ModulePage({ module, title, color, groups, defaultLayers, intro, caveat }: Props) {
  const { data: exps, isLoading, error } = useMethodology();
  const { data: layers } = useLayers();
  const { setLayers, select } = useMapStore();
  useEffect(() => {
    if (layers) setLayers(defaultLayers.filter((id) => layers.some((l) => l.id === id)).slice(0, 1));
    select(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [module, layers]);
  const mine = (exps ?? []).filter((e) => e.module === module);
  return (
    <div className="absolute inset-0 grid grid-cols-[minmax(0,1fr)_minmax(560px,46%)]">
      <div className="relative">
        <MapView />
        <div className="absolute top-3 left-3 bottom-10 z-10 flex pointer-events-none">
          <div className="pointer-events-auto max-h-full flex"><LayerPanel groups={groups} /></div>
        </div>
        <ReportPanel />
      </div>
      <div className="overflow-y-auto scroll-thin border-l border-ink-700 p-5 space-y-4 bg-ink-950">
        <div className="h-1 w-10 rounded" style={{ background: color }} />
        <PageHeader title={title}>{intro}</PageHeader>
        {caveat && <div className="panel p-3 text-xs text-fg-muted border-warn/30"><span className="text-warn font-medium">Scope note · </span>{caveat}</div>}
        {isLoading && <Loading label="Loading experiments" />}
        {error && <ErrorState error={error} />}
        {!isLoading && !mine.length && <Empty>No experiments for this module are stored yet. Run <code className="num">python scripts/run_pipeline.py mine_{module === "urban" ? "urban" : module} load_db</code>.</Empty>}
        {mine.map((e) => <ExperimentCard key={e.experiment_id} e={e} />)}
      </div>
    </div>
  );
}
