# Scoring

How a match score is computed. Scoring version: **terrain-v1**.

Authoritative numbers: [`config/scoring/terrain-v1.yaml`](../config/scoring/terrain-v1.yaml). If a number in this file disagrees with that yaml, the yaml wins. Windows, regions, and target footprints live in [`config/grids/pilot-v1.yaml`](../config/grids/pilot-v1.yaml) and [`config/targets/`](../config/targets/).

> The score is a **configured similarity**: it says how close the measurements are under the tolerances below. It is **not** a probability that the place is a good analog.

## Features (computed identically for Earth windows and planetary targets)

| Key | Meaning | Unit | How |
|---|---|---|---|
| `slope_median` | Typical steepness | degrees | Horn's method on the projected DEM using the body's true pixel size; median over valid pixels |
| `slope_p90` | Steep-end steepness | degrees | 90th percentile of slope |
| `slope_hist` | Steepness distribution | fractions per bin | Bins (degrees): 0–2, 2–5, 5–10, 10–15, 15–20, 20–30, 30–45, 45–90 |
| `relief` | Height range | metres | 95th − 5th percentile elevation in the window |
| `roughness` | Bumpiness after removing overall tilt | metres | Standard deviation of residuals after least-squares plane fit; scale = window size at comparison resolution (record it) |
| `valid_fraction` | Share of usable pixels | 0–1 | Used for eligibility only, not scored |

Comparison grids: **200 m** for Mars targets, **60 m** for Moon targets. Earth DEM is aggregated down to that grid. The Moon *product* is SLDEM2015 at about 59 m; the comparison grid is 60 m so neither axis is upsampled at Taurus–Littrow (decision D-023).

Each Earth cell has two profiles, one per `scale_m`. A Jezero search uses the 200 m profile only. A Taurus–Littrow search uses the 60 m profile only.

The scored target footprint is **10 km**, the same size as an Earth window. Wider preview boxes in the target yaml are hillshades, not the profile that gets scored.

## Per-feature similarity (design §9.1)

```
difference_i = |earth_i − target_i|
similarity_i = 100 × max(0, 1 − difference_i / tolerance_i)
```

For the histogram, `difference` is the Wasserstein-1 distance in degrees:

```
difference = ∫ from 0° to 90° of |CDF_earth(s) − CDF_target(s)| ds
```

The CDFs are built from the histogram bins above. The ground distance is degrees, not bin index. The last bin is 45° wide, so a bin-index distance would not match the 5° tolerance.

## Starting tolerances and weights

| Feature | Tolerance | Weight |
|---|---|---|
| `slope_hist` | 5° (Wasserstein-1) | 0.30 |
| `slope_median` | 5° | 0.20 |
| `slope_p90` | 8° | 0.15 |
| `relief` | max(50% of the target's relief, 20 m) | 0.20 |
| `roughness` | max(50% of the target's roughness, 2 m) | 0.15 |

The floors stop a nearly flat target from driving the tolerance to zero. The absolute tolerance used for a target is stored with the result.

Slope median, slope p90, and the slope histogram share 0.65 of the weight and move together. That is accepted for terrain-v1. The Atacama benchmark is where we see whether relief and roughness are under-weighted. Changing a weight means a new yaml version, not an edit to this one.

## Combining

```
total = Σ (weight_i × similarity_i) / Σ weight_i     over mandatory features available on BOTH sides
```

**Missing-data rule:** if a window is missing any *mandatory* feature, it is **excluded**, not scored on the rest. A feature is missing when its value is null or its availability flag is false. Optional features (geology, later) are shown separately and never raise the terrain score.

## Eligibility (before scoring)

Purpose for the hackathon: `exposed_terrain`.

| Rule | Starting value |
|---|---|
| `valid_fraction` | ≥ 0.90 |
| Water share (WorldCover class 80, counted at native 10 m) | ≤ 5% |
| Built-up share (class 50, native 10 m) | ≤ 2% |
| Snow/ice (class 70) and vegetation (classes 10, 20, 30, 40, 95, 100) | Flags in the evidence panel. `exposed_terrain` does not drop them |

Land-cover fractions are counts of 10 m pixels inside the window. They are not taken from a land-cover raster that was first resampled onto the DEM grid.

## Retrieval (shortlist before scoring)

The in-memory tree uses four scalars only: `slope_median`, `slope_p90`, `relief`, `roughness`. Each is a z-score using the mean and standard deviation of **eligible windows in the region being searched**. Those means and standard deviations are stored with the index version. Regions are not pooled.

`slope_hist` is not in the tree. It is applied at rerank. The shortlist is `10 × top_k` (default `top_k` 20, so 200 windows) so a window the histogram would like is likely to still be in the shortlist. Weight sliders rescore that shortlist. They do not run a new nearest-neighbour search, and the UI says so.

## Grouping

Greedy non-maximum suppression, then a merge:

1. Sort by score descending, then by `cell_id` ascending.
2. Keep a window when its IoU with every already kept window is ≤ 0.3.
3. Merge kept windows whose polygons still overlap (intersection area > 0) into one candidate. A shared edge with no area stays two candidates.
4. Candidate score = best member score. Every member window and its score are kept and shown.

Worked example. Windows are 10 km with a 5 km stride. Cardinal neighbors have IoU 1/3 ≈ 0.333 and are suppressed. Diagonal neighbors have IoU 25/175 ≈ 0.143 and can both survive. Because they still overlap, the merge step joins them.

| Window | Score | IoU with A | Result |
|---|---|---|---|
| A | 80 | — | kept |
| D (diagonal) | 75 | 0.143 | kept, then merged with A |
| B (east of A) | 70 | 0.333 | dropped |
| C (north of A) | 60 | 0.333 | dropped |

The candidate score is 80. Members are A and D. Across a block of similar scores the same rule thins cardinal duplicates and the merge reunites the diagonal survivors into one region.

## Where each result is read from

`features.parquet` is the search index (filter, nearest neighbours, score, group). `feature_profiles` in PostGIS is the evidence store. One pipeline run writes both and records the parquet SHA-256 on the `processing_runs` row. A search refuses to run when the file checksum does not match that row.

## Explanations (deterministic templates)

For each feature: Earth value, target value, difference, and whether it is inside the tolerance that was stored. The feature with the lowest similarity is the main mismatch. Unavailable features are listed as "not available".

The text states the measured difference. A relief gap of 210 m on a 310 m tolerance is similarity 32, not "−34%". Percent gaps are not shown in place of the similarity.

## Benchmark expectations

Positives are `known_analog_registry` rows inside `earth_atacama` whose `body_target_relevance` includes Mars terrain or Jezero. Other Atacama records are not Jezero positives. Documented rows are excluded from the default candidate list and returned in `reference_matches`, sorted by score. The Atacama demo reads that reference list.

Negatives are eligible windows in the searched region with relief under 30 m. They have passed the water and built-up filters, so the formula is what ranks them. They must not fill `top_k`. Ocean margins and cropland are the wrong control: eligibility drops them before scoring.

A weak ranking of the Mars-relevant Atacama sites is a result about terrain-v1. Report it. It is not a failed pipeline.

## Changing the scoring

1. Copy `terrain-v1.yaml` → `terrain-v2.yaml`. Never edit a released version in place.
2. Re-run the benchmark (Atacama reference ranking + eligible low-relief controls) and note the result in CHANGELOG.md.
3. Cache keys include the scoring version, so old results are never silently reused.

## Adding a feature

Implement it in `core/features/`, add a synthetic-DEM test with a known answer for all three bodies, add it to the feature schema version, add a tolerance and weight in a new scoring version, update this file. See `.claude/skills/geo-pipeline/SKILL.md`.
