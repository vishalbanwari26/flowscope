// Frames for a video of a page: scroll to each step, hold, with a caption. Then ffmpeg joins them.
// node assets/videoshot.mjs <file.html> <outdir> <steps.json>
// steps: [{"to": 0} | {"sel": ".first"} | {"h3": "text"}, "hold": frames, "caption": "text"]
import { spawn } from "node:child_process";
import { writeFileSync, mkdirSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

const [file, dir, stepsFile] = process.argv.slice(2);
const steps = JSON.parse(readFileSync(stepsFile, "utf8"));
mkdirSync(dir, { recursive: true });
const chrome = spawn("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  ["--headless=new", "--remote-debugging-port=9336", "--user-data-dir=/tmp/flowscope-videoshot",
   "--hide-scrollbars", "about:blank"], { stdio: "ignore" });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let targets;
for (let i = 0; i < 40; i++) {
  try { targets = await (await fetch("http://127.0.0.1:9336/json")).json(); break; } catch { await sleep(250); }
}
const ws = new WebSocket(targets.find((t) => t.type === "page").webSocketDebuggerUrl);
await new Promise((r) => (ws.onopen = r));
let id = 0; const pending = new Map();
ws.onmessage = (m) => { const d = JSON.parse(m.data); pending.get(d.id)?.(d.result); };
const send = (method, params = {}) => new Promise((r) => { pending.set(++id, r); ws.send(JSON.stringify({ id, method, params })); });
const ev = async (expression) => (await send("Runtime.evaluate", { expression, returnByValue: true })).result.value;
await send("Emulation.setDeviceMetricsOverride", { width: 1280, height: 720, deviceScaleFactor: 1, mobile: false });
await send("Emulation.setEmulatedMedia", { features: [{ name: "prefers-color-scheme", value: "dark" }] });
await send("Page.navigate", { url: "file://" + resolve(file) }); await sleep(1200);
await ev(`(() => { const c = document.createElement("div"); c.id = "cap";
  c.style.cssText = "position:fixed;left:0;right:0;bottom:0;padding:18px 32px;font:600 24px system-ui;color:#fff;background:linear-gradient(transparent,rgba(0,0,0,.88) 40%);text-align:center";
  document.body.appendChild(c); })()`);

const target = async (s) => {
  if (s.to !== undefined) return s.to;
  if (s.sel) return ev(`Math.max(0, document.querySelector(${JSON.stringify(s.sel)}).getBoundingClientRect().top + scrollY - 24)`);
  return ev(`Math.max(0, [...document.querySelectorAll("h3")].find(h => h.textContent.trim().startsWith(${JSON.stringify(s.h3)})).closest("article").getBoundingClientRect().top + scrollY - 24)`);
};
let n = 0, pos = 0;
const shot = async () => {
  const r = await send("Page.captureScreenshot", { format: "png" });
  writeFileSync(`${dir}/f${String(n++).padStart(4, "0")}.png`, Buffer.from(r.data, "base64"));
};
for (const s of steps) {
  const to = await target(s);
  await ev(`document.getElementById("cap").textContent = ${JSON.stringify(s.caption || "")}`);
  const move = pos === to ? 0 : 24;
  for (let i = 1; i <= move; i++) {
    const t = i / move, e = t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
    await ev(`scrollTo(0, ${Math.round(pos + (to - pos) * e)})`); await sleep(30); await shot();
  }
  pos = to;
  for (let i = 0; i < (s.hold || 60); i++) await shot();     // holding still: the same frame repeated is fine
}
chrome.kill(); console.log(n, "frames"); process.exit(0);
