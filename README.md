# Earth Analog Explorer

Find places on Earth whose **terrain** resembles a chosen spot on the Moon or Mars — and explain, feature by feature, why they match, where they differ, and what data is missing.

Hackathon project · non-commercial · hosted on Google Cloud.

> **Status (Nov 2026): planning complete, no code yet.** The next step is Phase 0 scaffolding. See [docs/HANDOFF.md](docs/HANDOFF.md).

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

_Not available yet — will be filled in during Phase 0._ Planned:

```bash
uv sync
```
```bash
docker compose -f infra/docker-compose.yml up -d
```
```bash
uv run pipeline seed-fake
```

Then open http://localhost:3000.

## Tech stack

Next.js + TypeScript + MapLibre · FastAPI + Pydantic · Python 3.12 (uv) with Rasterio, NumPy, GeoPandas, Shapely, PyProj, scikit-learn · PostgreSQL + PostGIS · Docker Compose · Google Cloud (Compute Engine + Cloud Storage).
