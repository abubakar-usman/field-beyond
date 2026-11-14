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
- Comparison grids: 200 m for Mars targets, 60 m for Moon targets (`config/targets/`, `config/grids/pilot-v1.yaml`, decision D-023). SLDEM2015 is the ~59 m *product*; the Moon grid is 60 m so the latitude axis at Taurus–Littrow is not upsampled.
- One Earth cell stores two profiles (`scale_m` 200 and 60). A search may use only the profile whose scale matches the target.
- Aggregate with area-weighted averaging (`Resampling.average`) onto a grid in the region's LAEA. Pixel edges are multiples of the comparison pixel size from that projection's origin. The proj strings are in `config/grids/pilot-v1.yaml`.
- **Never upsample.** Every resampling call goes through a helper that asserts both output pixel axes are coarser than or equal to the source ground pixel, in metres, on the correct body. This applies to Earth, Moon, and Mars rasters.
- The scored target footprint is the 10 km square in `config/targets/`. The preview bbox is a hillshade and is not passed to feature extraction.

## Features
- Live in `core/features/`, pure functions: `(dem: np.ndarray, pixel_size_m: float, mask: np.ndarray) -> value | None`.
- Return `None` (not 0, not NaN-filled) when not computable; set the availability mask.
- Same function for Earth and planetary inputs — no body-specific branches inside feature code.
- **Required test:** synthetic DEMs with known answers (flat → slope 0, tilted plane of known angle → exact slope, cone, plane + known Gaussian noise → roughness ≈ σ), run for Earth, Moon and Mars pixel sizes.
- New or changed feature → bump `feature_schema_version`, update `docs/SCORING.md`.

## Provenance
Every derived row stores: source asset IDs, git SHA, config hash, schema version. Every pipeline step writes a `processing_runs` row with status and error.

## Masks
Count WorldCover at native 10 m inside the window. Do not majority-filter it onto the DEM grid first. Class lists and which classes can exclude a window live in `config/scoring/terrain-v1.yaml`. The pipeline stores fractions; the scoring config decides eligibility. For `exposed_terrain`, water (class 80) and built-up (class 50) can exclude; snow/ice and vegetation are flags.
