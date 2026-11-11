import { createBrowserRouter, RouterProvider } from "react-router-dom";
import AppLayout from "@/layouts/AppLayout";
import Overview from "@/pages/Overview";
import Explore from "@/pages/Explore";
import ModulePage from "@/pages/ModulePage";
import Discoveries from "@/pages/Discoveries";
import History from "@/pages/History";
import Compare from "@/pages/Compare";
import Methodology from "@/pages/Methodology";
import Sources from "@/pages/Sources";

const router = createBrowserRouter([
  {
    path: "/",
    element: <AppLayout />,
    children: [
      { index: true, element: <Overview /> },
      { path: "explore", element: <Explore /> },
      {
        path: "heat",
        element: (
          <ModulePage module="heat" title="Urban Heat Intelligence" color="#e8774a" groups={["Heat", "Environment", "Population"]}
            defaultLayers={["lst_rel_2024", "lst_2024"]}
            intro={<>Daytime land surface temperature (Landsat, Apr–Jun) mined for thermal profiles (K-means), dense hot concentrations (DBSCAN),
              statistically significant hot spots (Gi*) and contextual anomalies (Isolation Forest vs LOF), and related to vegetation, built-up surface,
              population, terrain and distance to the sea.</>}
            caveat="Land surface temperature is the radiometric skin temperature of roofs, roads and ground at ~10:30 local time. It is not air temperature and does not measure human heat stress directly." />
        ),
      },
      {
        path: "flood",
        element: (
          <ModulePage module="flood" title="Flood Vulnerability Intelligence" color="#4f8fd9" groups={["Flood", "Terrain", "Urbanization"]}
            defaultLayers={["flood_kmeans", "rain_jjas", "elevation"]}
            intro={<>Terrain, imperviousness, vegetation, drainage proximity, surface-water history and CHIRPS rainfall mined for flood-related
              profiles and associations. Supervised models are trained only against an independent flood label.</>}
            caveat="No validated, cell-level record of historical urban flooding in Karachi is openly available; results describe flood-related susceptibility characteristics, not observed flood depth or frequency. Rainfall is assigned from ≈5.5 km pixels." />
        ),
      },
      {
        path: "urbanization",
        element: (
          <ModulePage module="urban" title="Urbanization & Land-use Intelligence" color="#c9a46b" groups={["Urbanization", "History", "Population"]}
            defaultLayers={["ndvi_change", "built"]}
            intro={<>Change between the 2000–02 and 2023–25 Landsat epochs (vegetation, built-up spectral signal, relative heat), World Bank EO4SD land-use
              2005→2017 transitions, and population growth — clustered into development trajectories and screened for unusually large changes.</>}
            caveat="Landsat 5 (TM) and Landsat 8/9 (OLI) differ slightly in band response; small index differences can be sensor effects. WorldCover 2020 vs 2021 differences are algorithmic and are never treated as change." />
        ),
      },
      {
        path: "infrastructure",
        element: (
          <ModulePage module="infra" title="Infrastructure Intelligence" color="#9a8fd1" groups={["Infrastructure", "Population"]}
            defaultLayers={["road_density"]}
            intro={<>Road-network density, intersection density, major-road access and mapped building density from OpenStreetMap, profiled with K-means.</>}
            caveat="No traffic observations were obtainable (TomTom requires a paid key; no open Karachi traffic feed was found). This module therefore describes infrastructure supply only and makes no congestion claims. OSM completeness varies across the city." />
        ),
      },
      {
        path: "vulnerability",
        element: (
          <ModulePage module="vulnerability" title="Multi-dimensional Vulnerability Intelligence" color="#d65b72" groups={["Vulnerability", "Heat", "Flood"]}
            defaultLayers={["uvi"]}
            intro={<>Normalized dimension indicators (heat, flood-related susceptibility, urbanization pressure, environmental stress) combined into an
              explainable composite index with an explicit missing-data rule, Monte-Carlo weight sensitivity, and clustering of overlapping stress.</>}
            caveat="The UVI is a transparent research construct for comparing locations within Karachi. It is not an officially certified disaster-risk assessment, and population density is treated as exposure, not social vulnerability." />
        ),
      },
      { path: "discoveries", element: <Discoveries /> },
      { path: "history", element: <History /> },
      { path: "compare", element: <Compare /> },
      { path: "methodology", element: <Methodology /> },
      { path: "sources", element: <Sources /> },
    ],
  },
], {
  future: { v7_relativeSplatPath: true, v7_fetcherPersist: true, v7_normalizeFormMethod: true,
            v7_partialHydration: true, v7_skipActionErrorRevalidation: true },
});

export default function App() {
  return <RouterProvider router={router} future={{ v7_startTransition: true }} />;
}
