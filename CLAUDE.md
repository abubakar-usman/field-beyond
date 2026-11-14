# CLAUDE.md — instructions for AI coding agents

## What this project is
Earth Analog Explorer: a web app that finds Earth regions whose **terrain** resembles a chosen Moon or Mars target, and explains the match. Hackathon project, non-commercial, hosted on one Google Cloud VM.

## Read first (in this order)
1. [docs/HANDOFF.md](docs/HANDOFF.md) — current state and next steps
2. [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) — especially §0 (decisions), §0.2 (hackathon MVP)
3. [docs/DECISIONS.md](docs/DECISIONS.md) — don't reopen settled decisions without a reason
4. The doc for the area you're touching: SCORING, DATA_SOURCES, ARCHITECTURE, DEPLOYMENT

## Current state
Planning only — no application code exists yet. Phase 0 (scaffold) is next. Update `docs/HANDOFF.md` "Current state" and `CHANGELOG.md` whenever you finish a meaningful piece of work.

## Hard rules (never break these)
1. **No machine learning** for now: no embeddings, encoders, pgvector/FAISS, PyTorch, or LLM-generated summaries. Retrieval is numeric nearest-neighbour + the transparent formula in docs/SCORING.md.
2. **Never upsample** a DEM. Earth 30 m data is aggregated *down* to the target's resolution (~59 m Moon, ~200 m Mars). Add an assertion wherever resampling happens.
3. **Keep Earth, Moon and Mars coordinate systems separate.** Use each body's own radius for distances and slope. Never put lunar/Martian coordinates on an Earth basemap — planetary targets are shown as pre-rendered images.
4. **Missing data is never a match.** Score only over mandatory features available on both sides; a window missing a mandatory feature is excluded, not scored higher. Missing values stay explicit (null + availability mask), never filled.
5. **Wording:** scores are "configured similarity (terrain-v1)", never "probability" or "confidence". Unlisted places are "not in checked records", never "new discovery". See `.claude/skills/scientific-copy/SKILL.md`.
6. **Provenance on everything derived:** source asset IDs, code version (git SHA), config hash, schema version.
7. **No secrets in the frontend or in git.** Secrets live in `.env` (gitignored) on the server. Only approved data hosts in `config/sources.yaml` may be fetched (SSRF guard).
8. **Licences:** keep `ATTRIBUTIONS.md` correct and visible in the app. FABDEM and EOX tiles are non-commercial only.
9. Tolerances, weights, window size, stride and thresholds live in config files, versioned — never hard-coded.

## Planned repo layout
See IMPLEMENTATION_PLAN.md §1. Key dirs: `core/` (shared pure Python: bodies, raster, features, scoring, grid), `pipeline/` (offline CLI), `backend/` (FastAPI), `frontend/` (Next.js + MapLibre), `config/`, `infra/`, `scripts/local` (PowerShell), `scripts/vm` (bash).

## Tooling conventions
- Python 3.12 managed by **uv** (the laptop's system Python 3.14 is too new for some geospatial wheels — don't use it).
- Lint/format: ruff; types: mypy; tests: pytest. Frontend: TypeScript strict, ESLint, Prettier.
- Every feature function in `core/features/` needs a synthetic-DEM test with an analytically known answer, run for all three bodies.
- The development laptop is **Windows** (PowerShell + Git Bash, no WSL yet, 64 GB free disk). Heavy data processing happens on the GCP VM, not the laptop.
- Shell scripts for the VM are bash, idempotent, and read settings from `scripts/vm/config.env`.

## Frontend design
Use the `design-taste-frontend` skill (taste-skill) once installed in `.claude/skills/`. Map-first layout; evidence panel is the hero of the UI; show tolerances and missing data openly.

## When unsure
Prefer the simpler hackathon option in IMPLEMENTATION_PLAN.md §0.2. Record any new decision in docs/DECISIONS.md.
