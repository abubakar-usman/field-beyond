# Changelog

One line per meaningful change, newest first.

## 2026-11-14
- Docker run scripts (`scripts/docker/up|down|logs`, bash and PowerShell). Local Compose: named data volume, MinIO behind `--profile storage`, no host DB port. Fixed: backend image Python selection, frontend image missing `public/` (map worker), BOM in PowerShell-written `.env`, duplicate target profiles on repeated `load-db`.
- Phases 0–3 code: `core/` (bodies, config, grid, raster, features, scoring, artifacts), `pipeline/` CLI (seed-fake, run, target, import-registry, load-db, push/pull, benchmark, verify-export), FastAPI backend with memory and PostGIS stores, Alembic migration #1, Next.js + MapLibre frontend with the evidence panel, Docker Compose (local and prod), Caddy, CI, VM and laptop scripts. 123 tests pass. Real-data runs and Docker have not been exercised yet. Decisions D-025–D-030.
- Resolved the planning contradictions: no queue in the hackathon scaffold, synchronous search, canonical ids and extents in `config/`, parquet as the only search index, 60 m Moon grid, scoring rules (histogram, grouping, tolerance floors, one purpose), and the Atacama benchmark definition. Decisions D-016–D-024.
- Planning docs written: implementation plan, system design copy, decisions, architecture, walkthrough (planned), data sources, scoring, deployment, local setup, manual steps, demo, limitations, glossary, project skills.
- Decisions: no ML for now; hackathon thin slice first; Copernicus / SLDEM2015 / MOLA–HRSC data; Jezero + Taurus–Littrow targets; Atacama + Western Sahara pilots; Google Cloud single VM; non-commercial.
