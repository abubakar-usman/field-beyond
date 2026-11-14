# Earth Analog Explorer

Find places on Earth whose **terrain** resembles a chosen spot on the Moon or Mars — and explain, feature by feature, why they match, where they differ, and what data is missing.

Hackathon project · non-commercial · hosted on Google Cloud.

> **Status (Nov 2026): Phases 0–3 coded and tested on synthetic data.** Real-data runs, Docker and the VM are next. See [docs/HANDOFF.md](docs/HANDOFF.md).

## How it works (one paragraph)

An offline pipeline downloads free elevation data (Copernicus DEM for Earth, SLDEM2015 for the Moon, MOLA–HRSC for Mars), cuts Earth pilot regions into overlapping 10 km windows, and computes the same terrain measurements for every window and for each planetary target: slope distribution, relief, roughness. The web app lets a user pick a target; the backend finds the Earth windows with the closest measurements, scores them with a transparent formula, merges overlapping hits, checks them against a registry of already-documented analog sites, and shows the results on a map with an evidence panel. Places not in the registry are labelled **"not in checked records"** — never "discovered".

## Documentation map

| Read this | For |
|---|---|
| [docs/HANDOFF.md](docs/HANDOFF.md) | **Start here.** Current state, decisions made, what to do next |
| [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) | Full plan: decisions, data sources, pricing, hackathon MVP, phases, scripts |
| [docs/SYSTEM_DESIGN.md](docs/SYSTEM_DESIGN.md) | Original system design (source of the idea) |
| [docs/DECISIONS.md](docs/DECISIONS.md) | Every decision with its reason (lightweight ADR log) |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Components, data flow, hackathon vs full architecture |
| [docs/WALKTHROUGH.md](docs/WALKTHROUGH.md) | Follow one search through the system, file by file |
| [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md) | Datasets, URLs, licenses, access, gotchas |
| [docs/SCORING.md](docs/SCORING.md) | Features, formulas, tolerances, missing-data rules |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | Google Cloud setup and VM scripts |
| [docs/LOCAL_SETUP.md](docs/LOCAL_SETUP.md) | Laptop tools: what's installed, what's missing |
| [docs/MANUAL_STEPS.md](docs/MANUAL_STEPS.md) | Things only the project owner can do (accounts, billing, sign-ins) |
| [docs/DEMO.md](docs/DEMO.md) | Demo script and pre-demo checklist |
| [docs/LIMITATIONS.md](docs/LIMITATIONS.md) | What the app does **not** claim |
| [docs/GLOSSARY.md](docs/GLOSSARY.md) | Terms: DEM, analog, window, relief, roughness… |
| [CLAUDE.md](CLAUDE.md) | Rules for AI coding agents working in this repo |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Branches, commits, tests, PR checklist |
| [ATTRIBUTIONS.md](ATTRIBUTIONS.md) | Required data credits |
| [CHANGELOG.md](CHANGELOG.md) | What changed, when |

## Quickstart

Without Docker (in-memory store; works on the Windows laptop today):

```bash
powershell -File scripts/local/dev.ps1 -NoDocker
```

With Docker (PostGIS + MinIO + API + frontend):

```bash
powershell -File scripts/local/dev.ps1
```

Then open http://localhost:3000 (API docs at http://localhost:8000/docs). Both modes seed **synthetic** features first, and the UI labels them as synthetic.

By hand:

```bash
uv sync
```
```bash
uv run pipeline seed-fake --scale 200
```
```bash
uv run uvicorn backend.main:app --port 8000
```
```bash
npm --prefix frontend run dev
```

Checks: `uv run pytest`, `uv run ruff check .`, `uv run mypy`, `npm --prefix frontend run lint`, `npm --prefix frontend run typecheck`.

Real data (on the VM; downloads Copernicus tiles and reads the planetary DEMs by range request):

```bash
uv run pipeline run --region earth_sahara --target mars_jezero
```

## Tech stack

Next.js + TypeScript + MapLibre · FastAPI + Pydantic · Python 3.12 (uv) with Rasterio, NumPy, pandas/PyArrow, Shapely, PyProj · PostgreSQL + PostGIS · Docker Compose · Google Cloud (Compute Engine + Cloud Storage).
