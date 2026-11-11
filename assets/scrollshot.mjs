// Frames of a local HTML page scrolling down: node assets/scrollshot.mjs <file.html> <outdir> <from> <to> <frames>
import { spawn } from "node:child_process";
import { writeFileSync, mkdirSync } from "node:fs";
import { resolve } from "node:path";

const [file, dir, from, to, count] = process.argv.slice(2);
mkdirSync(dir, { recursive: true });
const chrome = spawn("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  ["--headless=new", "--remote-debugging-port=9335", "--user-data-dir=/tmp/flowscope-scrollshot",
   "--hide-scrollbars", "about:blank"], { stdio: "ignore" });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let targets;
for (let i = 0; i < 40; i++) {
  try { targets = await (await fetch("http://127.0.0.1:9335/json")).json(); break; } catch { await sleep(250); }
}
const ws = new WebSocket(targets.find((t) => t.type === "page").webSocketDebuggerUrl);
await new Promise((r) => (ws.onopen = r));
let id = 0; const pending = new Map();
ws.onmessage = (m) => { const d = JSON.parse(m.data); pending.get(d.id)?.(d.result); };
const send = (method, params = {}) => new Promise((r) => { pending.set(++id, r); ws.send(JSON.stringify({ id, method, params })); });
await send("Emulation.setDeviceMetricsOverride", { width: 1000, height: 640, deviceScaleFactor: 1, mobile: false });
await send("Page.navigate", { url: "file://" + resolve(file) }); await sleep(1200);
const n = Number(count), a = Number(from), b = Number(to);
for (let i = 0; i < n; i++) {
  const t = i / (n - 1), eased = t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;   // slow at both ends
  await send("Runtime.evaluate", { expression: `window.scrollTo(0, ${Math.round(a + (b - a) * eased)})` });
  await sleep(60);
  const r = await send("Page.captureScreenshot", { format: "png" });
  writeFileSync(`${dir}/f${String(i).padStart(3, "0")}.png`, Buffer.from(r.data, "base64"));
}
chrome.kill(); process.exit(0);
