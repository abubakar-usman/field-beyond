# Manual steps (owner only)

Things that need the owner's accounts, money, sign-ins or judgement. AI agents can't do these — ask the owner. Tick them off here as they're done.

## Day 0 — before coding
- [ ] Install missing tools — [LOCAL_SETUP.md](LOCAL_SETUP.md) (WSL2 needs admin + restart; Docker Desktop terms acceptance)
- [ ] If WSL/Docker fails: enable Intel VT-x virtualization in BIOS/UEFI
- [ ] GCP: confirm hackathon credits are attached to a billing account
- [ ] GCP: create project (suggested ID `earth-analog-explorer`) and link billing
- [ ] GCP: **budget alert** $50 with alerts at 50/90/100% (Billing → Budgets & alerts)
- [ ] Laptop: `gcloud auth login` and `gcloud config set project <id>` (browser sign-in)
- [ ] (Optional) Register the project for Earth Engine non-commercial use, Community tier (code.earthengine.google.com)
- [ ] GitHub: create a repo (private is fine), invite teammates
- [ ] Answer open questions: hackathon length & team size; confirm non-commercial; keep default targets/regions?

## Day 1 — deployment
- [ ] Run `scripts/vm/create-vm.sh` (or let an agent run it while you watch) — creates billable resources
- [ ] Add the deploy key printed by `bootstrap.sh` to GitHub → repo Settings → Deploy keys (read-only)
- [ ] Choose the URL: `<ip>.sslip.io` (free) or point your own domain's DNS A record at the static IP
- [ ] Review the generated `.env` on the VM; share `DEMO_TOKEN` only with reviewers

## Before the demo
- [ ] Check hackathon rules on data licences and attribution; make sure the app's About page shows ATTRIBUTIONS
- [ ] Review the top candidates yourself (or with a geologist) and set review labels — the app must not claim novelty on its own
- [ ] Record a backup demo video in case the network fails ([DEMO.md](DEMO.md))

## Every day
- [ ] **Stop the VM when nobody is using it** (`scripts/vm/stop.sh`)
- [ ] Glance at GCP billing
