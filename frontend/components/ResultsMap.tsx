"use client";

// Earth map only. Moon and Mars locations are never drawn here (CLAUDE.md rule 3):
// planetary targets appear as pre-rendered preview images in the side panels.
import * as maplibregl from "maplibre-gl";
import type { GeoJSONSource, MapLayerMouseEvent } from "maplibre-gl";
import type { FeatureCollection } from "geojson";
import { useEffect, useRef, useState } from "react";
import type { Candidate, Region, RegistryResponse } from "@/lib/api";
import { NOVELTY_LABEL, fmtScore } from "@/lib/copy";

const STYLE = "https://tiles.openfreemap.org/styles/liberty";
// Worker copied into public/ by scripts/copy-maplibre-worker.mjs.
maplibregl.setWorkerUrl("/maplibre/maplibre-gl-worker.mjs");
const ENABLE_EOX = process.env.NEXT_PUBLIC_ENABLE_EOX === "true";
const EMPTY: FeatureCollection = { type: "FeatureCollection", features: [] };

interface Props {
  region: Region | null;
  candidates: Candidate[];
  references: Candidate[];
  registry: RegistryResponse | null;
  selectedId: string | null;
  onSelect: (id: string) => void;
}

function toFC(cands: Candidate[]): FeatureCollection {
  return {
    type: "FeatureCollection",
    features: cands.map((c) => ({
      type: "Feature",
      id: c.rank,
      geometry: c.geometry,
      properties: { id: c.id, score: c.score, rank: c.rank, novelty: c.novelty_status },
    })),
  };
}

export default function ResultsMap({
  region,
  candidates,
  references,
  registry,
  selectedId,
  onSelect,
}: Props) {
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  // The loaded map instance. A new (not yet loaded) map after a remount is never used.
  const [loaded, setLoaded] = useState<maplibregl.Map | null>(null);
  const [showRefs, setShowRefs] = useState(true);
  const [showRegistry, setShowRegistry] = useState(false);
  const [showSat, setShowSat] = useState(false);
  const [hover, setHover] = useState<{ x: number; y: number; text: string } | null>(null);
  const onSelectRef = useRef(onSelect);
  useEffect(() => {
    onSelectRef.current = onSelect;
  }, [onSelect]);

  useEffect(() => {
    if (!el.current) return;
    const m = new maplibregl.Map({
      container: el.current,
      style: STYLE,
      center: [-40, 0],
      zoom: 2,
      attributionControl: { compact: true },
    });
    m.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    m.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-right");
    m.on("load", () => {
      if (ENABLE_EOX) {
        m.addSource("eox", {
          type: "raster",
          tiles: [
            "https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless-2023_3857/default/GoogleMapsCompatible/{z}/{y}/{x}.jpg",
          ],
          tileSize: 256,
          attribution:
            "Sentinel-2 cloudless by EOX IT Services GmbH (contains modified Copernicus Sentinel data 2023)",
        });
        m.addLayer({ id: "eox", type: "raster", source: "eox", layout: { visibility: "none" } });
      }
      for (const id of ["region", "cands", "refs", "registry", "members"]) {
        m.addSource(id, { type: "geojson", data: EMPTY });
      }
      m.addLayer({
        id: "region-line",
        type: "line",
        source: "region",
        paint: { "line-color": "#52514e", "line-width": 1.5, "line-dasharray": [3, 2] },
      });
      m.addLayer({
        id: "registry-fill",
        type: "fill",
        source: "registry",
        layout: { visibility: "none" },
        paint: { "fill-color": "#6250d6", "fill-opacity": 0.12 },
      });
      m.addLayer({
        id: "registry-line",
        type: "line",
        source: "registry",
        layout: { visibility: "none" },
        paint: { "line-color": "#6250d6", "line-width": 1 },
      });
      m.addLayer({
        id: "cands-fill",
        type: "fill",
        source: "cands",
        paint: {
          // Sequential blue: higher configured similarity = darker.
          "fill-color": [
            "interpolate",
            ["linear"],
            ["get", "score"],
            0,
            "#cde2fb",
            50,
            "#6da7ec",
            75,
            "#256abf",
            100,
            "#0d366b",
          ],
          "fill-opacity": 0.7,
        },
      });
      m.addLayer({
        id: "cands-line",
        type: "line",
        source: "cands",
        paint: { "line-color": "#fcfcfb", "line-width": 2 },
      });
      m.addLayer({
        id: "refs-line",
        type: "line",
        source: "refs",
        paint: { "line-color": "#6250d6", "line-width": 2.5, "line-dasharray": [2, 1.5] },
      });
      m.addLayer({
        id: "members-line",
        type: "line",
        source: "members",
        paint: { "line-color": "#eb6834", "line-width": 2 },
      });
      for (const layer of ["cands-fill", "refs-line"]) {
        m.on("click", layer, (e: MapLayerMouseEvent) => {
          const id = e.features?.[0]?.properties?.id as string | undefined;
          if (id) onSelectRef.current(id);
        });
        m.on("mousemove", layer, (e: MapLayerMouseEvent) => {
          const p = e.features?.[0]?.properties;
          if (!p) return;
          m.getCanvas().style.cursor = "pointer";
          setHover({
            x: e.point.x,
            y: e.point.y,
            text: `#${p.rank} · configured similarity ${fmtScore(Number(p.score))} · ${
              NOVELTY_LABEL[p.novelty as keyof typeof NOVELTY_LABEL] ?? p.novelty
            }`,
          });
        });
        m.on("mouseleave", layer, () => {
          m.getCanvas().style.cursor = "";
          setHover(null);
        });
      }
      setLoaded(m);
    });
    map.current = m;
    return () => {
      setLoaded(null);
      m.remove();
      map.current = null;
    };
  }, []);

  useEffect(() => {
    const m = loaded;
    if (!m || !region) return;
    const b = region.bbox;
    (m.getSource("region") as GeoJSONSource).setData({
      type: "Feature",
      properties: {},
      geometry: {
        type: "Polygon",
        coordinates: [
          [
            [b.west, b.south],
            [b.east, b.south],
            [b.east, b.north],
            [b.west, b.north],
            [b.west, b.south],
          ],
        ],
      },
    });
    m.fitBounds(
      [
        [b.west, b.south],
        [b.east, b.north],
      ],
      { padding: 40, duration: 600 },
    );
  }, [loaded, region]);

  useEffect(() => {
    const m = loaded;
    if (!m) return;
    (m.getSource("cands") as GeoJSONSource).setData(toFC(candidates));
    (m.getSource("refs") as GeoJSONSource).setData(showRefs ? toFC(references) : EMPTY);
  }, [loaded, candidates, references, showRefs]);

  useEffect(() => {
    const m = loaded;
    if (!m) return;
    (m.getSource("registry") as GeoJSONSource).setData(registry?.geojson ?? EMPTY);
    const vis = showRegistry ? "visible" : "none";
    m.setLayoutProperty("registry-fill", "visibility", vis);
    m.setLayoutProperty("registry-line", "visibility", vis);
  }, [loaded, registry, showRegistry]);

  useEffect(() => {
    const m = loaded;
    if (!m || !ENABLE_EOX) return;
    m.setLayoutProperty("eox", "visibility", showSat ? "visible" : "none");
  }, [loaded, showSat]);

  useEffect(() => {
    const m = loaded;
    if (!m) return;
    const sel = [...candidates, ...references].find((c) => c.id === selectedId);
    (m.getSource("members") as GeoJSONSource).setData(
      sel
        ? {
            type: "FeatureCollection",
            features: sel.members.map((w) => ({
              type: "Feature",
              geometry: w.geometry,
              properties: {},
            })),
          }
        : EMPTY,
    );
    if (sel) {
      m.easeTo({
        center: [sel.center.lon, sel.center.lat],
        zoom: Math.max(m.getZoom(), 9),
        duration: 600,
      });
    }
  }, [loaded, selectedId, candidates, references]);

  return (
    <div className="mapwrap">
      <div ref={el} className="map" role="region" aria-label="Map of Earth candidates" />
      {hover && (
        <div className="tooltip" style={{ left: hover.x + 12, top: hover.y + 12 }}>
          {hover.text}
        </div>
      )}
      <div className="maplegend">
        <strong>Configured similarity (terrain-v1)</strong>
        <div className="ramp" aria-hidden />
        <div className="legend num" style={{ justifyContent: "space-between" }}>
          <span>0</span>
          <span>50</span>
          <span>100</span>
        </div>
        <div className="legend">
          <span>
            <span className="swatch" style={{ background: "var(--target)" }} />
            Member windows (10 km)
          </span>
        </div>
        <label>
          <input
            type="checkbox"
            checked={showRefs}
            onChange={(e) => setShowRefs(e.target.checked)}
          />{" "}
          Documented analogs in results (dashed)
        </label>
        <label>
          <input
            type="checkbox"
            checked={showRegistry}
            onChange={(e) => setShowRegistry(e.target.checked)}
          />{" "}
          Checked registry records
        </label>
        {ENABLE_EOX && (
          <label>
            <input
              type="checkbox"
              checked={showSat}
              onChange={(e) => setShowSat(e.target.checked)}
            />{" "}
            Satellite (EOX, non-commercial)
          </label>
        )}
      </div>
    </div>
  );
}
