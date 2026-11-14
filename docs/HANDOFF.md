# Handoff — start here

Everything a new teammate or AI agent needs to pick up this project.

## 1. The idea in three sentences
Scientists and engineers use places on Earth that resemble the Moon or Mars ("analogs") to test equipment and study geology, but they mostly reuse the same known sites. This app searches broad Earth regions automatically for terrain that measurably matches a specific lunar or Martian location. It explains every match feature by feature and labels places not found in known-analog records as candidates for review, never as confirmed discoveries.

## 2. Current state (update this section as work lands)

| Item | State |
|---|---|
| System design | ✅ Done — [SYSTEM_DESIGN.md](SYSTEM_DESIGN.md) |
| Implementation plan | ✅ Done — [../IMPLEMENTATION_PLAN.md](../IMPLEMENTATION_PLAN.md) |
| Decisions (data, hosting, scope) | ✅ Made — [DECISIONS.md](DECISIONS.md) |
| Documentation set | ✅ Written (planning versions) |
| Laptop tools | ⚠️ Owner's Windows laptop: uv, WSL2, Docker Desktop, gcloud missing — [LOCAL_SETUP.md](LOCAL_SETUP.md). This checkout also opens on Linux; bash and uv run there without WSL |
| Owner's manual steps (GCP project, billing, gcloud login) | ⏳ Not done yet — [MANUAL_STEPS.md](MANUAL_STEPS.md) |
| Git repository | ✅ `main` tracks `git@github.com:abubakar-usman/field-beyond` (commit `7f86ee7` at last check) |
| Config (ids, boxes, scoring, hosts) | ✅ `config/grids`, `config/scoring`, `config/targets`, `config/sources.yaml` |
| taste-skill | ✅ Installed at `.claude/skills/design-taste-frontend/` (tasteskill 2.5.1). Evidence panel wins on conflicts (D-024) |
| Application code | ⏳ None yet |
| VM scripts | ⏳ Specified in [DEPLOYMENT.md](DEPLOYMENT.md), not written |

## 3. Key decisions (short version — details in DECISIONS.md)
- **No machine learning for now.** Transparent numeric matching only.
- **Hackathon first:** build the thin slice in IMPLEMENTATION_PLAN.md §0.2; the phased plan is the longer roadmap.
- **Data (all free, no API keys):** Copernicus DEM GLO-30 (Earth), ESA WorldCover (Earth masks), SLDEM2015 (Moon, 59 m), MOLA–HRSC blended DEM (Mars, 200 m), USGS Known Terrestrial Analog Sites (registry seed).
- **Targets:** `mars_jezero` (10 km at the Perseverance landing site, 200 m); `moon_taurus_littrow` (10 km at the Apollo 17 lunar module, 60 m). Preview images show a wider area and are not scored.
- **Pilot regions:** `earth_atacama` (benchmark) and `earth_sahara` (discovery: eastern Western Sahara and northern Mauritania; Mali is outside the box). Extents are in `config/grids/pilot-v1.yaml`.
- **Hosting:** Google Cloud credits — one e2-standard-4 VM with Docker Compose + Cloud Storage bucket. The 200 GB disk is about $20/month even while the VM is stopped (~$5 in a stopped week). A hackathon week with the VM on for a few days is about $15–25. Stop it when idle, and keep the $50 budget alert.
- **Licensing:** non-commercial (unlocks FABDEM and free EOX satellite tiles).

## 4. Open questions (ask the owner)
1. How long is the hackathon and how many developers? Does not block Phase 0. It decides how far down the Should list gets built.
2. Confirm non-commercial status. Copernicus, WorldCover, SLDEM2015, and the MOLA–HRSC blend do not depend on it. EOX tiles and FABDEM do. Leave those unused until the owner confirms.
3. Default targets and boxes are now in `config/`. Swap them there if you want different extents. No answer is required before scaffolding.

## 5. What to do next (in order)
1. Owner completes the remaining [MANUAL_STEPS.md](MANUAL_STEPS.md) Day-0 items: laptop tools, GCP project, billing, budget alert, `gcloud auth login`. The GitHub repo already exists.
2. **Phase 0 scaffold** (IMPLEMENTATION_PLAN.md §2, decision D-016): uv workspace, `core/` with `bodies.py`, FastAPI `/health`, Next.js blank page, PostGIS and MinIO in Docker Compose, Alembic migration #1. No Redis, no Celery, no worker.
3. Fake `features.parquet` using the columns in `config/scoring/terrain-v1.yaml`, so the API and the map can start before real rasters exist.
4. Data/geo track: download the Jezero 10 km scored square plus its preview bbox, and Copernicus tiles for one pilot region. Features get synthetic-DEM tests on all three bodies.
5. Write `scripts/vm/*` and deploy early (a blank app on a public URL by day 1–2). `process-region.sh` runs the CLI in the backend image.

## 6. Where things are
| Path | What |
|---|---|
| `IMPLEMENTATION_PLAN.md` | The plan |
| `CLAUDE.md` | Rules for AI agents |
| `docs/` | All guides |
| `.claude/skills/` | Project skills (geo-pipeline, run-app, scientific-copy) and design-taste-frontend |
| Original PDF | `C:\Users\Resident\Downloads\earth_analog_explorer_system_design.pdf` (owner's machine; Markdown copy in docs/SYSTEM_DESIGN.md) |
