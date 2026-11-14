# Scoring

How a match score is computed. Scoring version: **terrain-v1**. Config file (planned): `config/scoring/terrain-v1.yaml`.

> The score is a **configured similarity**: it says how close the measurements are under the tolerances below. It is **not** a probability that the place is a good analog.

## Features (computed identically for Earth windows and planetary targets)

| Key | Meaning | Unit | How |
|---|---|---|---|
| `slope_median` | Typical steepness | degrees | Horn's method on the projected DEM using the body's true pixel size; median over valid pixels |
| `slope_p90` | Steep-end steepness | degrees | 90th percentile of slope |
| `slope_hist` | Steepness distribution | fractions per bin | Bins: 0–2, 2–5, 5–10, 10–15, 15–20, 20–30, 30–45, 45–90° |
| `relief` | Height range | metres | 95th − 5th percentile elevation in the window |
| `roughness` | Bumpiness after removing overall tilt | metres | Standard deviation of residuals after least-squares plane fit; scale = window size at comparison resolution (record it) |
| `valid_fraction` | Share of usable pixels | 0–1 | Used for eligibility only, not scored |

Comparison resolution: 200 m for Mars targets, 59 m for Moon targets. Earth DEM is aggregated down to match; never upsampled.

## Per-feature similarity (design §9.1)

```
difference_i = |earth_i − target_i|
similarity_i = 100 × max(0, 1 − difference_i / tolerance_i)
```

For the histogram: `difference = Wasserstein-1 distance between the two slope distributions (in degrees)` (decision D-012).

## Starting tolerances and weights (to be tuned; every change bumps the version)

| Feature | Tolerance | Weight |
|---|---|---|
| `slope_hist` | 5° (Wasserstein-1) | 0.30 |
| `slope_median` | 5° | 0.20 |
| `slope_p90` | 8° | 0.15 |
| `relief` | 50% of the target's relief | 0.20 |
| `roughness` | 50% of the target's roughness | 0.15 |

Relative tolerances (relief, roughness) are converted to absolute values once per target and stored with the result.

## Combining

```
total = Σ (weight_i × similarity_i) / Σ weight_i     over mandatory features available on BOTH sides
```

**Missing-data rule:** if a window is missing any *mandatory* feature, it is **excluded**, not scored on the rest. Optional features (e.g. geology later) are shown separately and never raise the terrain score. This prevents windows from ranking high just because hard-to-measure features are absent (design §8 step 6).

## Eligibility (before scoring)

| Rule | Starting value |
|---|---|
| `valid_fraction` | ≥ 0.90 |
| Water share (WorldCover) | ≤ 5% |
| Built-up share | ≤ 2% |
| Snow/ice, vegetation | Flags shown in evidence; exclusion depends on the chosen purpose |

## Retrieval (shortlist before scoring)
Standardize scalar features with z-scores computed over the region's eligible windows (store the means/stds with the index version); nearest neighbours to the target vector; shortlist `10 × top_k`; then score as above and sort.

## Grouping
Non-maximum suppression over overlapping windows (IoU > 0.3 → keep the higher score), then merge touching survivors into candidate regions. Candidate score = best member score; all member windows and their scores are kept and shown.

## Explanations (deterministic templates)
For each feature: Earth value, target value, difference, within/outside tolerance. The largest gap is labelled "main mismatch". Unavailable features are listed as "not available", never hidden.

## Changing the scoring
1. Copy `terrain-v1.yaml` → `terrain-v2.yaml`; never edit a released version in place.
2. Re-run the benchmark notebook (Atacama known-analog ranking + negative controls) and note the result in CHANGELOG.md.
3. Cache keys include the scoring version, so old results are never silently reused.

## Adding a feature
Implement it in `core/features/`, add a synthetic-DEM test with a known answer for all three bodies, add it to the feature schema version, add a tolerance + weight in a new scoring version, update this file. See `.claude/skills/geo-pipeline/SKILL.md`.
