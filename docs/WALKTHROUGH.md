# Walkthrough

How data and a search flow through the system, step by step, with the files responsible for each step.

> **Planning version.** File and function names are the *intended* ones from IMPLEMENTATION_PLAN.md. When code lands, replace each "(planned)" with the real path and function, and keep this document true — it is the fastest way for a newcomer to understand the code.

---

## Part A — From raw data to a feature row (offline)

### A1. Download (planned: `pipeline/adapters/`)
- `stac.py` searches Earth Search for `cop-dem-glo-30` tiles that intersect the pilot region, then reads the Cloud-Optimized GeoTIFFs straight from `s3://copernicus-dem-30m` with `AWS_NO_SIGN_REQUEST=YES`.
- `s3_open.py` does the same for ESA WorldCover tiles.
- `usgs_astro.py` downloads the SLDEM2015 / MOLA–HRSC files (once, ~11 GB each) and crops them to the target area.
- Every file gets a SHA-256 checksum and a `source_assets` row; a copy goes to Cloud Storage.

### A2. Preprocess (planned: `pipeline/preprocess.py`, `core/raster/`)
- Mosaic and crop Earth tiles; reproject to the region's equal-area projection.
- **Aggregate** 30 m → 200 m (Mars comparisons) or → 59 m (Moon comparisons) using area-weighted averaging. An assertion blocks any upsampling.
- Build masks from WorldCover: water, built-up, snow/ice, vegetation share, nodata.
- Log a `processing_runs` row (inputs, git SHA, config hash).

### A3. Cut windows (planned: `core/grid/`, `pipeline/windows.py`)
- Tile the region into 10 km squares every 5 km (50% overlap). Each square is an `earth_cells` row tagged with `grid_version`.

### A4. Extract features (planned: `core/features/`, `pipeline/extract_earth.py`)
For each window: slope (Horn method, body-correct pixel size) → median, 90th percentile, histogram; relief (95th − 5th percentile elevation); roughness (spread after removing the best-fit plane); valid fraction. Result: one `feature_profiles` row + one line in `features.parquet`.

### A5. Target profile (planned: `pipeline/extract_target.py`)
Same feature code on the planetary DEM crop for Jezero (or Taurus–Littrow), plus a hillshade PNG preview saved to Cloud Storage.

---

## Part B — One search, from click to evidence panel (online)

### B1. User picks a target (planned: `frontend/app/page.tsx`, `frontend/components/TargetPicker.tsx`)
User chooses "Jezero crater" and the "Western Sahara" region, clicks **Search**. Frontend sends `POST /api/searches` with the JSON shape from SYSTEM_DESIGN.md §12.

### B2. API validates (planned: `backend/api/searches.py`, `backend/schemas/search.py`)
Pydantic validates the request; the backend loads the target profile and checks the region's features exist at the matching scale (200 m for Mars).

### B3. Eligibility filter (planned: `backend/search/filter.py`)
Drops windows with valid fraction < 0.9, too much water or built-up land. Thresholds come from `config/scoring/terrain-v1.yaml`.

### B4. Shortlist (planned: `backend/search/retrieve.py`)
Standardize features (z-scores using the region's stats), nearest-neighbour search to the target vector, keep `10 × top_k` windows.

### B5. Score (planned: `backend/search/score.py`, `core/scoring/`)
Per-feature similarity with the formula in [SCORING.md](SCORING.md); slope histogram via Wasserstein-1; weighted mean over the mandatory features both sides have.

### B6. Group (planned: `backend/search/group.py`)
Overlapping high-scoring windows are merged into candidate regions; the member windows and their individual scores are kept.

### B7. Novelty check (planned: `backend/search/novelty.py`)
Intersect each candidate with `known_analog_registry`. Overlap → *documented analog* (moved to the reference list). No overlap → *not in checked records*. The registry version and date are stored with the result.

### B8. Explain (planned: `backend/search/explain.py`)
Deterministic text from the numbers, e.g. "Median slope 7.9° vs target 8.4° (within tolerance); relief 410 m vs 620 m (−34%, main mismatch)."

### B9. Respond and display (planned: `backend/api/candidates.py`, `frontend/components/ResultsMap.tsx`, `EvidencePanel.tsx`)
Results are saved (`search_jobs`, `candidate_matches`) and returned. The map colours candidate regions by score; clicking one opens the evidence panel: feature bars (Earth vs target vs tolerance), slope histogram overlay, mismatches, missing data, sources, novelty label.

### B10. Review (planned: `backend/api/reviews.py`)
A reviewer with the demo token marks a candidate *promising / known / rejected*; a `review_records` row is written.
