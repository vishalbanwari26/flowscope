// Saves viewer screenshots: node assets/shoot.mjs <url> <out-dir>
import { spawn } from "node:child_process";
import { writeFileSync } from "node:fs";

const [url, out] = process.argv.slice(2);
const chrome = spawn("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  ["--headless=new", "--remote-debugging-port=9333", "--user-data-dir=/tmp/flowscope-shoot",
   "--window-size=1280,800", "--hide-scrollbars", "about:blank"], { stdio: "ignore" });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let targets;
for (let i = 0; i < 40; i++) {
  try { targets = await (await fetch("http://127.0.0.1:9333/json")).json(); break; } catch { await sleep(250); }
}
const ws = new WebSocket(targets.find((t) => t.type === "page").webSocketDebuggerUrl);
await new Promise((r) => (ws.onopen = r));
let id = 0; const pending = new Map();
ws.onmessage = (m) => { const d = JSON.parse(m.data); pending.get(d.id)?.(d.result); };
const send = (method, params = {}) => new Promise((r) => { pending.set(++id, r); ws.send(JSON.stringify({ id, method, params })); });
const js = (expression) => send("Runtime.evaluate", { expression, awaitPromise: true });
const shot = async (name) => {
  const r = await send("Page.captureScreenshot", { format: "png" });
  writeFileSync(`${out}/${name}.png`, Buffer.from(r.data, "base64"));
};
await send("Emulation.setDeviceMetricsOverride", { width: 1280, height: 800, deviceScaleFactor: 2, mobile: false });
await send("Page.navigate", { url }); await sleep(1500);
const click = (text) => js(`[...document.querySelectorAll("button,summary,li,div")].find(e=>e.children.length<4&&e.textContent.trim().startsWith(${JSON.stringify(text)}))?.click()`);
await click("small order"); await sleep(1500); await shot("viewer-flow");
await js(`[...document.querySelectorAll(".chip,button")].find(e=>e.textContent.trim().startsWith("catalog"))?.click()`); await sleep(1500); await shot("viewer-module");
await js(`document.getElementById("gcard").open=true`); await sleep(1500);
await js(`document.getElementById("gcard").scrollIntoView()`); await sleep(500); await shot("viewer-graph");
chrome.kill(); process.exit(0);
