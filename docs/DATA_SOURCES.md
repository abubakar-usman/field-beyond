# Data sources

All sources are free. None needs an API key. Checked November 2026 — re-verify URLs and versions during the Phase 1 data audit and record results in `docs/data-audit.md`.

## In use

### Copernicus DEM GLO-30 (Earth elevation) — primary
- **What:** global ~30 m elevation, Digital *Surface* Model (includes trees and buildings).
- **Where:** `s3://copernicus-dem-30m` (AWS eu-central-1), Cloud-Optimized GeoTIFFs, 1°×1° tiles named `Copernicus_DSM_COG_10_...`.
- **Discovery:** STAC API `https://earth-search.aws.element84.com/v1`, collection `cop-dem-glo-30`.
- **Access:** no account. Set `AWS_NO_SIGN_REQUEST=YES` and read with rasterio/GDAL (`/vsis3/...`).
- **Fallback:** Microsoft Planetary Computer STAC `https://planetarycomputer.microsoft.com/api/stac/v1`, collection `cop-dem-glo-30`; the `planetary-computer` Python package signs URLs anonymously.
- **License:** Copernicus DEM licence — free, attribution required, commercial OK.
- **Gotchas:** a few country tiles are not public; some items missing in Earth Search. Surface model → vegetation inflates roughness (use WorldCover flags).
- Registry page: https://registry.opendata.aws/copernicus-dem/

### ESA WorldCover 10 m (Earth land cover → masks)
- **Where:** `s3://esa-worldcover` (AWS eu-central-1), path `v200/2021/map/` (v100/2020 also available).
- **Access:** `AWS_NO_SIGN_REQUEST=YES`.
- **License:** CC BY 4.0. Credit: "© ESA WorldCover project / Contains modified Copernicus Sentinel data (2021) processed by ESA WorldCover consortium".
- **Use:** water, built-up, snow/ice, tree/shrub/grass shares per window.
- https://registry.opendata.aws/esa-worldcover-vito/

### SLDEM2015 (Moon elevation)
- **What:** LOLA laser altimetry merged with Kaguya Terrain Camera stereo; 512 px/degree (~59 m), ±60° latitude, ~3–4 m vertical accuracy.
- **Where:** USGS Astrogeology "Moon LRO LOLA – SELENE Kaguya TC DEM Merge 60N60S 59m" (~11 GB GeoTIFF); also NASA PGDA (tiles) and the MIT LOLA node (`imbrium.mit.edu/DATA/SLDEM2015/`).
- **Access:** HTTPS, no login. **Use tiles or crop on download** — only the Taurus–Littrow area is needed.
- **License:** public domain. Cite Barker et al. (2016), Icarus 273, 346–355.
- https://astrogeology.usgs.gov/search/map/moon_lro_lola_selene_kaguya_tc_dem_merge_60n60s_59m

### MOLA–HRSC Blended DEM Global 200 m v2 (Mars elevation)
- **What:** MOLA (Mars Global Surveyor) blended with HRSC (Mars Express) stereo; 200 m/px, global.
- **Where:** USGS Astrogeology (~11 GB GeoTIFF); also distributed via PDS.
- **Access:** HTTPS, no login.
- **License:** MOLA CC0; HRSC **CC BY-SA 3.0 IGO** → credit, and share derived Mars DEM products under the same licence if redistributed. Cite Fergason, Hare & Laura (2018).
- **Gotcha:** in areas without HRSC coverage it's MOLA-interpolated (smoother). Check Jezero has HRSC coverage during the audit.
- https://astrogeology.usgs.gov/search/map/mars_mgs_mola_mex_hrsc_blended_dem_global_200m

### USGS Known Terrestrial Analog Sites for Planetary Science (registry seed)
- **What:** US Government dataset of documented analog sites (metadata updated Oct 2025).
- **Where:** https://catalog.data.gov/dataset/known-terrestrial-analog-sites-for-planetary-science and https://www.usgs.gov/data/known-terrestrial-analog-sites-planetary-science
- **To do in audit:** check its format (points vs polygons) and fields. If points, buffer them (e.g. 10 km) and record that assumption.
- Supplement with NASA Planetary Analog Explorer (https://science.nasa.gov/solar-system/analog-explorer/) and literature, recording each source and date.

### Basemaps
- **OpenFreeMap** vector tiles, style `https://tiles.openfreemap.org/styles/liberty` — free, no key, OpenStreetMap data (credit OSM contributors).
- **EOX Sentinel-2 cloudless** WMTS — free for **non-commercial** use with the attribution EOX specifies for the chosen year. Commercial use needs a paid EOX licence.

## Optional / later

| Source | Use | Access | License |
|---|---|---|---|
| FABDEM v1.2 | Bare-earth cross-check of Copernicus (trees/buildings removed) | University of Bristol data portal | CC BY-NC-SA 4.0 (**non-commercial**) |
| Macrostrat API `https://macrostrat.org/api/v2/geologic_units/map` | Geology / lithology for candidates | REST, no key | CC BY 4.0 (cite Macrostrat + original maps) |
| Google Earth Engine | Quick exploratory looks at Earth data | Python API on the GCP project, non-commercial registration | Free Community tier: 150 EECU-hours/month |
| LOLA polar LDEMs | Lunar polar targets (down to 5 m/px) | PDS Geosciences / Lunar ODE | Public domain |
| HRSC / CTX stereo DEMs | Finer Mars targets | PDS / USGS | Varies |
| LRO Diviner, MRO CRISM, NASA POWER | Thermal / mineralogy / climate (Phase 4) | PDS / NASA | Public |

## Not used (and why)
- **OpenTopography API** — same Copernicus data, but needs a key and is limited to ~50 calls/day for non-academic users.
- **MOLA MEGDR 463 m** — superseded by the 200 m blended product for our purpose.
- **NASA POWER air temperature as surface temperature** — physically wrong (design §5).

## Approved hosts (for `config/sources.yaml` SSRF allowlist)
`copernicus-dem-30m.s3.eu-central-1.amazonaws.com`, `copernicus-dem-30m.s3.amazonaws.com`, `esa-worldcover.s3.eu-central-1.amazonaws.com`, `esa-worldcover.s3.amazonaws.com`, `earth-search.aws.element84.com`, `planetarycomputer.microsoft.com`, `*.blob.core.windows.net` (Planetary Computer assets), `planetarymaps.usgs.gov`, `astrogeology.usgs.gov`, `pgda.gsfc.nasa.gov`, `imbrium.mit.edu`, `pds-geosciences.wustl.edu`, `macrostrat.org`.
