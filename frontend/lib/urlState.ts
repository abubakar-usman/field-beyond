// The explorer's view lives in the URL query so a refresh, a shared link or the browser's
// Back button returns to the same screen, target, region and search.
// Example: /?view=compare&body=mars&target=mars_jezero&region=earth_sahara&k=50&c=c3
import type { Body } from "./api";

export type Screen = "select" | "explore" | "compare";

export interface ViewState {
  screen: Screen;
  body: Body;
  /** Backend target id, or null. */
  target: string | null;
  /** A custom point (no target), planetocentric degrees. */
  lat: number | null;
  lon: number | null;
  /** Earth region id; null means the default for the target's scale. */
  region: string | null;
  topK: number;
  /** Selected result: "c<rank>" for a candidate, "r<rank>" for a reference match. */
  pick: string | null;
}

export const DEFAULT_TOP_K = 20;
export const TOP_K_CHOICES = [10, 20, 50, 100];

type Params = Record<string, string | string[] | undefined>;

function one(p: Params, k: string): string | null {
  const v = p[k];
  const s = Array.isArray(v) ? v[0] : v;
  return s && s.length <= 200 ? s : null;
}

function num(p: Params, k: string, lo: number, hi: number): number | null {
  const s = one(p, k);
  if (s === null) return null;
  const n = Number(s);
  return Number.isFinite(n) && n >= lo && n <= hi ? n : null;
}

const ID = /^[a-z0-9_-]+$/i;

export function parseView(p: Params): ViewState {
  const view = one(p, "view");
  const body = one(p, "body") === "mars" ? "mars" : "moon";
  const target = one(p, "target");
  const region = one(p, "region");
  const pick = one(p, "c");
  const k = num(p, "k", 1, 100);
  const lat = num(p, "lat", -90, 90);
  const lon = num(p, "lon", -180, 180);
  const custom = lat !== null && lon !== null;
  return {
    screen: view === "explore" || view === "compare" ? view : "select",
    body,
    target: target && ID.test(target) ? target : null,
    lat: custom ? lat : null,
    lon: custom ? lon : null,
    region: region && ID.test(region) ? region : null,
    topK: k !== null && TOP_K_CHOICES.includes(k) ? k : DEFAULT_TOP_K,
    pick: pick && /^[cr]\d{1,3}$/.test(pick) ? pick : null,
  };
}

export function viewToUrl(v: ViewState): string {
  if (v.screen === "select") return "/";
  const q = new URLSearchParams({ view: v.screen, body: v.body });
  if (v.target) q.set("target", v.target);
  else if (v.lat !== null && v.lon !== null) {
    q.set("lat", v.lat.toFixed(4));
    q.set("lon", v.lon.toFixed(4));
  }
  if (v.region) q.set("region", v.region);
  if (v.screen === "compare") {
    if (v.topK !== DEFAULT_TOP_K) q.set("k", String(v.topK));
    if (v.pick) q.set("c", v.pick);
  }
  return `/?${q.toString()}`;
}
