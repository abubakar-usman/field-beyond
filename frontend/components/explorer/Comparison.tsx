"use client";

// Runs POST /searches for the chosen target and Earth region, lists the ranked candidates,
// and shows the evidence for the selected one. Scores come from the backend only.
import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import {
  ArrowLeft,
  ArrowUpRight,
  Check,
  CircleHelp,
  Download,
  Earth,
  Layers3,
  LoaderCircle,
  Mountain,
  Radio,
  RotateCcw,
  SlidersHorizontal,
  TriangleAlert,
} from "lucide-react";
import Globe from "./Globe";
import Reweight from "./Reweight";
import RunDetails from "./RunDetails";
import EvidenceDetails from "@/components/EvidencePanel";
import {
  ApiError,
  api,
  exportUrl,
  previewUrl,
  type Candidate,
  type CandidatesResponse,
  type Component,
  type Evidence,
  type Region,
  type RegistryResponse,
  type Target,
} from "@/lib/api";
import { FEATURE_LABEL, NOVELTY_LABEL, SCORE_NOTE, fmtScore, fmtValue } from "@/lib/copy";
import { coordinate, targetPoint, type Planet } from "@/lib/planets";

const ResultsMap = dynamic(() => import("@/components/ResultsMap"), { ssr: false });

const DEFAULT_TOP_K = 20;
const TOP_K_CHOICES = [10, 20, 50, 100];
const METRIC_ORDER = ["slope_hist", "slope_median", "slope_p90", "relief", "roughness"];

export function errorText(e: unknown): string {
  if (e instanceof ApiError) {
    if (e.code === "features_not_ready")
      return `No Earth features for this region at ${String(e.detail.scale_m ?? "this")} m yet. Run the pipeline (or seed-fake) for that scale.`;
    if (e.code === "target_not_ready")
      return "This target has no terrain profile yet. Run `pipeline target`.";
    if (e.code === "features_checksum_mismatch")
      return "The feature file does not match its processing run, so the search was refused.";
    return `${e.code} (HTTP ${e.status})`;
  }
  return e instanceof Error ? e.message : String(e);
}

function metricValue(c: Component, side: "earth" | "target"): string {
  const v = c[side];
  return Array.isArray(v) ? `${v.length}-bin histogram` : fmtValue(v, c.unit);
}

export default function Comparison({
  planet,
  target,
  region,
  regions,
  onRegionChange,
  registry,
  onBack,
}: {
  planet: Planet;
  target: Target;
  region: Region;
  regions: Region[];
  onRegionChange: (id: string) => void;
  registry: RegistryResponse | null;
  onBack: () => void;
}) {
  const [attempt, setAttempt] = useState(0);
  const [topK, setTopK] = useState(DEFAULT_TOP_K);
  const key = `${target.id}|${region.id}|${topK}|${attempt}`;
  // Results are keyed by request so a stale response never shows for another search.
  const [run, setRun] = useState<{ key: string; data?: CandidatesResponse; error?: string } | null>(
    null,
  );
  const [picked, setPicked] = useState<{ key: string; id: string } | null>(null);
  const [evidence, setEvidence] = useState<{ id: string; ev?: Evidence; error?: string } | null>(
    null,
  );
  const [evReload, setEvReload] = useState(0);

  useEffect(() => {
    let live = true;
    api
      .search({ target_id: target.id, region_id: region.id, top_k: topK })
      .then((s) => api.candidates(s.search_id, Math.max(topK, 50)))
      .then((data) => live && setRun({ key, data }))
      .catch((e: unknown) => live && setRun({ key, error: errorText(e) }));
    return () => {
      live = false;
    };
  }, [key, target.id, region.id, topK]);

  const current = run?.key === key ? run : null;
  const data = current?.data ?? null;
  const all: Candidate[] = data ? [...data.candidates, ...data.reference_matches] : [];
  const selectedId =
    (picked?.key === key ? picked.id : null) ?? data?.candidates[0]?.id ?? all[0]?.id ?? null;
  const selected = all.find((c) => c.id === selectedId) ?? null;

  useEffect(() => {
    if (!selectedId) return;
    let live = true;
    api
      .evidence(selectedId)
      .then((ev) => live && setEvidence({ id: selectedId, ev }))
      .catch((e: unknown) => live && setEvidence({ id: selectedId, error: errorText(e) }));
    return () => {
      live = false;
    };
  }, [selectedId, evReload]);

  const ev = evidence?.id === selectedId ? evidence : null;
  const meta = data?.search.meta;
  const loading = !current;
  const synthetic = meta?.data_status === "synthetic" || target.data_status === "synthetic";
  const preview = previewUrl(target.preview_url);
  const point = targetPoint(target);

  return (
    <main className="comparison-page">
      <button className="text-button back-link" onClick={onBack}>
        <ArrowLeft size={15} /> Back to exploration
      </button>
      <div className="comparison-heading">
        <div>
          <div className="eyebrow">
            <span /> TERRAIN ANALOG SEARCH
          </div>
          <h1>Different worlds. Similar terrain measurements.</h1>
          <p>
            Earth windows in {region.name} ranked by how closely their terrain measures like{" "}
            {target.name} at {target.comparison.scale_m} m.
          </p>
        </div>
        <span className="status-badge">
          <span /> {loading ? "SEARCHING" : current.error ? "SEARCH REFUSED" : "SEARCH COMPLETE"}
        </span>
      </div>

      <div className="analysis-banner">
        {loading ? <LoaderCircle className="spin" size={20} /> : <Radio size={20} />}
        <div>
          <strong>
            {loading
              ? `Scoring ${region.name} against ${target.name}…`
              : meta
                ? `${meta.target_name} vs ${meta.region_name} at ${meta.scale_m} m · ${meta.scoring_version}`
                : "The search did not complete."}
          </strong>
          <p>
            {meta
              ? `${meta.counts.eligible.toLocaleString()} of ${meta.counts.windows_in_region.toLocaleString()} windows eligible · ${meta.counts.excluded_missing_mandatory} excluded for missing data · shortlist ${meta.counts.shortlist} · ${meta.counts.groups} merged groups. Records checked: ${
                  meta.registry.registry_loaded
                    ? `${meta.registry.sources_checked.join(", ")} (${meta.registry.registry_version})`
                    : "none loaded"
                }.`
              : "Windows with too much water, built-up land or missing data are excluded before scoring."}
          </p>
        </div>
        <label className="banner-region">
          <span>EARTH REGION</span>
          <select
            value={region.id}
            onChange={(e) => onRegionChange(e.target.value)}
            aria-label="Earth search region"
          >
            {regions.map((r) => (
              <option key={r.id} value={r.id}>
                {r.name}
              </option>
            ))}
          </select>
        </label>
        <label className="banner-region banner-topk">
          <span>CANDIDATES</span>
          <select
            value={topK}
            onChange={(e) => setTopK(Number(e.target.value))}
            aria-label="Candidates to return"
          >
            {TOP_K_CHOICES.map((k) => (
              <option key={k} value={k}>
                Top {k}
              </option>
            ))}
          </select>
        </label>
        {meta && (
          <span className={`outline-tag ${synthetic ? "warn" : ""}`}>
            {synthetic ? "SYNTHETIC DEMO DATA" : "MEASURED DATA"}
          </span>
        )}
      </div>

      <div className="comparison-layout">
        <section className="panel ranked-panel">
          <div className="panel-heading">
            <h2>Earth candidates</h2>
            <span className="small-label">
              {data ? `${data.pagination.total} RESULTS` : loading ? "…" : "0 RESULTS"}
            </span>
          </div>
          <div className="result-toolbar">
            <SlidersHorizontal size={15} />
            <span>Ranked by configured similarity ({meta?.scoring_version ?? "terrain-v1"})</span>
          </div>
          {loading ? (
            <div className="empty-results">
              <div className="empty-icon">
                <LoaderCircle className="spin" size={28} />
              </div>
              <h3>Searching Earth windows…</h3>
            </div>
          ) : current.error ? (
            <div className="empty-results" role="alert">
              <div className="empty-icon">
                <TriangleAlert size={28} />
              </div>
              <h3>The search could not run.</h3>
              <p>{current.error}</p>
              <button className="secondary retry" onClick={() => setAttempt((n) => n + 1)}>
                <RotateCcw size={13} /> Retry
              </button>
            </div>
          ) : all.length === 0 ? (
            <div className="empty-results">
              <div className="empty-icon">
                <Earth size={31} />
              </div>
              <h3>No candidates passed the filters.</h3>
              <p>Try another Earth region.</p>
            </div>
          ) : (
            <div className="result-list" role="list">
              {data!.candidates.map((c) => (
                <ResultRow
                  key={c.id}
                  c={c}
                  active={c.id === selectedId}
                  onClick={() => setPicked({ key, id: c.id })}
                />
              ))}
              {data!.reference_matches.length > 0 && (
                <>
                  <span className="result-group">DOCUMENTED ANALOGS IN THE SHORTLIST</span>
                  {data!.reference_matches.map((c) => (
                    <ResultRow
                      key={c.id}
                      c={c}
                      active={c.id === selectedId}
                      onClick={() => setPicked({ key, id: c.id })}
                    />
                  ))}
                </>
              )}
            </div>
          )}
          {data && (
            <div className="export-row">
              <a className="secondary" href={exportUrl(data.search.id, "geojson")}>
                <Download size={12} /> GeoJSON
              </a>
              <a className="secondary" href={exportUrl(data.search.id, "csv")}>
                <Download size={12} /> CSV
              </a>
            </div>
          )}
          <div className="evidence-note">
            <CircleHelp size={16} />
            <p>
              Similarity describes terrain measurements, not habitability or geological origin.{" "}
              {SCORE_NOTE}
            </p>
          </div>
        </section>

        <section className="comparison-visuals">
          <div className="side-by-side">
            <div className="terrain-view">
              <div className="view-label">
                <span className="live-dot" /> PLANETARY TARGET
              </div>
              {preview ? (
                <img className="target-preview" src={preview} alt={`Hillshade of ${target.name}`} />
              ) : (
                <Globe planet={planet} selected={point} />
              )}
              <div className="terrain-caption">
                <strong>{target.name}</strong>
                <span>
                  {planet.name} · {coordinate(point.lat)} / {coordinate(point.lon, false)} ·{" "}
                  {preview
                    ? `hillshade of the preview area; the scored square is the central ${target.comparison.footprint_m / 1000} km`
                    : "illustrative texture, no preview image"}
                </span>
              </div>
            </div>
            <div className="terrain-view earth-view">
              <div className="view-label">
                <Earth size={13} /> EARTH CANDIDATES
              </div>
              <ResultsMap
                region={region}
                candidates={data?.candidates ?? []}
                references={data?.reference_matches ?? []}
                registry={registry}
                selectedId={selectedId}
                onSelect={(id) => setPicked({ key, id })}
              />
            </div>
          </div>

          <div className="panel metric-panel">
            <div className="panel-heading">
              <h2>
                <Layers3 size={16} /> Terrain signature
                {selected && <span className="heading-sub">candidate #{selected.rank}</span>}
              </h2>
              <span className="small-label">
                {ev?.ev
                  ? `${ev.ev.scale.scale_m} M PIXELS · ${ev.ev.scale.window_m / 1000} KM WINDOW · ${ev.ev.scale.feature_schema_version.toUpperCase()}`
                  : selected
                    ? "LOADING EVIDENCE"
                    : "NO MEASUREMENTS YET"}
              </span>
            </div>
            <div className="overall-similarity">
              <div>
                <span>CONFIGURED SIMILARITY ({meta?.scoring_version ?? "terrain-v1"})</span>
                <p>
                  {selected
                    ? `${NOVELTY_LABEL[selected.novelty_status]} · ${selected.members.length} window${selected.members.length > 1 ? "s" : ""} · centre ${selected.center.lat.toFixed(3)}°, ${selected.center.lon.toFixed(3)}°`
                    : "Not a probability. Select a candidate."}
                </p>
              </div>
              <strong aria-label="Configured similarity">
                {selected ? fmtScore(selected.score) : "—"}
                <small>{selected ? "out of 100" : "Awaiting results"}</small>
              </strong>
            </div>
            <div className="metric-table">
              <div className="metric-row metric-head">
                <span>METRIC</span>
                <span>{planet.name.toUpperCase()}</span>
                <span>EARTH</span>
                <span>TOLERANCE</span>
                <span>SIMILARITY</span>
              </div>
              {METRIC_ORDER.map((f) => {
                const c = selected?.components[f];
                const main = selected?.main_mismatch === f;
                return (
                  <div className={`metric-row ${main ? "is-mismatch" : ""}`} key={f}>
                    <span>
                      <Mountain size={14} />
                      {FEATURE_LABEL[f] ?? f}
                      {main && <em className="mismatch-tag">main mismatch</em>}
                    </span>
                    {c ? (
                      <>
                        <span>{metricValue(c, "target")}</span>
                        <span>{metricValue(c, "earth")}</span>
                        <span>
                          {Array.isArray(c.earth)
                            ? `W₁ ${fmtValue(c.difference, c.unit)} / ${fmtValue(c.tolerance, c.unit)}`
                            : `±${fmtValue(c.tolerance, c.unit)}`}
                        </span>
                        <span className={c.within_tolerance ? "ok" : "off"}>
                          {Math.round(c.similarity)}
                          <small>{c.within_tolerance ? " within" : " outside"}</small>
                        </span>
                      </>
                    ) : (
                      <>
                        <span>—</span>
                        <span>—</span>
                        <span>—</span>
                        <span className="metric-placeholder">
                          {selected ? "not available" : "Awaiting data"}
                        </span>
                      </>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          <div className="panel explanation-panel">
            <span className="insight-icon">
              <ArrowUpRight size={19} />
            </span>
            <div>
              <h3>{selected ? selected.explanation.summary : "The evidence comes first."}</h3>
              {selected ? (
                <>
                  {selected.explanation.main_mismatch && (
                    <p className="mismatch-line">{selected.explanation.main_mismatch}</p>
                  )}
                  {selected.explanation.lines.length > 0 && (
                    <ul>
                      {selected.explanation.lines.map((l) => (
                        <li key={l}>{l}</li>
                      ))}
                    </ul>
                  )}
                  {selected.explanation.not_available.length > 0 && (
                    <p>Not available: {selected.explanation.not_available.join(", ")}.</p>
                  )}
                </>
              ) : (
                <p>
                  Each match explains shared terrain features, the main difference and missing data.
                  Places absent from the checked registry are labelled &ldquo;not in checked
                  records&rdquo;, never &ldquo;discovered&rdquo;.
                </p>
              )}
            </div>
          </div>

          {selected && (
            <div className="panel evidence-panel">
              <div className="panel-heading">
                <h2>
                  <Layers3 size={16} /> Evidence
                </h2>
                {synthetic && (
                  <span className="small-label warn">SYNTHETIC — NOT MEASUREMENTS</span>
                )}
              </div>
              {ev?.error ? (
                <p className="ev-state" role="alert">
                  Evidence could not be loaded: {ev.error}{" "}
                  <button className="text-button" onClick={() => setEvReload((n) => n + 1)}>
                    Retry
                  </button>
                </p>
              ) : ev?.ev ? (
                <EvidenceDetails ev={ev.ev} onReload={() => setEvReload((n) => n + 1)} />
              ) : (
                <p className="ev-state">
                  <LoaderCircle className="spin" size={14} /> Loading evidence…
                </p>
              )}
            </div>
          )}

          {data && meta && (
            <Reweight
              key={data.search.id}
              searchId={data.search.id}
              defaults={meta.weights}
              scoringVersion={meta.scoring_version}
              candidateCells={new Map(all.map((c) => [c.best_cell_id, c.rank]))}
            />
          )}

          {meta && (
            <div className="panel provenance-panel">
              <div className="panel-heading">
                <h2>
                  <Layers3 size={16} /> Processing runs behind this search
                </h2>
                <span className="small-label">
                  SEARCH {data!.search.id.slice(0, 8).toUpperCase()}
                </span>
              </div>
              <div className="reweight-body">
                {typeof meta.provenance.earth_run_id === "string" && (
                  <RunDetails runId={meta.provenance.earth_run_id} label="Earth run" />
                )}
                {typeof meta.provenance.target_run_id === "string" && (
                  <RunDetails runId={meta.provenance.target_run_id} label="Target run" />
                )}
              </div>
            </div>
          )}
        </section>
      </div>
      <div className="comparison-footer">
        <Check size={14} /> Target {target.id} · {target.comparison.footprint_m / 1000} km footprint
        <span>
          Analysis window: {(meta?.window_m ?? 10_000) / 1000} km ·{" "}
          {meta?.scale_m ?? target.comparison.scale_m} m pixels ·{" "}
          {meta?.scoring_version ?? "terrain-v1"}
        </span>
      </div>
    </main>
  );
}

function ResultRow({ c, active, onClick }: { c: Candidate; active: boolean; onClick: () => void }) {
  const ref = c.list === "reference_matches";
  return (
    <button
      className={`result-item ${active ? "active" : ""}`}
      role="listitem"
      aria-current={active}
      onClick={onClick}
    >
      <span className="result-rank">{String(c.rank).padStart(2, "0")}</span>
      <span className="result-body">
        <strong>
          {ref
            ? (c.novelty.matched[0]?.name ?? "Documented analog")
            : NOVELTY_LABEL[c.novelty_status]}
        </strong>
        <small>
          {c.center.lat.toFixed(2)}°, {c.center.lon.toFixed(2)}° · main mismatch:{" "}
          {FEATURE_LABEL[c.main_mismatch ?? ""]?.toLowerCase() ?? "none"} · {c.members.length}{" "}
          window{c.members.length > 1 ? "s" : ""}
        </small>
      </span>
      <span className="result-score">{fmtScore(c.score)}</span>
    </button>
  );
}
