import { useQuery } from "@tanstack/react-query";
import type { DataSource, Discovery, Experiment, Layer, Report } from "@/types/api";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export async function api<T>(path: string): Promise<T> {
  const r = await fetch(`/api/v1${path}`);
  if (!r.ok) {
    let msg = r.statusText;
    try {
      msg = (await r.json()).detail ?? msg;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(r.status, typeof msg === "string" ? msg : JSON.stringify(msg));
  }
  return r.json() as Promise<T>;
}

const STATIC = { staleTime: 5 * 60_000 };

export const useOverview = () => useQuery({ queryKey: ["overview"], queryFn: () => api<any>("/overview"), ...STATIC });
export const useLayers = () => useQuery({ queryKey: ["layers"], queryFn: () => api<Layer[]>("/map/layers"), ...STATIC });
export const useBoundaries = () =>
  useQuery({ queryKey: ["boundaries"], queryFn: () => api<{ study_area: GeoJSON.FeatureCollection; subdivisions: GeoJSON.FeatureCollection }>("/map/boundaries"), ...STATIC });
export const useMapMeta = () => useQuery({ queryKey: ["map-meta"], queryFn: () => api<{ bounds: [number, number, number, number] }>("/map/metadata"), ...STATIC });
export const useReport = (id: string | null) =>
  useQuery({ queryKey: ["report", id], queryFn: () => api<Report>(`/areas/${id}/report`), enabled: !!id, ...STATIC });
export const useMethodology = () => useQuery({ queryKey: ["methodology"], queryFn: () => api<Experiment[]>("/methodology"), ...STATIC });
export const useExperiment = (id: string | null) =>
  useQuery({ queryKey: ["experiment", id], queryFn: () => api<Experiment>(`/experiments/${id}`), enabled: !!id, ...STATIC });
export const useDiscoveries = (category?: string) =>
  useQuery({
    queryKey: ["discoveries", category],
    queryFn: () => api<{ total: number; items: Discovery[] }>(`/discoveries${category ? `?category=${encodeURIComponent(category)}` : ""}`),
    ...STATIC,
  });
export const useSources = () => useQuery({ queryKey: ["sources"], queryFn: () => api<DataSource[]>("/data/sources"), ...STATIC });
export const useDataStatus = () => useQuery({ queryKey: ["data-status"], queryFn: () => api<any>("/data/status"), ...STATIC });
export const useEpochHistory = () => useQuery({ queryKey: ["hist-epochs"], queryFn: () => api<any[]>("/history/epochs"), ...STATIC });
export const useRainHistory = () => useQuery({ queryKey: ["hist-rain"], queryFn: () => api<any[]>("/history/rainfall"), ...STATIC });
export const useSubdivisions = () => useQuery({ queryKey: ["subdivisions"], queryFn: () => api<any[]>("/subdivisions"), ...STATIC });
export const useCompare = (ids: string[]) =>
  useQuery({ queryKey: ["compare", ids], queryFn: () => api<any>(`/compare?ids=${ids.join(",")}`), enabled: ids.length >= 2, ...STATIC });
