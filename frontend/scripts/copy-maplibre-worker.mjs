// MapLibre GL v6 runs its web worker from a separate ES module file. The Next bundler does not
// emit it, so copy the worker and the chunk it imports into public/ (runs before dev and build).
import { copyFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const src = join(root, "node_modules", "maplibre-gl", "dist");
const dst = join(root, "public", "maplibre");
mkdirSync(dst, { recursive: true });
for (const f of ["maplibre-gl-worker.mjs", "maplibre-gl-shared.mjs"]) {
  copyFileSync(join(src, f), join(dst, f));
}
console.log("maplibre worker copied to public/maplibre");
