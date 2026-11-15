import type { FeatureCollection, Geometry } from "geojson";

// Typed client for the FastAPI backend. All calls go through /api (same origin).

export type Body = "moon" | "mars";
export type NoveltyStatus =
  "not_in_checked_records" | "under_review" | "documented_analog" | "promising" | "rejected";
export type DataStatus = "synthetic" | "measured";

export interface Target {
  id: string;
  body: Body;
  name: string;
  comparison: { center_lat: number; center_lon: number; footprint_m: number; scale_m: number };
  preview: { bbox: { west: number; south: number; east: number; north: number }; note: string };
  preview_url: string | null;
  profile_status: "ready" | "not_ready";
  data_status: DataStatus | null;
  origin?: "curated" | "iau_gazetteer";
  diameter_km?: number | null;
  feature_type?: string | null;
  gazetteer_link?: string | null;
}

export interface Region {
  id: string;
  name: string;
  role: "benchmark" | "discovery";
  description: string;
  bbox: { west: number; south: number; east: number; north: number };
  scales: Record<
    string,
    { status: string; run_id?: string; data_status?: DataStatus; windows?: number }
  >;
  window_m: number;
  stride_m: number;
}

export interface Component {
  feature: string;
  earth: number | number[];
  target: number | number[];
  difference: number;
  tolerance: number;
  similarity: number;
  weight: number;
  unit: string;
  within_tolerance: boolean;
}

export interface Candidate {
  id: string;
  search_id: string;
  list: "candidates" | "reference_matches";
  rank: number;
  score: number;
  best_cell_id: number;
  center: { lon: number; lat: number };
  geometry: Geometry;
  members: { cell_id: number; score: number; geometry: Geometry }[];
  components: Record<string, Component>;
  main_mismatch: string | null;
  flags: Record<string, number | null>;
  novelty_status: NoveltyStatus;
  novelty: {
    registry_version: string;
    review_date: string;
    sources_checked: string[];
    registry_loaded: boolean;
    matched: { id: string; name: string; source: string; body_target_relevance: string[] }[];
  };
  explanation: {
    summary: string;
    lines: string[];
    main_mismatch: string | null;
    not_available: string[];
    text: string;
  };
}

export interface SearchMeta {
  target_id: string;
  target_name: string;
  target_body: Body;
  region_id: string;
  region_name: string;
  scale_m: number;
  window_m: number;
  top_k: number;
  scoring_version: string;
  feature_schema_version: string;
  tolerances: Record<string, number>;
  weights: Record<string, number>;
  slope_hist_bins_deg: number[];
  counts: {
    windows_in_region: number;
    eligible: number;
    ineligible_by_reason: Record<string, number>;
    shortlist: number;
    excluded_missing_mandatory: number;
    scored: number;
    groups: number;
  };
  registry: {
    registry_version: string;
    review_date: string;
    sources_checked: string[];
    registry_loaded: boolean;
    entries: number;
  };
  provenance: Record<string, unknown>;
  data_status: DataStatus;
  unavailable_evidence: string[];
  created_at: string;
}

export interface CandidatesResponse {
  search: { id: string; status: string; request: Record<string, unknown>; meta: SearchMeta };
  candidates: Candidate[];
  reference_matches: Candidate[];
  pagination: { offset: number; limit: number; total: number };
  reference_total: number;
}

export interface Profile {
  values: Record<string, number | number[] | null>;
  availability: Record<string, boolean>;
  run_id: string;
  scale_m: number;
}

export interface Review {
  id: number;
  reviewer_id: string;
  decision: NoveltyStatus;
  previous_status: NoveltyStatus;
  note: string;
  created_at: string | null;
}

export interface Evidence {
  candidate: Candidate;
  scale: {
    scale_m: number;
    window_m: number;
    scoring_version: string;
    feature_schema_version: string;
  };
  target: {
    id: string;
    name: string;
    body: Body;
    values: Record<string, number | number[] | null>;
    run_id: string;
    data_status: DataStatus;
    preview_url: string | null;
  };
  earth_profile: Profile | null;
  member_profiles: Record<string, Profile>;
  missing_profiles: number[];
  slope_hist_bins_deg: number[];
  tolerances: Record<string, number>;
  weights: Record<string, number>;
  unavailable_evidence: string[];
  novelty: Candidate["novelty"] & { status: NoveltyStatus };
  provenance: Record<string, unknown>;
  data_status: DataStatus;
  reviews: Review[];
}

export interface RegistryResponse {
  registry_version: string;
  review_date: string;
  sources_checked: string[];
  registry_loaded: boolean;
  geojson: FeatureCollection;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    public detail: Record<string, unknown>,
  ) {
    super(code);
  }
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    let body: Record<string, unknown> = {};
    try {
      body = (await res.json()) as Record<string, unknown>;
    } catch {
      /* non-JSON error body */
    }
    const code =
      typeof body.error === "string"
        ? body.error
        : typeof body.detail === "string"
          ? body.detail
          : `http_${res.status}`;
    throw new ApiError(res.status, code, body);
  }
  return (await res.json()) as T;
}

export interface TargetDetail extends Target {
  profile?: {
    values: Record<string, number | number[] | null>;
    availability: Record<string, boolean>;
    meta: Record<string, unknown>;
    run_id: string;
    schema_version: string;
    crs: string;
    footprint_wkt: string;
    source_asset_ids: string[];
  };
}

export interface RescoreResponse {
  search_id: string;
  weights: Record<string, number>;
  note: string;
  windows: { cell_id: number; score: number; main_mismatch: string | null }[];
}

export interface Health {
  status: "ok" | "degraded";
  store: string;
  store_detail: string;
  code_version: string;
  api_version: string;
}

export const api = {
  // /health answers 503 when degraded; keep the body so the UI can show why.
  health: async (): Promise<Health> => {
    const res = await fetch("/api/health");
    return (await res.json()) as Health;
  },
  targets: () => call<Target[]>("/targets"),
  regions: () => call<Region[]>("/regions"),
  registry: () => call<RegistryResponse>("/registry"),
  search: (req: { target_id: string; region_id: string; top_k: number }) =>
    call<{ search_id: string; status: string; scale_m: number }>("/searches", {
      method: "POST",
      body: JSON.stringify({
        ...req,
        purpose: "exposed_terrain",
        required_feature_groups: ["terrain"],
        optional_feature_groups: ["geology"],
        exclude_documented_analogs: true,
        retrieval_mode: "baseline",
        scoring_version: "terrain-v1",
      }),
    }),
  candidates: (searchId: string, limit = 100) =>
    call<CandidatesResponse>(`/searches/${searchId}/candidates?limit=${limit}`),
  target: (targetId: string) => call<TargetDetail>(`/targets/${encodeURIComponent(targetId)}`),
  run: (runId: string) =>
    call<Record<string, unknown>>(`/processing-runs/${encodeURIComponent(runId)}`),
  rescore: (searchId: string, weights: Record<string, number>) =>
    call<RescoreResponse>(`/searches/${searchId}/rescore`, {
      method: "POST",
      body: JSON.stringify({ weights }),
    }),
  evidence: (candidateId: string) => call<Evidence>(`/candidates/${candidateId}/evidence`),
  review: (
    candidateId: string,
    token: string,
    body: { reviewer_id: string; decision: NoveltyStatus; note: string },
  ) =>
    call<Review>(`/candidates/${candidateId}/reviews`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: JSON.stringify(body),
    }),
};

export function exportUrl(searchId: string, fmt: "geojson" | "csv"): string {
  return `/api/searches/${searchId}/export.${fmt}`;
}

export function previewUrl(path: string | null): string | null {
  return path ? `/api${path}` : null;
}
