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

### With Docker (any machine: Windows, macOS, Linux)

Needs only **git** and **Docker** (Docker Desktop on Windows/macOS; Docker Engine + the Compose plugin on Linux). No Python or Node on the host.

```bash
git clone https://github.com/abubakar-usman/field-beyond.git
```
```bash
cd field-beyond
```

Linux / macOS / Git Bash:

```bash
bash scripts/docker/up.sh
```

Windows PowerShell:

```bash
powershell -ExecutionPolicy Bypass -File scripts\docker\up.ps1
```

The script creates `.env` with random local secrets, builds the `eae-backend` and `eae-frontend` images, starts PostGIS, the API and the frontend, waits for the API, seeds **synthetic** demo features (2-4 min) and loads them into PostGIS. Then open:

- App: http://localhost:3000
- API docs: http://localhost:8000/docs

Options: `--moon` / `-Moon` adds 60 m data for the Moon target (about 15 min more); `--reseed` / `-Reseed` regenerates the data; `--no-seed` / `-NoSeed` only starts; `--storage` / `-Storage` also starts MinIO. Ports 3000 and 8000 can be changed with `APP_PORT` and `API_PORT` in `.env`.

| Task | Linux / macOS | Windows PowerShell |
|---|---|---|
| Logs | `bash scripts/docker/logs.sh backend` | `powershell -File scripts\docker\logs.ps1 backend` |
| Stop (keep data) | `bash scripts/docker/down.sh` | `powershell -File scripts\docker\down.ps1` |
| Stop and delete data | `bash scripts/docker/down.sh --wipe` | `powershell -File scripts\docker\down.ps1 -Wipe` |

The UI labels the seeded data as synthetic: it is generated terrain, not measurements.

### Without Docker (Windows laptop, uv + Node)

```bash
powershell -ExecutionPolicy Bypass -File scripts/local/dev.ps1 -NoDocker
```

This uses the in-memory store (D-027) instead of PostGIS. By hand: `uv sync`, `uv run pipeline seed-fake --scale 200`, `uv run uvicorn backend.main:app --port 8000`, `npm --prefix frontend run dev`.

Checks: `uv run pytest`, `uv run ruff check .`, `uv run mypy`, `npm --prefix frontend run lint`, `npm --prefix frontend run typecheck`.

### Real data

Runs on the GCP VM (downloads Copernicus tiles and reads the planetary DEMs by range request); see [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md):

```bash
scripts/vm/process-region.sh earth_sahara mars_jezero
```

## Tech stack

Next.js + TypeScript + MapLibre · FastAPI + Pydantic · Python 3.12 (uv) with Rasterio, NumPy, pandas/PyArrow, Shapely, PyProj · PostgreSQL + PostGIS · Docker Compose · Google Cloud (Compute Engine + Cloud Storage).
