// Display facts for the two planetary bodies, plus helpers for planetary coordinates.
// Locations come from the backend (/api/targets); nothing here is a scored target.
import type { Body, Target } from "./api";

export type PlanetId = Body;

/** A point on a planetary body. `targetId` is set only when it is a backend target. */
export type SurfacePoint = {
  lat: number;
  lon: number;
  name?: string;
  description?: string;
  targetId?: string;
};

export type Planet = {
  id: PlanetId;
  name: string;
  altName: string;
  subtitle: string;
  description: string;
  diameter: string;
  gravity: string;
  distance: string;
  distanceNote: string;
  dataset: string;
  /** Mean radius in metres. Each body uses its own radius (CLAUDE.md rule 3). */
  radiusM: number;
};

export const planets: Record<PlanetId, Planet> = {
  moon: {
    id: "moon",
    name: "Moon",
    altName: "Luna / Earth I",
    subtitle: "OUR NEAREST NEIGHBOUR",
    description: "Craters, maria and highlands, measured from orbit at about 60 m per pixel.",
    diameter: "3,474.8",
    gravity: "1.62",
    distance: "384,400",
    distanceNote: " KM FROM EARTH",
    dataset: "SLDEM2015",
    radiusM: 1_737_400, // IAU 2015 sphere, same as core/bodies.py
  },
  mars: {
    id: "mars",
    name: "Mars",
    altName: "Mars / Sol IV",
    subtitle: "THE RED PLANET",
    description: "Volcanoes, canyons and old crater lakes, compared at 200 m per pixel.",
    diameter: "6,779",
    gravity: "3.71",
    distance: "225M",
    distanceNote: " KM · AVG. FROM EARTH",
    dataset: "MOLA–HRSC",
    radiusM: 3_396_190, // IAU 2015 sphere, same as core/bodies.py
  },
};

export function coordinate(value: number, latitude = true) {
  const hemi = latitude ? (value >= 0 ? "N" : "S") : value >= 0 ? "E" : "W";
  return `${Math.abs(value).toFixed(4)}° ${hemi}`;
}

/** Great-circle distance on the given body, in metres. */
export function distanceM(a: SurfacePoint, b: SurfacePoint, radiusM: number): number {
  const r = Math.PI / 180;
  const dLat = (b.lat - a.lat) * r;
  const dLon = (b.lon - a.lon) * r;
  const h =
    Math.sin(dLat / 2) ** 2 + Math.cos(a.lat * r) * Math.cos(b.lat * r) * Math.sin(dLon / 2) ** 2;
  return 2 * radiusM * Math.asin(Math.min(1, Math.sqrt(h)));
}

export function targetPoint(t: Target): SurfacePoint {
  return {
    lat: t.comparison.center_lat,
    lon: t.comparison.center_lon,
    name: t.name,
    targetId: t.id,
    description: [
      t.feature_type,
      t.diameter_km != null ? `${t.diameter_km.toFixed(0)} km landform` : null,
      `Scored footprint: ${t.comparison.footprint_m / 1000} km square at ${t.comparison.scale_m} m pixels.`,
    ]
      .filter(Boolean)
      .join(" · "),
  };
}

/** Nearest backend target on the same body; profile-ready targets first. */
export function nearestTarget(
  point: SurfacePoint,
  targets: Target[],
  planet: Planet,
): { target: Target; distanceM: number } | null {
  let best: { target: Target; distanceM: number } | null = null;
  const pool = targets.filter((t) => t.body === planet.id);
  const ready = pool.filter((t) => t.profile_status === "ready");
  for (const t of ready.length ? ready : pool) {
    const d = distanceM(point, targetPoint(t), planet.radiusM);
    if (!best || d < best.distanceM) best = { target: t, distanceM: d };
  }
  return best;
}

export function fmtKm(m: number): string {
  const km = m / 1000;
  return km >= 100 ? `${km.toFixed(0)} km` : `${km.toFixed(1)} km`;
}
