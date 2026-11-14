"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import EvidencePanel from "@/components/EvidencePanel";
import {
  ApiError,
  api,
  exportUrl,
  previewUrl,
  type CandidatesResponse,
  type Region,
  type RegistryResponse,
  type Target,
} from "@/lib/api";
import { BODY_LABEL, FEATURE_LABEL, NOVELTY_LABEL, fmtScore } from "@/lib/copy";

const ResultsMap = dynamic(() => import("@/components/ResultsMap"), { ssr: false });

function errorText(e: unknown): string {
  if (e instanceof ApiError) {
    if (e.code === "features_not_ready")
      return `No features yet for this region at ${String(e.detail.scale_m)} m. Run the pipeline (or seed-fake) for that scale.`;
    if (e.code === "target_not_ready")
      return "This target has no profile yet. Run `pipeline target`.";
    if (e.code === "features_checksum_mismatch")
      return "The feature file does not match its processing run, so the search was refused.";
    return `${e.code} (HTTP ${e.status})`;
  }
  return e instanceof Error ? e.message : String(e);
}

export default function Home() {
  const [targets, setTargets] = useState<Target[]>([]);
  const [regions, setRegions] = useState<Region[]>([]);
  const [registry, setRegistry] = useState<RegistryResponse | null>(null);
  const [targetId, setTargetId] = useState("mars_jezero");
  const [regionId, setRegionId] = useState("earth_sahara");
  const [topK, setTopK] = useState(20);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<CandidatesResponse | null>(null);
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.targets(), api.regions(), api.registry()])
      .then(([t, r, g]) => {
        setTargets(t);
        setRegions(r);
        setRegistry(g);
      })
      .catch((e) => setError(`The API is not reachable: ${errorText(e)}`));
  }, []);

  const target = targets.find((t) => t.id === targetId) ?? null;
  const region = regions.find((r) => r.id === regionId) ?? null;
  const scaleStatus =
    target && region ? region.scales[String(target.comparison.scale_m)] : undefined;
  const synthetic = useMemo(
    () => target?.data_status === "synthetic" || scaleStatus?.data_status === "synthetic",
    [target, scaleStatus],
  );

  async function runSearch() {
    setBusy(true);
    setError(null);
    setSelected(null);
    try {
      const s = await api.search({ target_id: targetId, region_id: regionId, top_k: topK });
      setResult(await api.candidates(s.search_id));
    } catch (e) {
      setResult(null);
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }

  const meta = result?.search.meta;
  return (
    <div className={`shell${selected ? " with-evidence" : ""}`}>
      <header className="topbar">
        <h1>Earth Analog Explorer</h1>
        <span className="muted" style={{ fontSize: 12 }}>
          Terrain resemblance to Moon and Mars targets
        </span>
        <nav>
          <Link href="/about">Method &amp; data credits</Link>
        </nav>
      </header>

      <aside className="sidebar">
        <div className="section">
          <h3>1 · Target</h3>
          <div className="targets" role="group" aria-label="Planetary target">
            {targets.map((t) => {
              const src = previewUrl(t.preview_url);
              return (
                <button
                  key={t.id}
                  className="card"
                  aria-pressed={t.id === targetId}
                  onClick={() => setTargetId(t.id)}
                >
                  {src ? (
                    <img src={src} alt={`Hillshade of ${t.name}`} />
                  ) : (
                    <div className="noimg">No preview</div>
                  )}
                  <div className="meta">
                    <strong>{t.name}</strong>
                    <span>
                      {BODY_LABEL[t.body]} · {t.comparison.scale_m} m ·{" "}
                      {t.comparison.footprint_m / 1000} km
                    </span>
                    {t.data_status === "synthetic" && (
                      <span className="badge synthetic">synthetic</span>
                    )}
                    {t.profile_status !== "ready" && <span className="badge">no profile</span>}
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        <div className="section">
          <h3>2 · Earth region</h3>
          <div className="field">
            <label htmlFor="region">Pilot region</label>
            <select id="region" value={regionId} onChange={(e) => setRegionId(e.target.value)}>
              {regions.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.name} ({r.role})
                </option>
              ))}
            </select>
          </div>
          {region && (
            <p className="muted" style={{ margin: 0, fontSize: 12 }}>
              {region.description}
            </p>
          )}
          <div className="field">
            <label htmlFor="topk">Candidates to return</label>
            <input
              id="topk"
              type="number"
              min={1}
              max={100}
              value={topK}
              onChange={(e) => setTopK(Math.max(1, Math.min(100, Number(e.target.value) || 1)))}
            />
          </div>
          <p className="muted" style={{ margin: 0, fontSize: 12 }}>
            Purpose: exposed terrain. Windows with too much water, built-up land or missing data are
            excluded before scoring.
          </p>
          <button className="btn primary" onClick={runSearch} disabled={busy || !target || !region}>
            {busy ? "Searching…" : "Search"}
          </button>
          {scaleStatus?.status === "not_ready" && target && (
            <p className="muted" style={{ margin: 0, fontSize: 12 }}>
              No {target.comparison.scale_m} m features for this region yet.
            </p>
          )}
          {synthetic && (
            <div className="banner">
              Synthetic demo data is loaded. Results are not measurements.
            </div>
          )}
          {error && (
            <div className="error" role="alert">
              {error}
            </div>
          )}
        </div>

        {result && meta && (
          <div className="section">
            <h3>3 · Results</h3>
            <p className="muted" style={{ margin: 0, fontSize: 12 }}>
              {meta.target_name} vs {meta.region_name} at {meta.scale_m} m ·{" "}
              {meta.counts.eligible.toLocaleString()} of{" "}
              {meta.counts.windows_in_region.toLocaleString()} windows eligible · shortlist{" "}
              {meta.counts.shortlist} · {meta.scoring_version}
            </p>
            {result.candidates.length === 0 && (
              <p className="empty">No candidates passed the filters.</p>
            )}
            <div className="list" role="list">
              {result.candidates.map((c) => (
                <button
                  key={c.id}
                  className="row"
                  role="listitem"
                  aria-current={c.id === selected}
                  onClick={() => setSelected(c.id)}
                >
                  <span className="rank">{c.rank}</span>
                  <span>
                    <span>{NOVELTY_LABEL[c.novelty_status]}</span>
                    <span className="sub" style={{ display: "block" }}>
                      main mismatch: {FEATURE_LABEL[c.main_mismatch ?? ""]?.toLowerCase() ?? "none"}{" "}
                      · {c.members.length} window{c.members.length > 1 ? "s" : ""}
                    </span>
                  </span>
                  <span className="score">{fmtScore(c.score)}</span>
                </button>
              ))}
            </div>
            {result.reference_matches.length > 0 && (
              <>
                <h3 style={{ marginTop: 8 }}>Documented analogs in the shortlist</h3>
                <div className="list" role="list">
                  {result.reference_matches.map((c) => (
                    <button
                      key={c.id}
                      className="row"
                      role="listitem"
                      aria-current={c.id === selected}
                      onClick={() => setSelected(c.id)}
                    >
                      <span className="rank">{c.rank}</span>
                      <span>
                        {c.novelty.matched[0]?.name ?? "Documented analog"}
                        <span className="sub" style={{ display: "block" }}>
                          {c.novelty.matched[0]?.source}
                        </span>
                      </span>
                      <span className="score">{fmtScore(c.score)}</span>
                    </button>
                  ))}
                </div>
              </>
            )}
            <p className="muted" style={{ margin: 0, fontSize: 12 }}>
              Scores are configured similarity, not probability. Records checked:{" "}
              {meta.registry.registry_loaded
                ? `${meta.registry.sources_checked.join(", ")} (${meta.registry.registry_version})`
                : "none loaded"}
              .
            </p>
            <div style={{ display: "flex", gap: 8 }}>
              <a className="btn" href={exportUrl(result.search.id, "geojson")}>
                Export GeoJSON
              </a>
              <a className="btn" href={exportUrl(result.search.id, "csv")}>
                Export CSV
              </a>
            </div>
          </div>
        )}
      </aside>

      <ResultsMap
        region={region}
        candidates={result?.candidates ?? []}
        references={result?.reference_matches ?? []}
        registry={registry}
        selectedId={selected}
        onSelect={setSelected}
      />

      {selected && <EvidencePanel candidateId={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}
