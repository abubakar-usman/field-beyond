"use client";

// GET /processing-runs/{id}: provenance of a pipeline run (code version, config hash, sources).
import { useState } from "react";
import { ChevronDown, LoaderCircle } from "lucide-react";
import { api } from "@/lib/api";

function show(v: unknown): string {
  if (v === null || v === undefined || v === "") return "—";
  if (Array.isArray(v)) return v.length ? v.map((x) => show(x)).join(", ") : "none";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

export default function RunDetails({
  runId,
  label = "Processing run",
}: {
  runId: string;
  label?: string;
}) {
  const [state, setState] = useState<{ data?: Record<string, unknown>; error?: string } | null>(
    null,
  );
  const [open, setOpen] = useState(false);

  function toggle() {
    const next = !open;
    setOpen(next);
    if (next && !state)
      api
        .run(runId)
        .then((data) => setState({ data }))
        .catch((e: unknown) => setState({ error: e instanceof Error ? e.message : String(e) }));
  }

  return (
    <div className="run-details">
      <button className="text-button" onClick={toggle} aria-expanded={open}>
        <ChevronDown size={11} className={open ? "" : "-rotate-90"} /> {label}{" "}
        <span className="mono">{runId}</span>
      </button>
      {open &&
        (state?.error ? (
          <p className="run-error" role="alert">
            Run record not available: {state.error}
          </p>
        ) : state?.data ? (
          <dl className="run-kv">
            {Object.entries(state.data).map(([k, v]) => (
              <span key={k} style={{ display: "contents" }}>
                <dt>{k.replaceAll("_", " ")}</dt>
                <dd className="mono">{show(v)}</dd>
              </span>
            ))}
          </dl>
        ) : (
          <p className="run-error">
            <LoaderCircle className="spin" size={11} /> Loading run…
          </p>
        ))}
    </div>
  );
}
