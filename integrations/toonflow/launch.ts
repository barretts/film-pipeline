import { resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { readFile } from "node:fs/promises";
import { createHash } from "node:crypto";
const vendor = process.env.LOCAL_FILM_TOONFLOW_ROOT;
const profile = process.env.LOCAL_FILM_TOONFLOW_PROFILE;
if (!vendor || !profile) throw new Error("Launch with tools/start_cpu_film.py");
process.env.TOONFLOW_DATA_DIR = profile;
const { createApp } = await import(pathToFileURL(resolve(vendor, "apps/server/src/app.ts")).href);
const revision = createHash("sha256")
  .update(await readFile(resolve(import.meta.dirname, "build/nodes/filmProject.umd.js")))
  .update(await readFile(resolve(import.meta.dirname, "build/tools/filmProject.tool.js")))
  .digest("hex");
const app = await createApp({ webRoot: resolve(vendor, "build/web"), appVersion: "2.0.10-local-film",
  pluginRevision: `local-film-${revision}`,
  dataDirectory: profile, toolsRoot: resolve(profile, "bundledTools"),
  nodesRoot: resolve(import.meta.dirname, "build/nodes"), skillsRoot: resolve(import.meta.dirname, "skills") });
const port = Number(process.env.LOCAL_FILM_TOONFLOW_PORT ?? "33030");
app.listen(port, "127.0.0.1", () => console.log(`Local Toonflow: http://127.0.0.1:${port} — film GPU execution disabled`));
