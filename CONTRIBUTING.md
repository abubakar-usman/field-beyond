# Contributing

## Branches and commits
- `main` is always deployable (the VM deploys `main`).
- Work on short branches: `feat/...`, `fix/...`, `docs/...`, `data/...`.
- Commit messages: imperative, short subject (`Add slope histogram feature`), body explains why if not obvious.

## Before opening a PR
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] `uv run mypy core backend pipeline`
- [ ] `uv run pytest`
- [ ] Frontend: `npm run lint` and `npm run build`
- [ ] New feature/function in `core/` has a test (synthetic DEM for features)
- [ ] No secrets, no large data files (rasters go to object storage, `data/` is gitignored)
- [ ] User-facing text follows `.claude/skills/scientific-copy/SKILL.md`
- [ ] Docs updated: `docs/WALKTHROUGH.md` if a flow changed, `docs/SCORING.md` if scoring changed, `docs/DECISIONS.md` for new decisions, one line in `CHANGELOG.md`
- [ ] `docs/HANDOFF.md` "Current state" updated if a milestone finished

## Code style
- Python: type hints everywhere, pure functions in `core/`, no I/O in feature code, config via pydantic-settings.
- TypeScript: strict mode, API types generated from FastAPI's OpenAPI schema.
- Config values (tolerances, thresholds, window size) live in `config/`, never inline.
