# Demo

## Story (2–3 minutes)
1. **Problem (20 s):** analog research keeps reusing the same famous sites; finding new ones is manual.
2. **Pick Jezero crater (20 s):** show the Mars hillshade preview and its terrain profile (slope, relief, roughness).
3. **Search the Western Sahara (30 s):** map lights up with candidate regions; top ones labelled *not in checked records*.
4. **Open the top candidate (40 s):** feature bars Earth vs Jezero vs tolerance, slope histogram overlay, the main mismatch, what data is missing, sources.
5. **Credibility check (30 s):** search Atacama → the app ranks documented analogs highly on its own, without being told where they are.
6. **Honesty (20 s):** terrain similarity only; candidates need expert review; score is a configured similarity, not a probability. Show the weight sliders if built.

## Pre-demo checklist
- [ ] VM running, `scripts/vm/status.sh` green, site loads over HTTPS
- [ ] Both searches return results in < 2 s (warm the app once beforehand)
- [ ] Top candidates reviewed by a human; labels set
- [ ] About page shows limitations and attributions
- [ ] Backup: recorded video + screenshots in the slides
- [ ] Laptop on power, notifications off, browser zoom set

## Lines to avoid
"We discovered new Mars analogs", "92% probability", "this site is like Mars". Say instead: "unlisted candidate", "configured similarity 92 under terrain-v1", "terrain resembles Jezero at 200 m scale".
