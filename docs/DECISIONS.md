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
