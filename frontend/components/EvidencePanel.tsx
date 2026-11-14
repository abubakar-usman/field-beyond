"use client";

// The hero of the app. Every candidate view shows: scale, each feature with both
// values and the tolerance, the main mismatch, missing data, the novelty label with
// the records checked, and the scoring version (scientific-copy skill).
import { useEffect, useState } from "react";
import { FeatureStrip, SlopeHistogram } from "./Charts";
import ReviewBox from "./ReviewBox";
import { api, previewUrl, type Evidence } from "@/lib/api";
import { BODY_LABEL, FLAG_LABEL, NOVELTY_LABEL, SCORE_NOTE, fmtPct, fmtScore } from "@/lib/copy";

const SCALAR_ORDER = ["slope_median", "slope_p90", "relief", "roughness"];

export default function EvidencePanel({
  candidateId,
  onClose,
}: {
  candidateId: string;
  onClose: () => void;
}) {
  // Keyed by candidate so a stale response or error never shows for another candidate.
  const [loaded, setLoaded] = useState<{ id: string; ev?: Evidence; error?: string } | null>(null);
  const [reload, setReload] = useState(0);

  useEffect(() => {
    let live = true;
    api
      .evidence(candidateId)
      .then((ev) => live && setLoaded({ id: candidateId, ev }))
      .catch((err: Error) => live && setLoaded({ id: candidateId, error: err.message }));
    return () => {
      live = false;
    };
  }, [candidateId, reload]);

  const current = loaded?.id === candidateId ? loaded : null;
  const ev = current?.ev ?? null;
  const error = current?.error ?? null;
  if (error)
    return (
      <aside className="evidence">
        <div className="error">Evidence could not be loaded: {error}</div>
      </aside>
    );
  if (!ev || ev.candidate.id !== candidateId)
    return (
      <aside className="evidence">
        <p className="empty">Loading evidence…</p>
      </aside>
    );

  const c = ev.candidate;
  const comps = c.components;
  const hist = comps.slope_hist;
  const earthHist =
    (ev.earth_profile?.values.slope_hist as number[] | null) ?? (hist?.earth as number[]);
  const targetHist = hist?.target as number[];
  const preview = previewUrl(ev.target.preview_url);
  const synthetic = ev.data_status === "synthetic";
  const nov = ev.novelty;

  return (
    <aside className="evidence" aria-label="Evidence for the selected candidate">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2>
          {c.list === "reference_matches" ? "Reference match" : "Candidate"} #{c.rank}
        </h2>
        <button className="btn" onClick={onClose} aria-label="Close evidence panel">
          Close
        </button>
      </div>

      {synthetic && (
        <div className="banner" role="note">
          Synthetic demo data: these numbers come from generated terrain, not from measured DEMs.
        </div>
      )}

      <div className="section">
        <div className="hero-score">
          <span className="value">{fmtScore(c.score)}</span>
          <span className="secondary">configured similarity ({ev.scale.scoring_version})</span>
        </div>
        <p className="muted" style={{ margin: 0, fontSize: 12 }}>
          {SCORE_NOTE}
        </p>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          <span className={`badge ${nov.status}`}>{NOVELTY_LABEL[nov.status]}</span>
          <span className="badge">{ev.scale.scale_m} m pixels</span>
          <span className="badge">{ev.scale.window_m / 1000} km window</span>
          <span className="badge">{ev.scale.feature_schema_version}</span>
        </div>
        <p style={{ margin: 0 }}>{c.explanation.summary}</p>
        {c.explanation.main_mismatch && (
          <p className="mismatch" style={{ margin: 0 }}>
            {c.explanation.main_mismatch}
          </p>
        )}
      </div>

      <div className="compare">
        <figure>
          {preview ? (
            <img src={preview} alt={`Hillshade of ${ev.target.name}`} />
          ) : (
            <div className="noimg card">No preview</div>
          )}
          <figcaption>
            {BODY_LABEL[ev.target.body]} target: {ev.target.name}. Hillshade of the preview area;
            the scored square is the central 10 km.
          </figcaption>
        </figure>
        <figure>
          <dl className="kv num" style={{ margin: 0 }}>
            <dt>Centre</dt>
            <dd>
              {c.center.lat.toFixed(3)}°, {c.center.lon.toFixed(3)}°
            </dd>
            <dt>Windows</dt>
            <dd>{c.members.length} × 10 km</dd>
            <dt>Best window</dt>
            <dd className="mono">{c.best_cell_id}</dd>
          </dl>
          <figcaption>
            Earth candidate (shown on the map; Earth hillshade not generated yet).
          </figcaption>
        </figure>
      </div>

      <div className="section">
        <h3>Terrain measurements</h3>
        {hist && earthHist && targetHist && (
          <SlopeHistogram
            earth={earthHist}
            target={targetHist}
            bins={ev.slope_hist_bins_deg}
            component={hist}
            isMain={c.main_mismatch === "slope_hist"}
          />
        )}
        {SCALAR_ORDER.filter((f) => comps[f]).map((f) => (
          <FeatureStrip key={f} c={comps[f]!} isMain={c.main_mismatch === f} />
        ))}
        <details>
          <summary>Weights ({ev.scale.scoring_version} defaults)</summary>
          <dl className="kv num">
            {Object.entries(ev.weights).map(([k, w]) => (
              <span key={k} style={{ display: "contents" }}>
                <dt>{k}</dt>
                <dd>{w}</dd>
              </span>
            ))}
          </dl>
        </details>
      </div>

      <div className="section">
        <h3>Missing or unavailable evidence</h3>
        <ul style={{ margin: 0, paddingLeft: 18 }}>
          {ev.unavailable_evidence.map((u) => (
            <li key={u}>{u}: not available</li>
          ))}
          {ev.missing_profiles.length > 0 && (
            <li>{ev.missing_profiles.length} member window profile(s): not available</li>
          )}
          <li>
            Optional evidence beyond terrain (geology, thermal, mineralogy): not part of{" "}
            {ev.scale.scoring_version}
          </li>
        </ul>
        <dl className="kv num">
          {Object.entries(FLAG_LABEL).map(([k, label]) => (
            <span key={k} style={{ display: "contents" }}>
              <dt>{label}</dt>
              <dd>{fmtPct(c.flags[k])}</dd>
            </span>
          ))}
        </dl>
      </div>

      <div className="section">
        <h3>Records checked</h3>
        {nov.registry_loaded ? (
          <>
            <p style={{ margin: 0 }}>
              {nov.status === "documented_analog"
                ? "Overlaps a documented analog in the checked records:"
                : "No overlap with the checked records."}
            </p>
            {nov.matched.length > 0 && (
              <ul style={{ margin: 0, paddingLeft: 18 }}>
                {nov.matched.map((m) => (
                  <li key={m.id}>
                    {m.name} <span className="muted">({m.source})</span>
                  </li>
                ))}
              </ul>
            )}
            <dl className="kv">
              <dt>Registry</dt>
              <dd>{nov.registry_version}</dd>
              <dt>Sources</dt>
              <dd>{nov.sources_checked.join(", ")}</dd>
              <dt>Review date</dt>
              <dd>{nov.review_date}</dd>
            </dl>
          </>
        ) : (
          <p style={{ margin: 0 }}>
            No known-analog registry is loaded, so no records were checked. &ldquo;Not in checked
            records&rdquo; here means only that.
          </p>
        )}
      </div>

      <div className="section">
        <h3>Member windows</h3>
        <ul style={{ margin: 0, paddingLeft: 18 }} className="num">
          {c.members.map((m) => (
            <li key={m.cell_id}>
              <span className="mono">{m.cell_id}</span>: {fmtScore(m.score)}
            </li>
          ))}
        </ul>
      </div>

      <div className="section">
        <h3>Sources and versions</h3>
        <dl className="kv">
          {Object.entries(ev.provenance).map(([k, v]) => (
            <span key={k} style={{ display: "contents" }}>
              <dt>{k.replaceAll("_", " ")}</dt>
              <dd className="mono">
                {Array.isArray(v) ? (v.length ? `${v.length} asset(s)` : "none") : String(v ?? "—")}
              </dd>
            </span>
          ))}
          <dt>target run</dt>
          <dd className="mono">{ev.target.run_id}</dd>
        </dl>
      </div>

      <ReviewBox
        candidateId={c.id}
        status={nov.status}
        reviews={ev.reviews}
        onDone={() => setReload((n) => n + 1)}
      />
    </aside>
  );
}
