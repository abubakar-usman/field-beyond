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
| Laptop tools | ⚠️ uv 0.13.8 + Python 3.12.16 installed (uv lives under `%LOCALAPPDATA%\Microsoft\WinGet\Packages\astral-sh.uv_*`; open a new terminal for `uv` on PATH). WSL2, Docker Desktop, gcloud still missing; CPU virtualisation is off in firmware — [LOCAL_SETUP.md](LOCAL_SETUP.md) |
| Owner's manual steps (GCP project, billing, gcloud login) | ⏳ Not done yet — [MANUAL_STEPS.md](MANUAL_STEPS.md) |
| Git repository | ✅ `main` tracks `git@github.com:abubakar-usman/field-beyond` |
| Config (ids, boxes, scoring, hosts, products) | ✅ `config/grids`, `config/scoring`, `config/targets`, `config/sources.yaml`, `config/products-v1.yaml` (product URLs to re-check in the data audit) |
| Phase 0 scaffold | ✅ uv project (D-025), `core/bodies.py`, FastAPI `/health`, Alembic migration #1 (all §5 tables; compiles to SQL offline), Compose (PostGIS, MinIO + bucket init, API, frontend), CI workflow, pre-commit. **Not run:** `docker compose up` (no Docker here) |
| Phase 1 pipeline | ✅ Code + tests: grid windows, no-upsampling warp, Horn slope / relief / roughness / histogram with synthetic-DEM tests on Earth, Moon, Mars; Copernicus + WorldCover + SLDEM2015 + MOLA–HRSC adapters behind the allowlist; native-10 m land-cover counts; `pipeline run/target`. **Not run on real data yet** |
| Phase 2 app | ✅ Search engine (filter → 4-scalar shortlist → rerank → NMS/merge → novelty → explanation), all hackathon endpoints + rescore + CSV/GeoJSON export, Next.js + MapLibre map, evidence panel. Checked in the browser on synthetic data (memory store) |
| Phase 3 | ✅ Registry import (CSV/GeoJSON, point buffers recorded as assumptions), review workflow with transitions + demo token, benchmark report (positives, low-relief controls, ±20 % sensitivity), `verify-export`. The real USGS registry is not imported yet |
| Data on disk | ⚠️ `data/processed/` holds **synthetic** 200 m features for both regions and synthetic target profiles (`pipeline seed-fake`). No 60 m features yet, so Moon searches return 409 until `seed-fake --scale 60` or a real run |
| VM scripts | ✅ Written to [DEPLOYMENT.md](DEPLOYMENT.md); syntax-checked only. **Not run against GCP** |
| `SqlStore` / `pipeline load-db` | ⚠️ Written, never run against PostGIS |
| Tests | ✅ 123 pytest tests, ruff, mypy clean; frontend lint, typecheck and production build clean |

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
1. Owner: [MANUAL_STEPS.md](MANUAL_STEPS.md) Day-0 items (enable VT-x, WSL2, Docker Desktop, gcloud, GCP project, billing, budget alert). Confirm non-commercial status (EOX, FABDEM).
2. With Docker: `bash scripts/docker/up.sh` or `scripts\docker\up.ps1` (builds images, starts, seeds, loads PostGIS) — first real check of Compose, the migration on PostGIS, `pipeline load-db` and `SqlStore`. Pinned images to confirm: `postgis/postgis:16-3.4`, `minio/minio:RELEASE.2025-04-22T22-12-26Z`, `minio/mc:RELEASE.2025-04-16T18-13-26Z`, `ghcr.io/astral-sh/uv:0.13.8`.
3. Data audit (`docs/data-audit.md`): open each URL in `config/products-v1.yaml`; confirm SLDEM2015 and the MOLA–HRSC blend open by range request and report the expected CRS; check Jezero has HRSC coverage.
4. `uv run pipeline target --target mars_jezero` (small, works from the laptop), then `scripts/vm/create-vm.sh` (costs money — owner confirms) and `scripts/vm/process-region.sh earth_sahara mars_jezero`.
5. Import the USGS Known Terrestrial Analog Sites file with `pipeline import-registry` (map its column names with the flags), then run `pipeline benchmark --region earth_atacama --target mars_jezero --out docs/eval/baseline-v1.md`.
6. Should list: Earth hillshade beside the target preview, weight sliders (API `POST /searches/{id}/rescore` exists), Moon at 60 m.

## 6. Where things are
| Path | What |
|---|---|
| `IMPLEMENTATION_PLAN.md` | The plan |
| `CLAUDE.md` | Rules for AI agents |
| `docs/` | All guides |
| `.claude/skills/` | Project skills (geo-pipeline, run-app, scientific-copy) and design-taste-frontend |
| `core/` `pipeline/` `backend/` `frontend/` | Code; file-by-file flow in [WALKTHROUGH.md](WALKTHROUGH.md) |
| `infra/` `scripts/` | Compose files, Caddyfile, `.env.example`; laptop (PowerShell) and VM (bash) scripts |
| `data/processed/` | Pipeline outputs (gitignored); layout in `core/artifacts.py` |
| Original PDF | `C:\Users\Resident\Downloads\earth_analog_explorer_system_design.pdf` (owner's machine; Markdown copy in docs/SYSTEM_DESIGN.md) |
