---
name: geo-pipeline
description: Use when adding or changing a data source, raster preprocessing step, window grid, or terrain feature in Earth Analog Explorer (core/, pipeline/). Enforces body-correct coordinates, no upsampling, provenance and synthetic-DEM tests.
---

# Geo pipeline rules

## Adding a data source
1. Confirm it's free and its licence fits non-commercial use; add it to `docs/DATA_SOURCES.md` and `ATTRIBUTIONS.md`.
2. Add its host(s) to the allowlist in `config/sources.yaml`. Never fetch from an unlisted host.
3. Write an adapter in `pipeline/adapters/` implementing `discover(aoi) -> list[AssetRef]` and `fetch(asset) -> path`, with retries + exponential backoff.
4. Record every fetched file in `source_assets` (provider, body, footprint, resolution, version, SHA-256, storage URI). Copy raw files to object storage.
5. Public AWS buckets: use `AWS_NO_SIGN_REQUEST=YES`; never require AWS credentials.

## Coordinates and bodies
- Use `core/bodies.py` for radii and CRS. Moon R = 1,737,400 m (IAU_2015:30100); Mars R = 3,396,190 m (IAU_2015:49900); Earth WGS84.
- Compute slope only in a projected CRS on the **correct body** with true pixel size in metres.
- Earth regions: process in a per-region LAEA projection; store geometries in EPSG:4326.
- Planetary geometries: never give them an Earth SRID. Store GeoJSON/WKT + `body` + `crs`.

## Resolution
- Comparison scale: 200 m for Mars targets, 59 m for Moon targets.
- Earth 30 m → aggregate down with area-weighted averaging (`Resampling.average`).
- **Never upsample.** Every resampling call goes through a helper that asserts `target_res >= source_res`.

## Features
- Live in `core/features/`, pure functions: `(dem: np.ndarray, pixel_size_m: float, mask: np.ndarray) -> value | None`.
- Return `None` (not 0, not NaN-filled) when not computable; set the availability mask.
- Same function for Earth and planetary inputs — no body-specific branches inside feature code.
- **Required test:** synthetic DEMs with known answers (flat → slope 0, tilted plane of known angle → exact slope, cone, plane + known Gaussian noise → roughness ≈ σ), run for Earth, Moon and Mars pixel sizes.
- New or changed feature → bump `feature_schema_version`, update `docs/SCORING.md`.

## Provenance
Every derived row stores: source asset IDs, git SHA, config hash, schema version. Every pipeline step writes a `processing_runs` row with status and error.

## Masks
WorldCover gives water / built-up / snow-ice / vegetation shares. Store them as flags and fractions; whether they exclude a window is decided by the scoring config, not by the pipeline.
