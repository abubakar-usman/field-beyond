"use client";

// GET /targets/{id}: the scored terrain profile of the selected target (both sides of every
// comparison use these numbers). Missing values are shown as "not available", never filled.
import { useEffect, useState } from "react";
import RunDetails from "./RunDetails";
import { api, type TargetDetail } from "@/lib/api";
import { FEATURE_LABEL, fmtValue } from "@/lib/copy";

const ORDER = ["slope_median", "slope_p90", "relief", "roughness", "valid_fraction"];

function unitOf(feature: string): string {
  if (feature.startsWith("slope")) return "deg";
  if (feature === "relief" || feature === "roughness") return "m";
  return "";
}

export default function TargetProfile({ targetId }: { targetId: string }) {
  const [loaded, setLoaded] = useState<{ id: string; t?: TargetDetail; error?: string } | null>(
    null,
  );

  useEffect(() => {
    let live = true;
    api
      .target(targetId)
      .then((t) => live && setLoaded({ id: targetId, t }))
      .catch((e: unknown) => live && setLoaded({ id: targetId, error: String(e) }));
    return () => {
      live = false;
    };
  }, [targetId]);

  const current = loaded?.id === targetId ? loaded : null;
  if (!current) return <p className="profile-note">Loading terrain profile…</p>;
  if (current.error) return <p className="profile-note">Profile not available: {current.error}</p>;
  const p = current.t?.profile;
  if (!p) return <p className="profile-note">No terrain profile yet for this target.</p>;
  const hist = p.values.slope_hist;

  return (
    <div className="target-profile">
      <span className="profile-title">
        TERRAIN PROFILE · {current.t!.comparison.scale_m} M · {p.schema_version}
      </span>
      <dl className="run-kv">
        {ORDER.filter((f) => f in p.values).map((f) => {
          const v = p.values[f];
          const ok = p.availability[f] !== false && v !== null && v !== undefined;
          return (
            <span key={f} style={{ display: "contents" }}>
              <dt>{FEATURE_LABEL[f] ?? f}</dt>
              <dd>
                {!ok
                  ? "not available"
                  : f === "valid_fraction"
                    ? `${((v as number) * 100).toFixed(1)}%`
                    : fmtValue(v as number, unitOf(f))}
              </dd>
            </span>
          );
        })}
        <dt>Slope distribution</dt>
        <dd>{Array.isArray(hist) ? `${hist.length}-bin histogram` : "not available"}</dd>
        <dt>CRS</dt>
        <dd className="mono">{p.crs}</dd>
        <dt>Source assets</dt>
        <dd>{p.source_asset_ids.length || "none recorded"}</dd>
      </dl>
      <RunDetails runId={p.run_id} label="Target run" />
    </div>
  );
}
