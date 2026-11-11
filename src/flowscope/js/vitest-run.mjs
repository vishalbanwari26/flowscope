// Run every Vitest test once with the recorder on, and write a small report.
// node vitest-run.mjs <project root> <modules json> <out dir> <report file>
import { createRequire } from "node:module";
import { writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { pathToFileURL, fileURLToPath } from "node:url";
import { flowscopePlugin } from "./vitest-plugin.mjs";

const [root, modulesFile, outDir, reportFile] = process.argv.slice(2);
const here = dirname(fileURLToPath(import.meta.url));
const fromRoot = createRequire(join(root, "package.json"));
const load = (p) => import(pathToFileURL(p).href);

const vitestNode = await load(fromRoot.resolve("vitest/node"));
const vitePath = createRequire(fromRoot.resolve("vitest/package.json")).resolve("vite");
const { parseAst } = await load(vitePath);

process.env.FLOWSCOPE_OUT = outDir;
const plugin = flowscopePlugin({ parseAst, modulesFile, runtimeFile: join(here, "runtime-vitest.mjs") });
const vitest = await vitestNode.startVitest("test", [], { root, run: true, watch: false, reporters: ["dot"] }, { plugins: [plugin] });

const rows = [];
function visit(task, chain, file) {
  const here = task.name ? [...chain, task.name] : chain;
  if (task.type === "test" || task.type === "custom") {
    const r = task.result || {};
    const err = (r.errors && r.errors[0]) || null;
    rows.push({ file, name: here.join(" > "), title: task.name, state: r.state || (task.mode === "skip" || task.mode === "todo" ? "skip" : "unknown"),
                duration: r.duration || null, error: err ? (err.stack || err.message || String(err)) : "" });
  } else for (const t of task.tasks || []) visit(t, here, file);
}
for (const f of vitest ? vitest.state.getFiles() : []) {
  const before = rows.length;
  for (const t of f.tasks) visit(t, [], f.filepath);
  const r = f.result || {};
  if (r.state === "fail" && rows.length === before)
    rows.push({ file: f.filepath, name: "(file)", title: "test file failed to run", state: "error", duration: null,
                error: ((r.errors && r.errors[0] && (r.errors[0].stack || r.errors[0].message)) || "") });
}
writeFileSync(reportFile, JSON.stringify(rows));
if (vitest) await vitest.close();
process.exit(0);
