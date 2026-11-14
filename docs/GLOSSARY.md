# Glossary

| Term | Meaning |
|---|---|
| **Analog (site)** | A place on Earth that resembles some aspect of another world, used for research or equipment testing |
| **Target** | The specific Moon or Mars location we compare against (e.g. Jezero crater) |
| **Pilot region** | A bounded Earth area that has been processed and can be searched |
| **Window / cell** | One 10 km × 10 km square of a pilot region; the unit that gets measured and scored |
| **Stride** | Distance between window starts (5 km → windows overlap by half) |
| **Candidate** | One or more overlapping high-scoring windows merged into a region |
| **DEM** | Digital Elevation Model — a grid of heights |
| **DSM vs DTM** | Surface model (includes trees/buildings) vs terrain model (bare ground). Copernicus is a DSM; FABDEM is a DTM |
| **COG** | Cloud-Optimized GeoTIFF — a raster file that can be partially read over HTTP |
| **STAC** | SpatioTemporal Asset Catalog — a standard way to search for geospatial files |
| **CRS** | Coordinate Reference System. Earth, Moon and Mars each have their own |
| **LAEA** | Lambert Azimuthal Equal-Area projection — used so every window covers the same real area |
| **Aggregate / upsample** | Combine pixels into coarser ones / invent finer pixels. We aggregate; we never upsample |
| **Slope** | Steepness in degrees, from elevation differences between neighbouring pixels (Horn method) |
| **Relief** | Height range in a window: 95th minus 5th percentile elevation |
| **Roughness** | How bumpy terrain is after removing its overall tilt (std of residuals from a fitted plane) |
| **Wasserstein-1** | "Earth mover's distance" between two histograms; here in degrees of slope |
| **Tolerance** | The difference at which a feature's similarity drops to 0 |
| **Configured similarity** | Our 0–100 score; depends on chosen tolerances and weights. Not a probability |
| **Registry** | Our table of documented analog sites, with sources and check dates |
| **Provenance** | Record of which source files, code version and settings produced a value |
| **SLDEM2015** | Lunar DEM from LOLA laser + Kaguya stereo, ~59 m |
| **MOLA / HRSC** | Mars laser altimeter (Mars Global Surveyor) / stereo camera (Mars Express) |
| **WorldCover** | ESA's 10 m global land-cover map, used for water/built-up/vegetation masks |
| **sslip.io** | Free DNS service: `34-1-2-3.sslip.io` resolves to IP 34.1.2.3 — lets Caddy get HTTPS without buying a domain |
| **Scored footprint** | The 10 km square whose terrain is actually compared. Wider preview images are not scored |
| **Comparison grid** | 200 m pixels for Mars targets, 60 m pixels for Moon targets |
| **Search index** | `features.parquet`. PostGIS holds the evidence rows, not the nearest-neighbour input |
| **Reference list** | Documented analogs returned beside the candidates, sorted by score, excluded from the default candidate list |
| **exposed_terrain** | The only hackathon purpose. Water and built-up can exclude a window; vegetation and snow/ice are flags |
| **Scored footprint** | The 10 km square whose terrain is actually compared. Wider preview images are not scored |
| **Comparison grid** | 200 m pixels for Mars targets, 60 m pixels for Moon targets |
| **Search index** | `features.parquet`. PostGIS holds the evidence rows, not the nearest-neighbour input |
| **Reference list** | Documented analogs returned beside the candidates, sorted by score, excluded from the default candidate list |
| **exposed_terrain** | The only hackathon purpose. Water and built-up can exclude a window; vegetation and snow/ice are flags |
