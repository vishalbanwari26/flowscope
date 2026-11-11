// Full-page screenshot of a local HTML file: node assets/pageshot.mjs <file.html> <out.png>
import { spawn } from "node:child_process";
import { writeFileSync } from "node:fs";
import { resolve } from "node:path";

const [file, out] = process.argv.slice(2);
const chrome = spawn("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  ["--headless=new", "--remote-debugging-port=9334", "--user-data-dir=/tmp/flowscope-pageshot",
   "--hide-scrollbars", "about:blank"], { stdio: "ignore" });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let targets;
for (let i = 0; i < 40; i++) {
  try { targets = await (await fetch("http://127.0.0.1:9334/json")).json(); break; } catch { await sleep(250); }
}
const ws = new WebSocket(targets.find((t) => t.type === "page").webSocketDebuggerUrl);
await new Promise((r) => (ws.onopen = r));
let id = 0; const pending = new Map();
ws.onmessage = (m) => { const d = JSON.parse(m.data); pending.get(d.id)?.(d.result); };
const send = (method, params = {}) => new Promise((r) => { pending.set(++id, r); ws.send(JSON.stringify({ id, method, params })); });
await send("Emulation.setDeviceMetricsOverride", { width: 1000, height: 800, deviceScaleFactor: 1, mobile: false });
await send("Page.navigate", { url: "file://" + resolve(file) }); await sleep(1200);
const h = (await send("Runtime.evaluate", { expression: "document.documentElement.scrollHeight" })).result.value;
const r = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: true,
  clip: { x: 0, y: 0, width: 1000, height: h, scale: 1 } });
writeFileSync(out, Buffer.from(r.data, "base64"));
chrome.kill(); console.log(out, h); process.exit(0);
