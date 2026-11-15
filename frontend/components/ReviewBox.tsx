"use client";

import { useState } from "react";
import { ApiError, api, type NoveltyStatus, type Review } from "@/lib/api";
import { NOVELTY_LABEL } from "@/lib/copy";

const NEXT: Record<NoveltyStatus, NoveltyStatus[]> = {
  not_in_checked_records: ["under_review", "promising", "rejected", "documented_analog"],
  under_review: ["promising", "rejected", "documented_analog"],
  promising: ["under_review", "rejected", "documented_analog"],
  rejected: ["under_review"],
  documented_analog: ["under_review"],
};

function storedToken(): string {
  try {
    return sessionStorage.getItem("eae-demo-token") ?? "";
  } catch {
    return "";
  }
}

export default function ReviewBox({
  candidateId,
  status,
  reviews,
  onDone,
}: {
  candidateId: string;
  status: NoveltyStatus;
  reviews: Review[];
  onDone: () => void;
}) {
  const options = NEXT[status];
  const [token, setToken] = useState(storedToken);
  const [reviewer, setReviewer] = useState("");
  const [decision, setDecision] = useState<NoveltyStatus>(options[0] ?? "under_review");
  const [note, setNote] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit() {
    setBusy(true);
    setMsg(null);
    try {
      try {
        sessionStorage.setItem("eae-demo-token", token);
      } catch {
        /* storage unavailable */
      }
      await api.review(candidateId, token, { reviewer_id: reviewer, decision, note });
      setNote("");
      setMsg("Saved.");
      onDone();
    } catch (e) {
      const status = e instanceof ApiError ? e.status : 0;
      setMsg(
        status === 503
          ? "Not saved: reviews are turned off because the API was started without DEMO_TOKEN. Start it with scripts/local/dev.ps1 -NoDocker (or Docker), then use the token from .env."
          : status === 401
            ? "Not saved: the demo token is missing or wrong. Use the DEMO_TOKEN value from .env."
            : `Not saved: ${(e as Error).message}`,
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="section">
      <h3>Review</h3>
      {reviews.length > 0 && (
        <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12 }}>
          {reviews.map((r) => (
            <li key={r.id}>
              {r.reviewer_id}: {NOVELTY_LABEL[r.previous_status]} → {NOVELTY_LABEL[r.decision]}
              {r.note && <span className="muted"> — {r.note}</span>}
            </li>
          ))}
        </ul>
      )}
      <div className="field">
        <label htmlFor="rv-decision">Decision</label>
        <select
          id="rv-decision"
          value={decision}
          onChange={(e) => setDecision(e.target.value as NoveltyStatus)}
        >
          {options.map((o) => (
            <option key={o} value={o}>
              {NOVELTY_LABEL[o]}
            </option>
          ))}
        </select>
      </div>
      <div className="field">
        <label htmlFor="rv-name">Reviewer name</label>
        <input
          id="rv-name"
          type="text"
          value={reviewer}
          onChange={(e) => setReviewer(e.target.value)}
        />
      </div>
      <div className="field">
        <label htmlFor="rv-note">Note</label>
        <textarea id="rv-note" rows={2} value={note} onChange={(e) => setNote(e.target.value)} />
      </div>
      <div className="field">
        <label htmlFor="rv-token">Demo token</label>
        <input
          id="rv-token"
          type="password"
          autoComplete="off"
          value={token}
          onChange={(e) => setToken(e.target.value)}
        />
      </div>
      <button className="btn" disabled={busy || !reviewer || !token} onClick={submit}>
        Save review
      </button>
      {msg && (
        <p className="muted" style={{ margin: 0 }} role="status">
          {msg}
        </p>
      )}
    </div>
  );
}
