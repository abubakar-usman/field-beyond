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
- Mosaic and crop Earth tiles; reproject to the region's equal-area projection (`config/grids/pilot-v1.yaml`).
- **Aggregate** 30 m → 200 m (Mars comparisons) and → 60 m (Moon comparisons) with area-weighted averaging. Pixel edges are multiples of that size from the LAEA origin. An assertion blocks any upsampling, including of the Moon and Mars DEMs.
- Count WorldCover classes at native 10 m inside each window (class lists in `config/scoring/terrain-v1.yaml`).
- Log a `processing_runs` row (inputs, git SHA, config hash, parquet SHA-256).

### A3. Cut windows (planned: `core/grid/`, `pipeline/windows.py`)
- Tile the region into 10 km squares every 5 km (50% overlap). Each square is an `earth_cells` row tagged with `grid_version`.

### A4. Extract features (planned: `core/features/`, `pipeline/extract_earth.py`)
For each window, at each `scale_m` (200 and 60): slope (Horn method, body-correct pixel size) → median, 90th percentile, histogram; relief (95th − 5th percentile elevation); roughness (spread after removing the best-fit plane); valid fraction. Result: one `feature_profiles` row and one line in `features.parquet`. Columns are listed in `config/scoring/terrain-v1.yaml`. A mandatory null excludes the window later.

### A5. Target profile (planned: `pipeline/extract_target.py`)
Same feature code on the 10 km scored square in `config/targets/` (Jezero landing site, or the Apollo 17 lunar module). The wider preview bbox is rendered to a hillshade PNG and is not scored.

---

## Part B — One search, from click to evidence panel (online)

### B1. User picks a target (planned: `frontend/app/page.tsx`, `frontend/components/TargetPicker.tsx`)
User chooses Jezero crater and `earth_sahara`, clicks **Search**. Frontend sends:

```json
{
  "target_id": "mars_jezero",
  "region_id": "earth_sahara",
  "purpose": "exposed_terrain",
  "required_feature_groups": ["terrain"],
  "exclude_documented_analogs": true,
  "retrieval_mode": "baseline",
  "top_k": 20,
  "scoring_version": "terrain-v1"
}
```

`footprint_m` and `scale_m` come from the target file (10 km, 200 m). The client does not send a drawn geometry in the hackathon.

### B2. API validates (planned: `backend/api/searches.py`, `backend/schemas/search.py`)
Pydantic validates the request. The backend loads the target profile and the region's `features.parquet` at the target's `scale_m`. The file's SHA-256 must match `processing_runs`. If the file is missing, the response is HTTP 409:

```json
{"error": "features_not_ready", "region_id": "earth_sahara", "target_id": "mars_jezero", "scale_m": 200}
```

The hackathon API does not enqueue processing. When the file is present, the search runs in the request and the response is:

```json
{"search_id": "…", "status": "completed", "scoring_version": "terrain-v1", "region_id": "earth_sahara", "target_id": "mars_jezero", "scale_m": 200}
```

The client then calls `GET /searches/{id}/candidates`. It does not poll.

### B3. Eligibility filter (planned: `backend/search/filter.py`)
Drops windows with valid fraction < 0.9, water share above 5%, or built-up share above 2%. Thresholds and WorldCover class lists come from `config/scoring/terrain-v1.yaml`. Snow/ice and vegetation stay as flags.

### B4. Shortlist (planned: `backend/search/retrieve.py`)
Z-score four scalars — `slope_median`, `slope_p90`, `relief`, `roughness` — using eligible windows in this region. Nearest neighbours against the target vector. Keep `10 × top_k` windows. The slope histogram is not in the tree.

### B5. Score (planned: `backend/search/score.py`, `core/scoring/`)
Per-feature similarity with the formula in [SCORING.md](SCORING.md). The histogram uses Wasserstein-1 in degrees. Relative relief and roughness tolerances use the floors in the yaml. Weighted mean over the mandatory features both sides have. A missing mandatory feature excludes the window.

### B6. Group (planned: `backend/search/group.py`)
Overlapping high-scoring windows are merged into candidate regions; the member windows and their individual scores are kept.

### B7. Novelty check (planned: `backend/search/novelty.py`)
Intersect each candidate with `known_analog_registry`. Overlap → *documented analog*, moved to `reference_matches`. No overlap → *not in checked records*, kept in `candidates`. The registry version and date are stored with the result. Jezero positives for the benchmark are rows inside `earth_atacama` whose relevance includes Mars terrain or Jezero.

### B8. Explain (planned: `backend/search/explain.py`)
Deterministic text from the numbers, e.g. "Median slope 7.9° vs target 8.4° (within tolerance); relief 410 m vs 620 m (−34%, main mismatch)."

### B9. Respond and display (planned: `backend/api/candidates.py`, `frontend/components/ResultsMap.tsx`, `EvidencePanel.tsx`)
Results are saved (`search_jobs` with status `completed`, `candidate_matches`). `GET /searches/{id}/candidates` returns `candidates` and `reference_matches`. The map colours candidate regions by score. The Atacama demo turns on the reference list. Clicking a result opens the evidence panel, which reads `feature_profiles`: feature bars (Earth vs target vs the stored tolerance), slope histogram overlay, the main mismatch, missing data, sources, novelty label.

### B10. Review (planned: `backend/api/reviews.py`)
A reviewer with the demo token marks a candidate *promising / known / rejected*; a `review_records` row is written.
