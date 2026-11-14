# Decision log

Lightweight decision records. Add new ones at the bottom; don't rewrite old ones. To change a decision, add a new entry that supersedes it.

Format: **ID — Title** · Date · Status · Decision · Why · Alternatives considered

---

**D-001 — No machine learning for now** · 2026-11-14 · Accepted
- Decision: drop the ML encoder, embeddings, hybrid retrieval and LLM summaries (design §9.2–9.3).
- Why: owner request; the design itself says ML is an enhancement, not a prerequisite (§18). Keeps the hackathon scope achievable.
- Revisit: after the baseline works and has an evaluation harness.

**D-002 — Hackathon thin slice before the phased roadmap** · 2026-11-14 · Accepted
- Decision: build IMPLEMENTATION_PLAN.md §0.2 first: precomputed features, in-memory search, no job queue, one-button review.
- Why: it's a hackathon; the full Phase 0–2 roadmap is ~8–9 weeks.
- Alternatives: full Celery/Redis architecture from day 1 (too slow to build).

**D-003 — Earth DEM: Copernicus GLO-30 from AWS Open Data** · 2026-11-14 · Accepted
- Decision: primary Earth elevation source is Copernicus DEM GLO-30 (`s3://copernicus-dem-30m`), discovered via Element84 Earth Search STAC; Planetary Computer STAC as fallback.
- Why: free, global, no account/key, no rate limit, commercial-safe.
- Caveat: it's a surface model (includes trees/buildings). Mitigated by WorldCover vegetation/built-up flags; pilot regions are deserts.
- Alternatives: FABDEM (bare-earth but non-commercial; kept as optional cross-check), NASADEM (older), OpenTopography API (needs key, ~50 calls/day non-academic).

**D-004 — Moon DEM: SLDEM2015 (59 m)** · 2026-11-14 · Accepted
- Why: best global-scale lunar DEM within ±60° latitude; public domain; no login.
- Polar targets later: LOLA polar LDEMs.

**D-005 — Mars DEM: MOLA–HRSC Blended DEM v2 (200 m)** · 2026-11-14 · Accepted
- Why: ~2× sharper than MOLA MEGDR (463 m); global; no login. 10 km window ≈ 50×50 px, enough for stable statistics.
- Caveat: HRSC part is CC BY-SA 3.0 IGO → credit; share derived Mars DEM products under the same terms if redistributed.

**D-006 — Compare at the target's resolution** · 2026-11-14 · Accepted
- Decision: aggregate Earth DEM down to ~59 m (Moon comparisons) and ~200 m (Mars comparisons). Two Earth feature sets.
- Why: design §5 — never upsample; compare compatible resolutions.

**D-007 — First targets: Jezero (Mars), Taurus–Littrow (Moon)** · 2026-11-14 · Accepted (owner may swap)
- Why: well-studied landing sites with ground truth → easy to sanity-check; both covered by the chosen DEMs.

**D-008 — Pilot regions: Atacama+Altiplano and Western Sahara** · 2026-11-14 · Accepted (owner may swap)
- Why: Atacama has many documented analogs → benchmark ("does it find known ones?"). Western Sahara (Mauritania/Mali) has few → discovery ("does it find unlisted ones?").

**D-009 — Hosting on Google Cloud: one VM + Cloud Storage** · 2026-11-14 · Accepted
- Decision: Compute Engine e2-standard-4 (resize to e2-standard-8 for processing), Docker Compose, Caddy for HTTPS, Cloud Storage bucket, 200 GB disk, `us-central1`.
- Why: team has GCP credits; one VM is the simplest thing that works. ≈ $98/month on-demand, ≈ $5–15 per hackathon week if stopped when idle.
- Alternatives: Cloud Run + Cloud SQL + Memorystore (more wiring, more cost for a hackathon), AWS, Hetzner.

**D-010 — Non-commercial licensing stance** · 2026-11-14 · Accepted (owner to confirm)
- Unlocks: FABDEM, EOX Sentinel-2 cloudless tiles, Earth Engine free tier.
- If commercial later: swap EOX for a paid basemap (e.g. MapTiler ≈ $25–30/month), drop FABDEM and Earth Engine free tier.

**D-011 — Basemap: OpenFreeMap + EOX satellite layer** · 2026-11-14 · Accepted
- Why: both free with no API key (EOX non-commercial). Planetary targets shown as pre-rendered hillshade images, never on an Earth basemap.

**D-012 — Slope-histogram comparison: Wasserstein-1 distance** · 2026-11-14 · Accepted
- Why: works on ordered bins, has units (degrees) so a tolerance is meaningful, robust to small shifts. Histogram intersection rejected: ignores how far apart bins are.

**D-013 — Retrieval: standardized features + scikit-learn nearest neighbours in memory** · 2026-11-14 · Accepted
- Why: pilot regions give tens of thousands of windows — trivially fast in memory. No vector database needed.

**D-014 — Python 3.12 via uv, not the laptop's Python 3.14** · 2026-11-14 · Accepted
- Why: geospatial wheels (rasterio, GDAL bindings) lag new Python releases.

**D-015 — Heavy data processing on the VM, not the laptop** · 2026-11-14 · Accepted
- Why: laptop has 64 GB free disk and a 4-core CPU; planetary DEMs alone are ~22 GB.

**D-016 — Hackathon scaffold has no job queue** · 2026-11-14 · Accepted
- Decision: Phase 0 and the hackathon app do not include Celery, Redis, or a worker service. Compose is PostGIS, MinIO, the API, and the frontend. The pipeline is a CLI run in the backend image. `process-region.sh` uses that container.
- Why: D-002. The Phase 0 text still required a worker, which rebuilds the architecture the hackathon dropped.
- Supersedes: the worker and Redis lines previously in IMPLEMENTATION_PLAN.md §1, §2, and §8.2. A queue comes back only when a search can no longer be precomputed.

**D-017 — Hackathon search is synchronous** · 2026-11-14 · Accepted
- Decision: `POST /searches` runs in the request, writes `search_jobs.status = completed`, and returns the search id. The client loads candidates with `GET /searches/{id}/candidates`. It does not poll. Missing features return HTTP 409 `features_not_ready`. Processing stays the CLI.
- Why: the regions are precomputed, so a queue would never run. The search id keeps the later job-shaped API.
- Later: the full design may return 202 and poll. `retrieval_mode` accepts only `baseline`.

**D-018 — Canonical ids and default extents** · 2026-11-14 · Accepted (owner may swap extents in config)
- Decision: ids are `mars_jezero`, `moon_taurus_littrow`, `earth_atacama`, `earth_sahara`. Boxes, Lambert centers, and the 10 km scored footprints are in `config/grids/pilot-v1.yaml` and `config/targets/`. Preview boxes are hillshades and are not scored.
- Sahara box: 21.5–26°N, 13–7°W (eastern Western Sahara and northern Mauritania). Mali is outside it.
- Atacama box: 24.5–19.5°S, 70.5–65.5°W (northern Chile, southwest Bolivia, northwest Argentina).
- Jezero is scored as a 10 km square at Octavia E. Butler Landing (18.4446°N, 77.4509°E), not as the whole 45 km crater.
- Taurus–Littrow is scored as a 10 km square at the Apollo 17 lunar module (20.1911°N, 30.7723°E).
- Supersedes the names `pilot_1`, `pilot_region`, `mars_target_01`, and `western_sahara`.

**D-019 — Parquet is the search index; PostGIS holds evidence** · 2026-11-14 · Accepted
- Decision: filter, nearest neighbours, score, and grouping read `features.parquet` for one region and one `scale_m`. The evidence API reads `feature_profiles`. One pipeline run writes both and stores the parquet SHA-256 on `processing_runs`. A checksum mismatch refuses the search.
- Why: two stores were both described as the search input, so rank and evidence could drift.

**D-020 — Nearest neighbours uses four scalars; the histogram is rerank-only** · 2026-11-14 · Accepted
- Decision: the tree is z-scored `slope_median`, `slope_p90`, `relief`, and `roughness`, using eligible windows of the region being searched. `slope_hist` is Wasserstein-1 at rerank. Shortlist size is `10 × top_k` (default `top_k` 20). Weight sliders rescore that shortlist and do not rebuild the tree.
- Why: the histogram is not a scalar. Leaving it out of the tree without a large shortlist would drop windows the histogram would have ranked highly.
- Weights are unchanged. The slope family sums to 0.65. A weight change is a new scoring version.

**D-021 — Histogram distance, grouping, tolerance floors, one purpose** · 2026-11-14 · Accepted
- Decision: Wasserstein-1 is the integral of the absolute CDF gap from 0° to 90°, in degrees. Grouping is greedy non-maximum suppression at IoU > 0.3 (tie-break: higher score, then smaller `cell_id`), then a merge of survivors that still overlap. Relief tolerance is `max(50% of target relief, 20 m)`. Roughness tolerance is `max(50% of target roughness, 2 m)`. The hackathon purpose id is `exposed_terrain`: vegetation and snow/ice are flags, not exclusions.
- Why: unequal histogram bins make a bin-index distance the wrong unit; the 5 km stride produces cardinal IoU 0.33, so the threshold needed a worked example; a flat target would otherwise collapse a relative tolerance to zero; "purpose" had no allowed value.

**D-022 — What the Atacama benchmark is allowed to call a success** · 2026-11-14 · Accepted
- Decision: Jezero positives are registry rows inside `earth_atacama` whose recorded relevance includes Mars terrain or Jezero. They are judged on `reference_matches`, not on the default candidate list. Negatives are eligible windows with relief under 30 m, and they must not fill `top_k`. A weak positive ranking is reported as a property of terrain-v1.
- Why: many Atacama analog records were chosen for soils or minerals. Ocean and cropland never reach the formula, because eligibility drops them.

**D-023 — Comparison grids are 200 m and 60 m, aligned to the region projection** · 2026-11-14 · Accepted
- Decision: Mars comparisons use a 200 m grid. Moon comparisons use a 60 m grid. Each Earth cell stores both profiles. Aggregation is area-weighted averaging onto pixels whose edges are multiples of that size from the region LAEA origin. An assertion requires both output axes to be coarser than or equal to the source ground pixel. WorldCover fractions are counts of native 10 m pixels (class lists in `terrain-v1.yaml`).
- Why: 200/30 and 59/30 are not integer factors, and a 59 m Moon grid would upsample SLDEM's latitude posting near 20°N (~59.2 m). 60 m is coarser than that posting and coarser than Earth 30 m.
- Supersedes: the approximate "~59 m comparison grid" in D-006. SLDEM2015 itself remains the ~59 m product (D-004).

**D-024 — One decision log, and the evidence panel outranks the marketing-site skill** · 2026-11-14 · Accepted
- Decision: new decisions go only in this file. Do not also open `docs/adr/`. `design-taste-frontend` (tasteskill 2.5.1) is already installed. On a conflict, the map, the evidence panel, and `.claude/skills/scientific-copy/SKILL.md` win over that skill's landing-page rules.
- Why: two ADR locations were specified, and the taste skill's house rules hide the numbers this product has to show.
