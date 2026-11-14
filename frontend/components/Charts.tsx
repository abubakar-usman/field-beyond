"use client";

import { useState } from "react";
import type { Component } from "@/lib/api";
import { FEATURE_HINT, FEATURE_LABEL, fmtValue } from "@/lib/copy";

/** One scalar feature: Earth and target positions on a shared axis, with the tolerance band. */
export function FeatureStrip({ c, isMain }: { c: Component; isMain: boolean }) {
  const earth = c.earth as number;
  const target = c.target as number;
  const lo = Math.min(earth, target - c.tolerance, 0);
  const hi = Math.max(earth, target + c.tolerance) * 1.05 || 1;
  const x = (v: number) => ((v - lo) / (hi - lo)) * 100;
  return (
    <div className="feature">
      <div className="feature-head">
        <span className="name" title={FEATURE_HINT[c.feature]}>
          {FEATURE_LABEL[c.feature] ?? c.feature}
          {isMain && (
            <span className="badge" style={{ marginLeft: 6 }}>
              main mismatch
            </span>
          )}
        </span>
        <span className="num">
          similarity <strong>{Math.round(c.similarity)}</strong>
        </span>
      </div>
      <svg
        viewBox="0 0 100 14"
        preserveAspectRatio="none"
        width="100%"
        height="14"
        role="img"
        aria-label={`Earth ${fmtValue(earth, c.unit)}, target ${fmtValue(target, c.unit)}, tolerance ±${fmtValue(c.tolerance, c.unit)}`}
      >
        <rect x="0" y="6" width="100" height="2" fill="var(--surface-2)" />
        <rect
          x={x(target - c.tolerance)}
          y="3"
          width={x(target + c.tolerance) - x(target - c.tolerance)}
          height="8"
          rx="2"
          fill="var(--target)"
          opacity="0.18"
        />
        <rect x={x(target) - 0.4} y="1" width="0.8" height="12" fill="var(--target)" />
        <circle
          cx={x(earth)}
          cy="7"
          r="3.2"
          fill="var(--earth)"
          stroke="var(--surface-1)"
          strokeWidth="1"
          vectorEffect="non-scaling-stroke"
        />
      </svg>
      <div className="feature-values num">
        <span>
          <span className="swatch" style={{ background: "var(--earth)" }} />
          Earth {fmtValue(earth, c.unit)}
        </span>
        <span>
          <span className="swatch" style={{ background: "var(--target)" }} />
          Target {fmtValue(target, c.unit)}
        </span>
        <span>difference {fmtValue(c.difference, c.unit)}</span>
        <span>
          tolerance ±{fmtValue(c.tolerance, c.unit)} ({c.within_tolerance ? "within" : "outside"})
        </span>
      </div>
    </div>
  );
}

/** Earth vs target slope histogram: paired bars per bin, unequal bin widths labelled. */
export function SlopeHistogram({
  earth,
  target,
  bins,
  component,
  isMain,
}: {
  earth: number[];
  target: number[];
  bins: number[];
  component: Component;
  isMain: boolean;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const max = Math.max(...earth, ...target, 0.01);
  const n = earth.length;
  const W = 320;
  const H = 120;
  const pad = { l: 28, r: 4, t: 6, b: 22 };
  const cw = (W - pad.l - pad.r) / n;
  const bw = Math.max(4, (cw - 6) / 2);
  const y = (v: number) => pad.t + (H - pad.t - pad.b) * (1 - v / max);
  return (
    <div className="feature">
      <div className="feature-head">
        <span className="name" title={FEATURE_HINT.slope_hist}>
          {FEATURE_LABEL.slope_hist}
          {isMain && (
            <span className="badge" style={{ marginLeft: 6 }}>
              main mismatch
            </span>
          )}
        </span>
        <span className="num">
          similarity <strong>{Math.round(component.similarity)}</strong>
        </span>
      </div>
      <div className="legend">
        <span>
          <span className="swatch" style={{ background: "var(--earth)" }} />
          Earth window
        </span>
        <span>
          <span className="swatch" style={{ background: "var(--target)" }} />
          Target
        </span>
      </div>
      <div style={{ position: "relative" }}>
        <svg
          viewBox={`0 0 ${W} ${H}`}
          width="100%"
          role="img"
          aria-label="Share of pixels per slope bin, Earth and target"
        >
          {[0, 0.5, 1].map((f) => (
            <g key={f}>
              <line
                x1={pad.l}
                x2={W - pad.r}
                y1={y(max * f)}
                y2={y(max * f)}
                stroke="var(--border)"
                strokeWidth="1"
              />
              <text
                x={pad.l - 4}
                y={y(max * f) + 3}
                fontSize="9"
                textAnchor="end"
                fill="var(--text-muted)"
              >
                {Math.round(max * f * 100)}%
              </text>
            </g>
          ))}
          {earth.map((e, i) => {
            const x0 = pad.l + i * cw + (cw - 2 * bw - 2) / 2;
            const t = target[i] ?? 0;
            return (
              <g key={i} onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}>
                <rect
                  x={pad.l + i * cw}
                  y={pad.t}
                  width={cw}
                  height={H - pad.t - pad.b}
                  fill="transparent"
                />
                <path
                  d={bar(x0, y(e), bw, y(0))}
                  fill="var(--earth)"
                  opacity={hover === null || hover === i ? 1 : 0.45}
                />
                <path
                  d={bar(x0 + bw + 2, y(t), bw, y(0))}
                  fill="var(--target)"
                  opacity={hover === null || hover === i ? 1 : 0.45}
                />
                <text
                  x={pad.l + i * cw + cw / 2}
                  y={H - 8}
                  fontSize="9"
                  textAnchor="middle"
                  fill="var(--text-muted)"
                >
                  {bins[i]}–{bins[i + 1]}°
                </text>
              </g>
            );
          })}
        </svg>
        {hover !== null && (
          <div className="tooltip" style={{ left: 8, top: 0 }}>
            {bins[hover]}–{bins[hover + 1]}°: Earth {((earth[hover] ?? 0) * 100).toFixed(1)}%,
            target {((target[hover] ?? 0) * 100).toFixed(1)}%
          </div>
        )}
      </div>
      <div className="feature-values num">
        <span>Wasserstein-1 distance {component.difference.toFixed(2)}°</span>
        <span>
          tolerance {component.tolerance}° ({component.within_tolerance ? "within" : "outside"})
        </span>
      </div>
      <details>
        <summary>Table</summary>
        <table className="num" style={{ width: "100%", fontSize: 12 }}>
          <thead>
            <tr>
              <th align="left">Slope bin</th>
              <th align="right">Earth</th>
              <th align="right">Target</th>
            </tr>
          </thead>
          <tbody>
            {earth.map((e, i) => (
              <tr key={i}>
                <td>
                  {bins[i]}–{bins[i + 1]}°
                </td>
                <td align="right">{(e * 100).toFixed(1)}%</td>
                <td align="right">{((target[i] ?? 0) * 100).toFixed(1)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </div>
  );
}

/** Bar with a 4px rounded top anchored on the baseline. */
function bar(x: number, top: number, w: number, base: number): string {
  const h = base - top;
  if (h <= 0.5) return `M${x},${base}h${w}v-0.5h${-w}z`;
  const r = Math.min(4, w / 2, h);
  return `M${x},${base}V${top + r}Q${x},${top} ${x + r},${top}H${x + w - r}Q${x + w},${top} ${x + w},${top + r}V${base}Z`;
}
