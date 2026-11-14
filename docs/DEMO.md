# Demo

## Story (2–3 minutes)
1. **Problem (20 s):** analog research keeps returning to the same famous sites. Looking for other candidates is still manual.
2. **Pick Jezero crater (20 s):** show the Mars hillshade, and say the scored profile is the 10 km square at the landing site (slope, relief, roughness at 200 m).
3. **Search `earth_sahara` (30 s):** map shows candidate regions. Top ones are labelled *not in checked records*.
4. **Open the top candidate (40 s):** feature bars Earth vs Jezero vs the stored tolerance, slope histogram overlay, the main mismatch, what data is missing, sources.
5. **Credibility check (30 s):** search `earth_atacama` and open the reference list. Registry rows linked to Mars terrain or Jezero should rank highly there. The app was not given those locations as search seeds. If they rank poorly, say so — that is a result about terrain-v1.
6. **Honesty (20 s):** terrain similarity only; candidates need expert review; the score is a configured similarity, not a probability. Weight sliders, if built, rescore the current shortlist only.

## Pre-demo checklist
- [ ] VM running, `scripts/vm/status.sh` green, site loads over HTTPS
- [ ] Both searches return results in < 2 s (warm the app once beforehand)
- [ ] Top candidates reviewed by a human; labels set
- [ ] About page shows limitations and attributions
- [ ] Backup: recorded video + screenshots in the slides
- [ ] Laptop on power, notifications off, browser zoom set

## Lines to avoid
"We discovered new Mars analogs", "92% probability", "this site is like Mars". Say instead: "unlisted candidate", "configured similarity 92 under terrain-v1", "terrain resembles Jezero at 200 m scale".
