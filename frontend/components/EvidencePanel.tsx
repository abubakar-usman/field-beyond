"use client";

// Full evidence for one candidate (the hero of the comparison screen). With the metric
// table above it, the candidate view shows: scale, each feature with both values and the
// tolerance, the main mismatch, missing data, the novelty label with the records checked,
// and the scoring version (scientific-copy skill).
import { FeatureStrip, SlopeHistogram } from "./Charts";
import ReviewBox from "./ReviewBox";
import type { Evidence } from "@/lib/api";
import { FLAG_LABEL, NOVELTY_LABEL, fmtPct, fmtScore } from "@/lib/copy";

const SCALAR_ORDER = ["slope_median", "slope_p90", "relief", "roughness"];

export default function EvidenceDetails({ ev, onReload }: { ev: Evidence; onReload: () => void }) {
  const c = ev.candidate;
  const comps = c.components;
  const hist = comps.slope_hist;
  const earthHist =
    (ev.earth_profile?.values.slope_hist as number[] | null) ?? (hist?.earth as number[]);
  const targetHist = hist?.target as number[];
  const nov = ev.novelty;

  return (
    <div className="ev" aria-label="Evidence for the selected candidate">
      <div className="section">
        <h3>Measurements against tolerance</h3>
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
        <ul>
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
        <h3>Records checked · {NOVELTY_LABEL[nov.status]}</h3>
        {nov.registry_loaded ? (
          <>
            <p>
              {nov.status === "documented_analog"
                ? "Overlaps a documented analog in the checked records:"
                : "No overlap with the checked records."}
            </p>
            {nov.matched.length > 0 && (
              <ul>
                {nov.matched.map((m) => (
                  <li key={m.id}>
                    {m.name} <span className="muted-ev">({m.source})</span>
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
          <p>
            No known-analog registry is loaded, so no records were checked. &ldquo;Not in checked
            records&rdquo; here means only that.
          </p>
        )}
      </div>

      <div className="section">
        <h3>Member windows</h3>
        <ul className="num">
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

      <ReviewBox candidateId={c.id} status={nov.status} reviews={ev.reviews} onDone={onReload} />
    </div>
  );
}
