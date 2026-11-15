import Link from "next/link";

export const metadata = { title: "Method and data credits · Earth Analog Explorer" };

const CREDITS: [string, string][] = [
  [
    "Copernicus DEM GLO-30",
    "© DLR e.V. 2010–2014 and © Airbus Defence and Space GmbH 2014–2018, provided under COPERNICUS by the European Union and ESA; all rights reserved. Copernicus DEM licence. Accessed via AWS Open Data.",
  ],
  [
    "ESA WorldCover",
    "© ESA WorldCover project 2021 / Contains modified Copernicus Sentinel data (2021) processed by ESA WorldCover consortium. CC BY 4.0.",
  ],
  [
    "SLDEM2015 (Moon)",
    "NASA / LRO LOLA team and JAXA / SELENE (Kaguya) Terrain Camera; USGS Astrogeology. Public domain. Barker, M.K. et al. (2016), Icarus 273, 346–355.",
  ],
  [
    "MOLA–HRSC Blended DEM v2 (Mars)",
    "NASA / MGS MOLA (CC0) and ESA / DLR / FU Berlin Mars Express HRSC (CC BY-SA 3.0 IGO); Fergason, Hare & Laura (2018), USGS Astrogeology. Derived Mars elevation products are shared under CC BY-SA 3.0 IGO.",
  ],
  [
    "Known Terrestrial Analog Sites for Planetary Science",
    "U.S. Geological Survey. Public domain.",
  ],
  [
    "Gazetteer of Planetary Nomenclature",
    "IAU-adopted names compiled by the USGS Astrogeology Science Center. Public domain. A listed name is a place that can be profiled; the scored footprint is the 10 km square at its center.",
  ],
  ["Base map", "© OpenStreetMap contributors (ODbL), tiles by OpenFreeMap, OpenMapTiles."],
  [
    "Satellite layer (if enabled)",
    "Sentinel-2 cloudless by EOX IT Services GmbH (contains modified Copernicus Sentinel data). Non-commercial use.",
  ],
];

export default function About() {
  return (
    <main className="page">
      <Link href="/">← Back to the map</Link>
      <h1>Method and data credits</h1>

      <section>
        <h2>What the score means</h2>
        <p>
          Each Earth window is 10 km square. Its terrain is measured at the target&rsquo;s scale
          (200 m pixels for Mars, 60 m for the Moon) and compared with the target&rsquo;s 10 km
          square. Five measurements are compared: the slope distribution, median slope,
          90th-percentile slope, relief and roughness. Each gets a similarity from 0 to 100 within a
          stated tolerance, and the weighted mean is the{" "}
          <strong>configured similarity (terrain-v1)</strong>. It says how close the measurements
          are under those settings. It is not a probability that a place is a good analog, and no
          machine learning is involved.
        </p>
        <p>
          A window missing any of the five measurements is left out; it is never scored on what
          remains. Windows with more than 5% water, more than 2% built-up land, or under 90% valid
          elevation pixels are excluded before scoring. Snow, ice and vegetation are shown as flags.
        </p>
        <p>
          &ldquo;Not in checked records&rdquo; means the place does not overlap the registry
          versions listed with the result. It does not mean the place is unknown to science.
        </p>
      </section>

      <section>
        <h2>Coordinates</h2>
        <p>
          Earth, Moon and Mars are measured on their own figures (WGS84; IAU 2015 spheres of
          1,737,400 m and 3,396,190 m). Planetary targets are never drawn on the Earth map; they
          appear as hillshade images. Elevation data is only ever averaged down to a coarser grid,
          never up.
        </p>
      </section>

      <section>
        <h2>Data credits</h2>
        <table>
          <tbody>
            {CREDITS.map(([k, v]) => (
              <tr key={k}>
                <th scope="row">{k}</th>
                <td>{v}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="muted">Non-commercial hackathon project.</p>
      </section>
    </main>
  );
}
