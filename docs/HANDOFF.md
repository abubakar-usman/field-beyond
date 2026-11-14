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
| Laptop tools | ⚠️ uv, WSL2, Docker Desktop, gcloud missing — [LOCAL_SETUP.md](LOCAL_SETUP.md) |
| Owner's manual steps (GCP project, billing, GitHub) | ⏳ Not done yet — [MANUAL_STEPS.md](MANUAL_STEPS.md) |
| Git repository | ⏳ Not initialised |
| taste-skill | ⏳ Not installed (needs `npx skills add`, see §5) |
| Application code | ⏳ None yet |
| VM scripts | ⏳ Specified in [DEPLOYMENT.md](DEPLOYMENT.md), not written |

## 3. Key decisions (short version — details in DECISIONS.md)
- **No machine learning for now.** Transparent numeric matching only.
- **Hackathon first:** build the thin slice in IMPLEMENTATION_PLAN.md §0.2; the phased plan is the longer roadmap.
- **Data (all free, no API keys):** Copernicus DEM GLO-30 (Earth), ESA WorldCover (Earth masks), SLDEM2015 (Moon, 59 m), MOLA–HRSC blended DEM (Mars, 200 m), USGS Known Terrestrial Analog Sites (registry seed).
- **Targets:** Mars — Jezero crater; Moon — Apollo 17 Taurus–Littrow valley.
- **Pilot regions:** Atacama + Altiplano (benchmark, many known analogs); Western Sahara, Mauritania/Mali (discovery, few known analogs).
- **Hosting:** Google Cloud credits — one e2-standard-4 VM with Docker Compose + Cloud Storage bucket. ~$5–15 for a hackathon week if stopped when idle.
- **Licensing:** non-commercial (unlocks FABDEM and free EOX satellite tiles).

## 4. Open questions (ask the owner)
1. How long is the hackathon and how many developers?
2. Confirm non-commercial status.
3. Keep the default targets and pilot regions?

## 5. What to do next (in order)
1. Owner completes [MANUAL_STEPS.md](MANUAL_STEPS.md) Day-0 items (tools, GCP project, budget alert, GitHub repo).
2. `git init` (a `.gitignore` already exists), first commit with these docs, push to the GitHub repo.
3. Install taste-skill into the repo:
   ```bash
   npx skills add https://github.com/Leonxlnx/taste-skill --skill design-taste-frontend
   ```
   Check it landed in `.claude/skills/`, then commit it. Check the repo README for the current install command first.
4. **Phase 0 scaffold** (IMPLEMENTATION_PLAN.md §2): uv workspace, `core/` package with `bodies.py`, FastAPI `/health`, Next.js blank page, PostGIS in Docker Compose, Alembic migration #1, `scripts/local/check-tools.ps1`.
5. Fake feature file with the real schema so backend and frontend can start before real data exists.
6. Data/geo track: download Jezero DEM subset + Copernicus tiles for one pilot region; implement features with synthetic-DEM tests.
7. Write `scripts/vm/*` and deploy early (a blank app on a public URL by day 1–2).

## 6. Where things are
| Path | What |
|---|---|
| `IMPLEMENTATION_PLAN.md` | The plan |
| `CLAUDE.md` | Rules for AI agents |
| `docs/` | All guides |
| `.claude/skills/` | Project skills (geo-pipeline, run-app, scientific-copy) + taste-skill once installed |
| Original PDF | `C:\Users\Resident\Downloads\earth_analog_explorer_system_design.pdf` (owner's machine; Markdown copy in docs/SYSTEM_DESIGN.md) |
