// User-facing labels. Wording rules: .claude/skills/scientific-copy/SKILL.md
// Scores are "configured similarity", never probability or confidence.
// Unlisted places are "not in checked records", never discoveries.
import type { NoveltyStatus } from "./api";

export const FEATURE_LABEL: Record<string, string> = {
  slope_hist: "Slope distribution",
  slope_median: "Median slope",
  slope_p90: "90th-percentile slope",
  relief: "Relief (p95 − p5)",
  roughness: "Roughness",
  valid_fraction: "Valid pixels",
};

export const FEATURE_HINT: Record<string, string> = {
  slope_hist: "Wasserstein-1 distance between slope distributions, in degrees",
  slope_median: "Median Horn slope over the window",
  slope_p90: "Steep end: 90th percentile of slope",
  relief: "Elevation range between the 5th and 95th percentiles",
  roughness: "Spread of elevation after removing the best-fit plane",
};

export const NOVELTY_LABEL: Record<NoveltyStatus, string> = {
  not_in_checked_records: "Not in checked records",
  under_review: "Under review",
  documented_analog: "Documented analog",
  promising: "Reviewed: promising",
  rejected: "Reviewed: rejected",
};

export const FLAG_LABEL: Record<string, string> = {
  valid_fraction: "Valid DEM pixels",
  water_fraction: "Water (WorldCover)",
  built_up_fraction: "Built-up (WorldCover)",
  snow_ice_fraction: "Snow / ice (flag only)",
  vegetation_fraction: "Vegetation (flag only)",
};

export const BODY_LABEL = { moon: "Moon", mars: "Mars" } as const;

export function fmtValue(v: number, unit: string): string {
  if (unit.startsWith("deg")) return `${v.toFixed(1)}°`;
  if (unit === "m") return Math.abs(v) >= 10 ? `${v.toFixed(0)} m` : `${v.toFixed(1)} m`;
  return v.toFixed(2);
}

export function fmtPct(v: number | null | undefined): string {
  if (v === null || v === undefined) return "not available";
  return `${(v * 100).toFixed(v < 0.01 && v > 0 ? 2 : 1)}%`;
}

export function fmtScore(v: number): string {
  return v.toFixed(1);
}

export const SCORE_NOTE =
  "Configured similarity under terrain-v1: how close the measurements are within the stated tolerances. It is not a probability.";
