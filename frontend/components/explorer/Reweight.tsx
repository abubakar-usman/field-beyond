"use client";

// POST /searches/{id}/rescore: re-weight the stored shortlist only (D-020). The
// nearest-neighbour shortlist is not rebuilt, and the backend's note says so.
import { useState } from "react";
import { LoaderCircle, RotateCcw, SlidersHorizontal } from "lucide-react";
import { ApiError, api, type RescoreResponse } from "@/lib/api";
import { FEATURE_LABEL, fmtScore } from "@/lib/copy";

const SHOWN = 15;

export default function Reweight({
  searchId,
  defaults,
  scoringVersion,
  candidateCells,
}: {
  searchId: string;
  defaults: Record<string, number>;
  scoringVersion: string;
  /** Best window id → candidate rank, to show where re-weighted windows sit today. */
  candidateCells: Map<number, number>;
}) {
  const [weights, setWeights] = useState<Record<string, number>>(defaults);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<RescoreResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const changed = Object.keys(defaults).some((k) => weights[k] !== defaults[k]);

  async function run() {
    setBusy(true);
    setError(null);
    try {
      setResult(await api.rescore(searchId, weights));
    } catch (e) {
      setResult(null);
      setError(e instanceof ApiError ? `${e.code} (HTTP ${e.status})` : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="panel reweight-panel">
      <div className="panel-heading">
        <h2>
          <SlidersHorizontal size={16} /> Re-weight the shortlist
        </h2>
        <span className="small-label">
          {changed ? "CUSTOM WEIGHTS" : `${scoringVersion.toUpperCase()} DEFAULTS`}
        </span>
      </div>
      <div className="reweight-body">
        <div className="weight-grid">
          {Object.keys(defaults).map((k) => (
            <label key={k} className="weight-row">
              <span>{FEATURE_LABEL[k] ?? k}</span>
              <input
                type="range"
                min={0}
                max={3}
                step={0.1}
                value={weights[k] ?? 0}
                onChange={(e) => setWeights({ ...weights, [k]: Number(e.target.value) })}
                aria-label={`Weight for ${FEATURE_LABEL[k] ?? k}`}
              />
              <output>{(weights[k] ?? 0).toFixed(1)}</output>
            </label>
          ))}
        </div>
        <div className="reweight-actions">
          <button className="secondary" onClick={run} disabled={busy}>
            {busy ? <LoaderCircle className="spin" size={12} /> : <SlidersHorizontal size={12} />}{" "}
            Rescore shortlist
          </button>
          <button
            className="text-button"
            onClick={() => {
              setWeights(defaults);
              setResult(null);
            }}
            disabled={!changed && !result}
          >
            <RotateCcw size={11} /> Reset to defaults
          </button>
        </div>
        {error && (
          <p className="run-error" role="alert">
            Rescore refused: {error}
          </p>
        )}
        {result && (
          <>
            <p className="reweight-note">{result.note}</p>
            <div className="rescore-table" role="table">
              <div className="rescore-row head" role="row">
                <span>#</span>
                <span>WINDOW</span>
                <span>SCORE</span>
                <span>MAIN MISMATCH</span>
                <span>CURRENT RANK</span>
              </div>
              {result.windows.slice(0, SHOWN).map((w, i) => (
                <div className="rescore-row" role="row" key={w.cell_id}>
                  <span>{i + 1}</span>
                  <span className="mono">{w.cell_id}</span>
                  <span>{fmtScore(w.score)}</span>
                  <span>{FEATURE_LABEL[w.main_mismatch ?? ""] ?? "none"}</span>
                  <span>{candidateCells.get(w.cell_id) ?? "—"}</span>
                </div>
              ))}
            </div>
            <p className="reweight-note">
              Showing {Math.min(SHOWN, result.windows.length)} of {result.windows.length} shortlist
              windows. These are windows, not merged candidates; &ldquo;current rank&rdquo; is the
              candidate whose best window this is under the default weights.
            </p>
          </>
        )}
      </div>
    </div>
  );
}
