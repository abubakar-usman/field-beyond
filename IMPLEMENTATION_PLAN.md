# Earth Analog Explorer — Implementation Plan

Source: *Earth Analog Explorer — Project Overview and System Design* — Markdown copy in [docs/SYSTEM_DESIGN.md](docs/SYSTEM_DESIGN.md).
This plan turns that design into buildable milestones. Section references (§) inside a "Why" column or written as "§N step M" point to the design document; references like §0.2 or §8.1 point to sections of this plan.
Start-here guide for new people and AI agents: [docs/HANDOFF.md](docs/HANDOFF.md).

Decisions D-016–D-024 lock the hackathon contract: no job queue, a synchronous search, ids and extents in `config/`, `features.parquet` as the only search index, and a 60 m Moon comparison grid. If an older sentence below disagrees with those decisions or with a file in `config/`, the decision and the config win.

---

## 0. Guiding decisions

| Decision | Choice | Why |
|---|---|---|
| Scope | Terrain-based mathematical baseline only; **all machine-learning work (§9.2, §9.3, embeddings, LLM summaries) is out of scope for this plan** | §18: ML is an enhancement, not a prerequisite |
| Repo shape | Single monorepo: `core/`, `backend/`, `pipeline/`, `frontend/`, `infra/`. No `worker/` package in the hackathon (D-016) | One versioned codebase so processing versions are traceable |
| Python | 3.12, `uv` for dependency management, shared `core` package | Pipeline CLI and API reuse the same feature code |
| Earth pilot DEM | **Copernicus DEM GLO-30** from AWS Open Data, found via the Element84 Earth Search STAC API | Free, global, no account or key needed, commercial use allowed |
| Lunar target DEM | **SLDEM2015** (LOLA + Kaguya merged DEM, ~59 m/px, ±60° latitude) | Best global-scale lunar DEM; public domain |
| Martian target DEM | **MOLA–HRSC Blended DEM v2** (~200 m/px, global) | ~2× sharper than MOLA MEGDR alone, still global |
| Comparison scale | Earth DEM is **aggregated down** onto a 60 m grid (Moon) and a 200 m grid (Mars). One cell, two profiles. SLDEM2015 is the ~59 m product; the grid is 60 m so that product is not upsampled (D-023) | §5: never upsample coarse data; compare compatible resolutions |
| First targets | Mars: **Jezero crater region**; Moon: **Apollo 17 Taurus–Littrow valley region** | Both have rover/landing ground truth and DEM coverage; easy to sanity-check |
| Pilot Earth regions | `earth_atacama` and `earth_sahara` in `config/grids/pilot-v1.yaml`. Atacama (Chile, Bolivia, Argentina) is the benchmark. The Sahara box is eastern Western Sahara and northern Mauritania; Mali is outside it | One region tests whether known Mars-terrain analogs rank highly; the other returns unlisted candidates |
| Window grid | Square windows in a per-region equal-area projection (LAEA), 10 km footprint, 50% overlap — all configurable | §8 step 2 |
| Baseline retrieval | Standardized feature vectors + scikit-learn `BallTree`/brute-force kNN in memory | §10: simple numeric nearest-neighbour search |
| Map | MapLibre + **OpenFreeMap** base tiles (free, no key) + **EOX Sentinel-2 cloudless** satellite layer (free for non-commercial use, attribution required); Earth candidates also shown as our own DEM hillshade; **pre-rendered PNG previews** for Moon/Mars targets | §10: never place planetary coords on an Earth basemap |
| Hosting | **Google Cloud** (paid from the team's credits): one Compute Engine VM running Docker Compose + a Cloud Storage bucket | Simplest setup that fits a hackathon; no managed-service wiring |
| Licensing stance | **Non-commercial** (hackathon) — unlocks FABDEM and free satellite tiles. If the project later goes commercial, swap the EOX layer and drop FABDEM; everything else stays | Keeps the door open both ways |

Targets and regions above are defaults; changing them is a config change, not a code change.

---

## 0.1 Data sources, API keys and pricing

### Data (all free)

| Purpose | Source | Access | Key / login? | License | Cost |
|---|---|---|---|---|---|
| Earth elevation | Copernicus DEM GLO-30 — bucket `s3://copernicus-dem-30m` (eu-central-1) | STAC search: `https://earth-search.aws.element84.com/v1` collection `cop-dem-glo-30`; read COGs directly with `--no-sign-request` | **None** | Copernicus DEM license (free, attribution) | $0 |
| Earth elevation fallback | Microsoft Planetary Computer STAC (`cop-dem-glo-30`) | `planetary-computer` Python package signs URLs automatically | None (anonymous tokens) | Same | $0 |
| Bare-earth cross-check (optional) | FABDEM v1.2 (trees/buildings removed) | University of Bristol data portal | None | **CC BY-NC-SA 4.0 — non-commercial only** (fine for the hackathon) | $0 |
| Satellite imagery layer | EOX Sentinel-2 cloudless WMTS | Public WMTS endpoint | None | Free for non-commercial use with attribution | $0 |
| Quick exploration (optional) | Google Earth Engine — has Copernicus GLO-30, WorldCover, FABDEM in its catalogs | Python API on the team's GCP project, registered as non-commercial | GCP project (no key) | Non-commercial Community tier: 150 compute-hours/month free | $0 |
| Earth land cover masks (water, built-up, snow, vegetation) | ESA WorldCover 10 m — bucket `s3://esa-worldcover` | Direct S3, `--no-sign-request` | **None** | CC BY 4.0 | $0 |
| Earth geology (Phase 4) | Macrostrat API `https://macrostrat.org/api/v2/geologic_units/map` | REST, JSON | **None** | CC BY 4.0 (cite Macrostrat + original maps) | $0 |
| Moon elevation | SLDEM2015 (USGS Astrogeology / NASA PGDA / MIT LOLA node) | HTTPS download, ~11 GB global file; tiles also available | **None** | Public domain | $0 |
| Moon polar targets (later) | LOLA polar LDEMs (down to 5 m/px) via PDS Geosciences / Lunar ODE | HTTPS | None (ODE login optional) | Public domain | $0 |
| Mars elevation | MOLA–HRSC Blended DEM Global 200 m v2 (USGS Astrogeology) | HTTPS download, ~11 GB | **None** | MOLA CC0; HRSC **CC BY-SA 3.0 IGO** → credit and share derived DEM products under the same terms | $0 |
| Known analog registry seed | USGS "Known Terrestrial Analog Sites for Planetary Science" (data.gov, updated Oct 2025) + NASA Planetary Analog Explorer + literature | Download / manual curation | None | US Government public data | $0 |

**Not used:** OpenTopography API — it serves the same Copernicus DEM but needs a key and allows only ~50 calls/day for non-academic users. Direct AWS access has no such limit.

### API keys and secrets the app actually needs

| Secret | Needed for | Required? |
|---|---|---|
| Postgres password | Database | Yes |
| GCP service account with access to the storage bucket (VM uses its attached service account, so no key file) | Storing rasters and previews | Yes |
| Shared demo password or simple token | Protect review/processing endpoints during the demo | Yes (simple) |

No data provider needs a key for the chosen sources. All secrets live in server-side env vars, never in the frontend.

### Google Cloud setup (paid from credits)

| Component | GCP service | Notes |
|---|---|---|
| App server | Compute Engine **e2-standard-4** (4 vCPU, 16 GB) in `us-central1`, Ubuntu + Docker Compose | Runs Postgres/PostGIS, API, frontend. Resize to **e2-standard-8** for a few hours while processing a region, then back down |
| Raster storage | Cloud Storage bucket, Standard class, same region | Source DEM copies, derived rasters, previews |
| Disk | 200 GB balanced persistent disk | Working space for DEM processing |
| Domain / HTTPS | VM external IP + Caddy (automatic HTTPS) | Avoids load-balancer cost |
| Optional | Earth Engine (non-commercial registration on the same project) | Quick looks only; the real pipeline stays in our code |

### Pricing (checked Nov 2026; confirm in the GCP Pricing Calculator)

| Item | Approx. cost |
|---|---|
| All scientific data | **$0** |
| e2-standard-4 VM, on-demand ($0.134/h) | ≈ **$98/month**, ≈ **$3.20/day**; stop it when not in use |
| Temporary e2-standard-8 for processing | ≈ $0.27/h → **a few dollars per region** |
| Cloud Storage Standard (~$0.020/GB-month) for 50–100 GB | ≈ **$1–2/month** |
| 200 GB balanced disk | ≈ **$20/month** |
| Download costs | Pulling data in from AWS Open Data / USGS: **$0** to us. Serving the app to demo viewers: negligible at hackathon traffic |
| Base map + satellite layer | **$0** (OpenFreeMap + EOX, non-commercial) |

**Estimated total:** about **$120/month if left running 24/7**. The 200 GB disk is about **$20/month even while the VM is stopped** (about $5 in a fully stopped week). A hackathon week with the VM on for a few days is about **$15–25**. Set a **GCP budget alert** (e.g. $50) on the project so credits are never drained by surprise.

**If the project ever goes commercial:** replace the EOX satellite layer (e.g. MapTiler paid plan ≈ $25–30/month) and stop using FABDEM and Earth Engine's free tier. Everything else is commercial-safe.

---

## 0.2 Hackathon MVP (build this first)

The phased plan below (§2–§9) is the full roadmap. For the hackathon, build a thin slice that proves the core idea: **"pick a Mars or Moon target → the app finds unlisted Earth places with similar terrain and explains why."**

### Simplifications for the hackathon
| Full plan | Hackathon version | Why it's safe |
|---|---|---|
| Celery + Redis job queue | **None.** Phase 0 does not start Redis or a worker (D-016). Features are precomputed by a CLI. `POST /searches` runs inline and returns a completed search id (D-017). Missing features return 409 `features_not_ready` | No long requests left once features are precomputed |
| PostGIS for everything | PostGIS holds cells, profiles, registry, and results. **Search reads only `features.parquet`.** Evidence reads `feature_profiles`. The parquet SHA-256 must match the processing run (D-019) | Rank and evidence stay on the same run |
| Full review workflow + roles | One "mark as reviewed / promising / known" button behind a shared demo token | Shows the novelty concept without auth work |
| Formal evaluation harness | One benchmark notebook, defined in D-022: Mars-relevant Atacama registry rows on the reference list, plus eligible windows with relief under 30 m as negative controls | Gives a credible "it works" slide |
| Drawn search areas | Two pre-defined pilot regions | Avoids on-demand processing |

### Priorities
**Must (the demo fails without these)**
1. Download the MOLA–HRSC blend for the Jezero preview box and the 10 km scored square; Copernicus DEM + WorldCover for `earth_atacama` and `earth_sahara`.
2. Feature extraction (slope median/p90/histogram, relief, roughness, valid fraction) at 200 m, with synthetic-DEM tests. Each Earth cell also gets a 60 m profile when the lunar target is built.
3. 10 km windows with 5 km stride from `config/grids/pilot-v1.yaml`; eligibility from `config/scoring/terrain-v1.yaml` (water, built-up, valid fraction). Vegetation and snow/ice are flags.
4. Scoring per [docs/SCORING.md](docs/SCORING.md): four-scalar nearest neighbours, histogram at rerank, then overlap grouping.
5. Known-site check against the USGS "Known Terrestrial Analog Sites" dataset → labels *documented analog* / *not in checked records*. Documented rows go to `reference_matches`.
6. API: `GET /targets`, `POST /searches` (inline, status `completed`, or 409 `features_not_ready`), `GET /searches/{id}/candidates` (includes `reference_matches`), `GET /candidates/{id}/evidence`. No polling.
7. Frontend: target picker with Mars preview image → map of ranked candidates → evidence panel (feature bars Earth vs target, slope histogram overlay, mismatches, missing data, novelty label).
8. Deployed on the GCP VM with a public URL using the §8.2 scripts (`create-vm.sh`, `bootstrap.sh`, `deploy.sh`).
9. `README.md`, `docs/WALKTHROUGH.md`, `CLAUDE.md`, `ATTRIBUTIONS.md` and the taste skill in place from day 1.

**Should (big demo value, add if time allows)**
10. Lunar target (`moon_taurus_littrow`) on the 60 m grid.
11. Side-by-side hillshade: target vs candidate.
12. Satellite layer (EOX) toggle; documented analogs as a reference layer.
13. CSV/GeoJSON export with the search configuration.
14. Weight sliders that rescore the current shortlist (they do not run a new nearest-neighbour search). The UI says so.

**Could (only if everything else is done)**
15. Geology from Macrostrat for candidates.
16. FABDEM cross-check flag on candidates.
17. Sensitivity view: how rank changes with window size.

### Suggested split for a small team
| Person | Owns |
|---|---|
| Data / geo | Downloads, preprocessing, windows, feature extraction, synthetic tests |
| Backend | Scoring, retrieval, grouping, registry check, FastAPI, GCP deploy |
| Frontend | Next.js + MapLibre map, target picker, evidence panel, styling |
| (4th, if any) | Benchmark notebook, demo story, slides, Should-list items |

Data work blocks everything else, so on day 1 the backend and frontend build against a small **fake `features.parquet`** whose columns are listed in `config/scoring/terrain-v1.yaml`, then switch to real data when it lands.

### Demo story (2–3 minutes)
Same beats as [docs/DEMO.md](docs/DEMO.md): Jezero's 10 km profile, `earth_sahara` candidates labelled *not in checked records*, the evidence panel, then `earth_atacama` judged on `reference_matches` for registry rows linked to Mars terrain or Jezero. A weak ranking is reported as a property of terrain-v1.

---

## 0.3 Manual steps (things only you can do)

| # | Step | When | Notes |
|---|---|---|---|
| 1 | Install the missing tools on the laptop (§0.4) | Day 0 | Docker needs WSL2 and a restart |
| 2 | If WSL/Docker fails to start: **enable CPU virtualization (Intel VT-x) in the BIOS/UEFI** | Day 0 | Windows currently reports virtualization as disabled |
| 3 | Free disk space: only **64 GB free** on C: | Day 0 | Docker images + DEMs need ~40 GB. Recommended: do heavy data processing **on the VM**, keep only small samples locally |
| 4 | GCP: confirm credits are on a billing account, create a project (e.g. `earth-analog-explorer`), link billing | Day 0 | Console → Billing |
| 5 | GCP: set a **budget alert** (e.g. $50, alerts at 50/90/100%) | Day 0 | Console → Billing → Budgets & alerts |
| 6 | GCP: run `gcloud auth login` and `gcloud config set project <id>` on the laptop | Day 0 | Opens a browser sign-in; I can't do this for you |
| 7 | Enable APIs: Compute Engine, Cloud Storage (and Earth Engine if wanted) | Day 0 | `scripts/vm/create-vm.sh` can do this once you're signed in |
| 8 | (Optional) Register the project for **Earth Engine non-commercial** use | Day 0 | code.earthengine.google.com → choose Community tier |
| 9 | Create a **GitHub repo** and invite teammates | Day 0 | Private is fine; the VM pulls from it with a read-only deploy key |
| 10 | Add the VM's deploy key to GitHub (printed by `bootstrap.sh`) | Day 1 | Repo → Settings → Deploy keys |
| 11 | Choose a URL: free `http://<ip>.sslip.io` style hostname, or point your own domain's DNS at the VM IP | Day 1 | sslip.io works with Caddy HTTPS and costs nothing |
| 12 | Fill in `.env` on the VM (DB password, demo token) — generated by `bootstrap.sh`, review it | Day 1 | Never commit `.env` |
| 13 | Check hackathon rules on data licenses and attribution; keep `ATTRIBUTIONS.md` visible in the app | Before demo | |
| 14 | Review the top candidates yourself (or with a domain expert) and set their review labels | Before demo | The app must not claim novelty on its own |
| 15 | **Stop the VM when not in use** (`scripts/vm/stop.sh`) | Daily | Saves most of the cost |

## 0.4 Local machine status (checked on this laptop, Nov 2026)

Machine: Intel i7-8565U (4 cores / 8 threads), 15.8 GB RAM, Windows 11 Pro, 64 GB free disk.

| Tool | Status | Action |
|---|---|---|
| Git 2.54 | ✅ installed | — |
| Node.js 24 + npm 12 | ✅ installed | — |
| VS Code | ✅ installed | — |
| curl, ssh | ✅ installed | — |
| Python 3.14 | ✅ installed, but **too new for some geospatial wheels** | Don't use it directly; let `uv` install Python 3.12 for the project |
| **uv** | ❌ missing | `winget install astral-sh.uv` |
| **WSL2** | ❌ missing | `wsl --install` (admin), restart |
| **Docker Desktop** | ❌ missing | `winget install Docker.DockerDesktop` after WSL2; free for personal/education/small teams |
| **Google Cloud CLI (gcloud)** | ❌ missing | `winget install Google.CloudSDK`, then `gcloud auth login` |
| GDAL / psql | ❌ missing | **Not needed on the laptop** — they run inside Docker and inside the `rasterio` wheel |
| AWS CLI | ❌ missing | **Not needed** — public S3 data is read directly with `AWS_NO_SIGN_REQUEST=YES` |
| make | ❌ missing | **Not needed** — we use PowerShell and bash scripts |
| pnpm | ❌ missing | Optional; npm is fine |

`scripts/local/check-tools.ps1` repeats this check so teammates can verify their own machines.

---

## 1. Repository layout

```
earth-analog-explorer/
├── core/                      # shared Python package (pure, unit-tested)
│   ├── bodies.py              # Earth/Moon/Mars radii, CRS definitions
│   ├── raster/                # load, reproject, aggregate, masks
│   ├── features/              # slope, relief, roughness, histograms, landforms
│   ├── scoring/               # similarity functions, weighting, versions
│   ├── grid/                  # window generation, grid versioning
│   └── provenance.py          # checksums, run records
├── pipeline/                  # offline ingestion + processing (CLI; runs in the backend image)
│   ├── adapters/              # stac.py, pds.py, ... (one per provider)
│   ├── ingest.py
│   ├── preprocess.py
│   ├── extract_earth.py
│   └── extract_target.py
├── backend/                   # FastAPI app
│   ├── api/                   # routers per resource
│   ├── schemas/               # Pydantic models
│   ├── db/                    # SQLAlchemy models + Alembic migrations
│   ├── search/                # retrieval, rerank, grouping, novelty, explanations
│   └── auth/
├── frontend/                  # Next.js + TypeScript + MapLibre
├── config/
│   ├── scoring/terrain-v1.yaml
│   ├── grids/pilot-v1.yaml
│   ├── targets/               # mars-jezero.yaml, moon-taurus-littrow.yaml
│   └── sources.yaml           # approved hosts
├── infra/
│   ├── docker-compose.yml      # local dev: postgis, minio, api, frontend
│   ├── docker-compose.prod.yml # VM: postgis, api, frontend, caddy
│   ├── Caddyfile               # reverse proxy + automatic HTTPS
│   └── .env.example            # every setting, no real secrets
├── scripts/
│   ├── local/                  # Windows dev helpers (PowerShell)
│   └── vm/                     # GCP VM create / deploy / process / backup (bash)
├── docs/                       # see §8.1
├── .claude/
│   └── skills/                 # taste skill + project skills (see §8.1)
├── CLAUDE.md                   # instructions for AI coding agents
├── README.md
└── ATTRIBUTIONS.md             # required data credits
```

---

## 2. Phase 0 — Foundations (≈1 week)

**Goal:** everything runs locally with one command; nothing scientific yet.

1. Monorepo scaffold, `uv` workspace, ruff + mypy + pytest, pre-commit.
2. `docker-compose.yml`: PostGIS 16, MinIO locally (Cloud Storage on GCP, same S3-style code via `fsspec`/`gcsfs`), API, frontend. No Redis and no worker (D-016).
3. Config system (pydantic-settings) reading `config/`; secrets only via env vars / secret store, never in the frontend bundle (§15).
4. Alembic migration #1 with all tables from §5 below (empty).
5. CI pipeline: lint, type-check, unit tests, build images.
6. `core/bodies.py`: body constants and CRS strings (Moon IAU_2015:30100, Mars IAU_2015:49900 or equivalent PROJ strings; Earth EPSG:4326 / per-region LAEA). Unit tests that distances/derivatives use the correct radius.

**Exit criteria:** `docker compose up` gives a healthy API (`/health`), a database with the schema, a MinIO bucket, and a blank Next.js page. There is no worker container.

---

## 3. Phase 1 — Data audit and terrain baseline (≈3–4 weeks)

**Goal:** deterministic, provenance-tracked terrain features for one Martian target and a pilot Earth region (lunar follows in the same phase once the Mars path works).

### 3.1 Data audit (deliverable: `docs/data-audit.md`)
- For each source: product ID/version, resolution, coverage of target & pilot, license, access method (auth, signed URLs, rate limits).
- The scored footprints and preview boxes are already in `config/targets/`. The audit checks those boxes against the DEM, then writes them out as GeoJSON in body-native coordinates.
- Confirm DEM coverage and quality over both targets and both pilot regions (check Copernicus tile gaps, SLDEM2015 artefacts, HRSC vs MOLA-only areas in the blended DEM).
- Confirm the grids: a 10 km window holds 50×50 px at 200 m (Mars) and about 167×167 px at 60 m (Moon), which is enough for stable slope histograms.

### 3.2 Source adapters & ingestion
- `Adapter` interface: `discover(aoi) -> [AssetRef]`, `fetch(asset) -> local/object path`, with retries + exponential backoff, provider rate limits, credential injection.
- `stac.py` (Copernicus DEM via Earth Search, Planetary Computer fallback), `s3_open.py` (WorldCover), `usgs_astro.py` (SLDEM2015, MOLA–HRSC blended DEM downloads).
- Allowlist of hosts in `config/sources.yaml`; reject any other URL (SSRF guard, §15).
- Every fetched file → `source_assets` row (provider, body, footprint, resolution, version, SHA-256, access metadata) and stored in object storage.

### 3.3 Body-aware preprocessing
- Clip/mosaic, reproject to the region's LAEA (Earth) or a local LAEA on the correct sphere (Moon, Mars). Proj strings and radii come from `config/grids/pilot-v1.yaml` and `core/bodies.py`.
- Aggregate onto the comparison grid with area-weighted averaging. Pixel edges are multiples of 200 m or 60 m from the LAEA origin. Assert both output axes are coarser than or equal to the source ground pixel. This applies to Earth, Moon, and Mars rasters (D-023).
- Count WorldCover at native 10 m using the class lists in `terrain-v1.yaml`. Water and built-up can exclude a window. Snow/ice and vegetation are flags under `exposed_terrain`. Vegetation also flags windows where Copernicus (a surface model) may overstate roughness.
- Each step logged as a `processing_runs` row (inputs, code version = git SHA, config hash, parquet SHA-256, status, errors).

### 3.4 Window generation
- `core/grid`: tile region in LAEA, 10 km windows, configurable stride (default 5 km). Grid identified by `grid_version`.
- Persist `earth_cells` with boundary (stored in EPSG:4326 for PostGIS), parent region, footprint size, grid version.

### 3.5 Feature extraction (same code for Earth and planetary)
| Feature | Implementation |
|---|---|
| Slope | Horn's method on projected DEM with body-correct pixel size; median, p90, fixed-bin histogram (e.g. 0–2–5–10–15–20–30–45–90°) |
| Relief | p95 − p5 elevation within window (m) |
| Roughness | Std of residuals after least-squares plane fit at a declared scale (store scale in metadata) |
| Valid fraction | Share of non-masked pixels; drives eligibility |
| Landforms (optional) | Placeholder schema field; populated only from documented classifications |

- Output one `feature_profiles` row per scale (200 m and 60 m) and the matching line in `features.parquet`. Availability flags must match null values. Columns are in `terrain-v1.yaml`.
- **Golden tests:** synthetic DEMs (flat plane, tilted plane, cone, known noise) with analytically known slope/relief/roughness, run on all three bodies.

### 3.6 Target profiles
- `planetary_targets` row + its `feature_profiles` (one profile per scale) + pre-rendered hillshade PNG in object storage.

**Exit criteria:** CLI `pipeline run --region earth_atacama --target mars_jezero` reproducibly produces identical feature values (bit-for-bit or within tolerance) on re-run; all rows carry provenance; golden tests pass; the parquet SHA-256 on the processing run matches the file.

---

## 4. Phase 2 — Discovery application (≈4 weeks)

### 4.1 Search engine (`backend/search/`)
1. **Eligibility filter** (§8 step 3): thresholds in `config/scoring/terrain-v1.yaml`. Purpose `exposed_terrain` drops windows on valid fraction, water, and built-up. Snow/ice and vegetation are flags.
2. **Retrieval** (D-020): z-score `slope_median`, `slope_p90`, `relief`, and `roughness` using eligible windows of the region being searched. The histogram is not in the tree. Shortlist `10 × top_k`. Read `features.parquet` for that region and `scale_m` only, and refuse the search if its SHA-256 does not match the processing run.
3. **Rerank** (§9.1, D-021):
   - Scalar features: `similarity_i = 100 * max(0, 1 - |earth_i - target_i| / tolerance_i)`
   - Slope histogram: Wasserstein-1 in degrees, `∫|CDF_earth − CDF_target| ds` from 0° to 90°. Not histogram intersection, and not bin index.
   - Relief and roughness tolerances use the floors in the yaml. Store the absolute tolerance used.
   - Weighted mean **only over mandatory features available for both**; a candidate missing a mandatory feature is excluded, not scored higher (§8 step 6).
   - Tolerances and weights from `config/scoring/terrain-v1.yaml`; config hash stored with every result.
4. **Spatial grouping** (D-021): greedy non-maximum suppression, IoU > 0.3, tie-break higher score then smaller `cell_id`. Merge survivors whose intersection area is still > 0. Keep member windows and their individual scores. Worked example in [docs/SCORING.md](docs/SCORING.md).
5. **Novelty check** (§3 novelty policy, D-022): intersect with `known_analog_registry`; assign status `documented_analog` / `not_in_checked_records` / `under_review`; store which registry version and review date were checked. Exclude documented ones from `candidates`; return them in `reference_matches`.
6. **Explanations** (§8 step 8): deterministic templates from measured differences, e.g. *"Median slope 7.9° vs target 8.4° (within tolerance); relief 410 m vs 620 m (similarity 32, main mismatch); geology not available."*

### 4.2 Jobs
Hackathon (D-017): `POST /searches` validates and runs in the request. `retrieval_mode` accepts only `baseline`. It writes `search_jobs.status = completed` and returns the search id. The client calls `GET /searches/{id}/candidates` and does not poll. Missing features return HTTP 409 `features_not_ready`. Processing stays the CLI. The cache key is still hash(target profile version, Earth feature version, filters, scoring version), and a repeat of that key returns the stored result.

Full design, later: a miss may return 202 and a Celery job with states `queued, running, completed, partially_completed, failed, cancelled`. Do not build that path in the hackathon.

Idempotency of a processing run: input checksums + config version (§15).

### 4.3 API (§12)
Implement all listed endpoints with Pydantic schemas; OpenAPI published. Add:
- Pagination on `/searches/{id}/candidates`.
- `GET /candidates/{id}/evidence` returns feature table, member windows, sources, versions, coverage, mismatches, unavailable evidence.
- Auth: shared demo token for review endpoints in the hackathon. OIDC is later. Read endpoints are public within the deployment.
- Limits: max search area, max `top_k`, per-user concurrent jobs (§15).

### 4.4 Frontend
Pages:
1. **Search setup:** target picker (with planetary preview image), the two pilot regions, purpose `exposed_terrain`, top-k. Drawing a search area is later.
2. **No progress page in the hackathon.** The search returns `completed` or 409.
3. **Results map:** MapLibre with candidate regions coloured by score, member windows on hover, `reference_matches` as a layer that the Atacama demo turns on.
4. **Comparison panel:** side-by-side target preview vs Earth hillshade, per-feature bars (Earth vs target vs tolerance), slope histogram overlay, mismatch & missing-evidence list, novelty status badge.
5. **Sources panel:** provenance (asset IDs, resolutions, processing versions).
6. **Export:** CSV + GeoJSON with full search configuration embedded.

UI rule: never show a single "probability" — label scores as "configured similarity (terrain-v1)".

**Exit criteria:** end-to-end flow from §13 works for the Mars target on the pilot region; results reproducible from the exported configuration.

---

## 5. Data model (Alembic migrations)

| Table | Key columns |
|---|---|
| `source_assets` | id, provider, body, footprint (geometry, body-specific SRID or WKT + body), resolution_m, source_version, sha256, storage_uri, access_meta (jsonb) |
| `processing_runs` | id, kind, inputs (jsonb), code_version, config_hash, status, error, started_at, finished_at |
| `earth_cells` | id, region_id, grid_version, boundary (geometry 4326), footprint_m, parent_id |
| `feature_profiles` | id, owner_type (cell/target), owner_id, schema_version, scale_m, values (jsonb), availability (jsonb), source_asset_ids, run_id |
| `planetary_targets` | id, body, name, boundary (WKT + body CRS), description, preview_uri |
| `search_jobs` | id, cache_key, request (jsonb), scoring_version, status, progress, error, timestamps |
| `candidate_matches` | id, search_id, rank, region_geom, member_cell_ids, component_scores (jsonb), total_score, novelty_status, explanation |
| `known_analog_registry` | id, name, boundary, body_target_relevance, references (jsonb), registry_version, review_date |
| `review_records` | id, candidate_id, reviewer_id, decision, evidence (jsonb), novelty_status, created_at |

Note: PostGIS geometry is Earth-oriented; store planetary geometries as WKT/GeoJSON with an explicit body + CRS column rather than forcing an Earth SRID.

---

## 6. Phase 3 — Novelty and validation (≈3 weeks)

1. **Known-analog registry:** import documented sites (USGS "Known Terrestrial Analog Sites for Planetary Science" dataset first, then NASA Planetary Analog Explorer and literature) with boundaries, references, `registry_version`, review date. Admin import CLI + review UI.
2. **Review workflow:** `POST /candidates/{id}/reviews`; reviewer roles; status transitions `not_in_checked_records → under_review → documented_analog | rejected | promising`; full audit trail.
3. **Validation harness** (`backend/eval/`):
   - Geographic holdouts: split by region blocks; buffer to prevent overlapping windows leaking across splits.
   - Benchmarks: does the baseline rank documented analogs highly for their known targets? (recall@k on reference cases — they are a test set, not the candidate universe).
   - Negative controls: clearly dissimilar terrain (flat farmland, ocean margins) must score low.
   - Sensitivity: sweep weights, tolerances, window size, stride, resolution; report rank stability (Kendall τ / top-k overlap).
4. **Reproducible exports:** export bundle = results + config + versions + registry version; a re-run tool that verifies identical output.

**Exit criteria:** evaluation report in `docs/eval/baseline-v1.md`; review workflow usable by an external reviewer.

---

## 7. Phase 4 — Broader evidence (ongoing)

- Add lunar target (if not completed in Phase 1) and more targets.
- Expand Earth coverage region by region; track spatial search coverage metric.
- Geology adapter using the Macrostrat API (broad lithology categories) with a categorical similarity function; optional only where coverage is reliable.
- Higher-resolution planetary DEMs for specific targets (e.g. HRSC or CTX stereo DEMs on Mars, LOLA polar DEMs on the Moon) where they exist.
- Thermal (Diviner surface temperature vs Earth **land surface** temperature, not air temperature) and illumination profiles with explicit time windows.
- Fieldwork logistics layer (access roads, permits) displayed separately from similarity.

---

## 8. Cross-cutting work

**Testing**
- Unit: features (golden synthetic DEMs), scoring, grouping, novelty logic, cache keys.
- Property tests: no upsampling path exists; missing values never score as matches.
- Integration: pipeline on a tiny fixture region; API end-to-end against docker compose.
- Frontend: Playwright smoke tests for search → results → evidence.

**Operations (§15)**
- Structured logs with credential redaction; per-job logs stored and surfaced.
- Metrics: preprocessing throughput, job failure rate, query latency, storage growth, valid-data fraction.
- Partial coverage: if a source fails, job → `partially_completed` with the failed source listed.
- Raster data only in object storage; DB holds references.

### 8.1 Documentation (written alongside the code, not at the end)

| File | Contents |
|---|---|
| `README.md` | What the app does, screenshot, 5-minute local quickstart, links to everything below |
| `docs/WALKTHROUGH.md` | End-to-end walkthrough: follow one search from the UI click → API → retrieval → scoring → grouping → novelty check → evidence panel, naming the exact files and functions at each step. Also: how data gets from a raw DEM to a feature row |
| `docs/ARCHITECTURE.md` | Component diagram (Mermaid), data flow, what runs offline vs online, hackathon vs full design differences |
| `docs/DATA_SOURCES.md` | Every dataset: URL, version, resolution, license, how we fetch it, known gaps (the §0.1 tables, kept up to date) |
| `docs/SCORING.md` | Formulas, tolerances, weights, why missing data never raises a score, how to add a feature |
| `docs/DEPLOYMENT.md` | GCP setup and every VM script, with what each one does and how to recover from failures |
| `docs/DEMO.md` | The demo script, pre-demo checklist, fallback (screenshots / recorded video) if the network fails |
| `docs/LIMITATIONS.md` | §17 non-goals and novelty policy in plain language; also shown in the app's About page |
| `docs/data-audit.md` | Phase 1 audit results |
| `docs/DECISIONS.md` | The only decision log (D-024). Do not also create `docs/adr/` |
| `CONTRIBUTING.md` | Branching, commit style, how to run tests and linters, PR checklist |
| `ATTRIBUTIONS.md` | Required credits: Copernicus DEM © DLR/Airbus, ESA WorldCover, USGS/NASA (SLDEM2015, MOLA), ESA/DLR/FU Berlin (HRSC, CC BY-SA 3.0 IGO), EOX Sentinel-2 cloudless, OpenFreeMap/OpenStreetMap, Macrostrat, FABDEM |
| `CHANGELOG.md` | One line per meaningful change; helps the final presentation |

**AI-agent instructions and skills**

| File | Contents |
|---|---|
| `CLAUDE.md` | Repo map, how to run/test, hard rules (never upsample DEMs, keep Earth/Moon/Mars CRSs separate, missing data is never a match, no secrets in frontend, no ML for now) |
| `.claude/skills/design-taste-frontend/` | tasteskill 2.5.1, already installed. Visual craft for the UI. The evidence panel and scientific-copy win when a landing-page rule conflicts (D-024) |
| `.claude/skills/geo-pipeline/SKILL.md` | Project skill: how to add a data source or feature correctly (CRS per body, resolution matching, provenance rows, synthetic-DEM test required) |
| `.claude/skills/run-app/SKILL.md` | Project skill: how to start the stack locally, seed fake data, and run the VM scripts |
| `.claude/skills/scientific-copy/SKILL.md` | Project skill: wording rules for UI text and docs — "configured similarity", "not in checked records", never "discovered" or "probability" |

### 8.2 Scripts to run the app on the VM

All VM scripts are idempotent (safe to re-run) and print what they do. Bash scripts run on the VM or via `gcloud compute ssh`; laptop wrappers are PowerShell.

| Script | Runs on | What it does |
|---|---|---|
| `scripts/local/check-tools.ps1` | Laptop | Checks git, uv, node, Docker, gcloud, free disk, virtualization; prints install commands for anything missing |
| `scripts/local/dev.ps1` | Laptop | `docker compose up` for local dev, runs migrations, seeds a small fake feature file |
| `scripts/vm/create-vm.sh` | Laptop (Git Bash) | Enables APIs; creates the Cloud Storage bucket, service account (bucket access only), static IP, firewall rules (22 from your IP only, 80/443 public), and the e2-standard-4 VM with a 200 GB disk |
| `scripts/vm/bootstrap.sh` | VM (first time) | Installs Docker + Compose, creates the deploy key and prints it for GitHub, clones the repo, generates `.env` with random DB password and demo token, sets up a nightly backup cron |
| `scripts/vm/deploy.sh` | VM | `git pull` → build images → run Alembic migrations → `docker compose -f infra/docker-compose.prod.yml up -d` → health-check `/health`; rolls back to the previous image tag if the check fails |
| `scripts/vm/process-region.sh <region> <target>` | Laptop | Resizes the VM to e2-standard-8, runs `pipeline run` inside the backend image (for example `earth_sahara mars_jezero`), syncs outputs to the bucket, resizes back to e2-standard-4 |
| `scripts/vm/backup-db.sh` | VM (cron) | `pg_dump` → gzip → Cloud Storage, keeps the last 7 |
| `scripts/vm/restore-db.sh <backup>` | VM | Restores a chosen backup |
| `scripts/vm/start.sh` / `stop.sh` | Laptop | Start / stop the VM (stop when idle to save credits) |
| `scripts/vm/status.sh` | Laptop | VM state, container health, disk use, public URL |
| `scripts/vm/logs.sh [service]` | Laptop | Tails container logs over SSH |
| `scripts/vm/ssh.sh` | Laptop | Shortcut for `gcloud compute ssh` with the right zone/project |

Configuration (project ID, zone, VM name, bucket) lives in one file, `scripts/vm/config.env`, so no script has hard-coded values.

### 8.3 Other documentation
- Inline docstrings on every public function in `core/`; OpenAPI docs served at `/docs` by FastAPI.

---

## 9. Timeline summary

| Phase | Duration (1–2 devs) | Key output |
|---|---|---|
| 0 Foundations | 1 wk | Running stack, schema, CI |
| 1 Data + baseline | 3–4 wks | Reproducible features for Mars target + pilot region |
| 2 Discovery app | 4 wks | End-to-end search, map, evidence |
| 3 Novelty + validation | 3 wks | Registry, review workflow, eval report |
| 4 Broader evidence | ongoing | More targets, geology, thermal |

Full MVP (Phases 0–2) ≈ 8–9 weeks. The hackathon slice in §0.2 is designed to fit a few days with 3–4 people.

---

## 10. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Planetary DEM resolution limits what can be compared | Use the 200 m blended DEM (not 463 m MOLA); window size is config; finer target DEMs in Phase 4 |
| Earth DEM artefacts (voids, forests in DSM) bias roughness | WorldCover masks + valid-fraction threshold; GLO-30 is a surface model, so flag vegetated windows; FABDEM cross-check if non-commercial |
| Free public services change or disappear (OpenFreeMap, Planetary Computer, Earth Search) | Adapters with fallbacks; cache all fetched source files in our own object storage |
| Share-alike terms on HRSC data | Credit sources; publish derived Mars DEM products under CC BY-SA if redistributed |
| Scores look like probabilities to users | Labelled "configured similarity", versioned, tolerances visible |
| Missing features inflate scores | Score only over common mandatory features; exclusion rule tested |
| Stale cached results after source/model change | Cache key includes all versions (§11) |
| Provider access changes | Adapter layer, retries, partial-coverage status |
| Compute cost of large regions | Area/job limits; pilot regions only until profiled |

---

## 11. Open questions to resolve

These do not block Phase 0.

1. How long is the hackathon, and how many developers? (Sets which "Should" items in the hackathon MVP make it in.)
2. Confirm non-commercial status. Needed before using FABDEM, EOX tiles, or Earth Engine's free tier. The core DEMs do not depend on it.
3. Extents are set in `config/grids/pilot-v1.yaml` and `config/targets/`. Swap them there to change a box. No answer is required before scaffolding.
