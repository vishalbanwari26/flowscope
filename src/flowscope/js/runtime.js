// Jest setup file: records, for each test, the calls the instrumented functions make.
// It is the Node twin of hook.py. The result of every test is written to FLOWSCOPE_OUT.
const fs = require("fs");
const path = require("path");

const SETUP = /^(add|set|seed|generate|create|build|make|load|reset|insert|populate|register|init)/;
const roleFor = (func) => (func === "constructor" || SETUP.test(func) ? "setup" : "action");

let run = null;          // the test being recorded, or null
let phase = null;        // "setup" while one of the test's own before/after hooks runs
let nextId = 0;

function newRun() {
  return { events: [], internal: new Map(), funcs: new Map(), stack: [], entryRole: null, entryTok: null };
}

function enter(mod, func) {
  const r = run;
  if (!r) return null;
  try {
    const top = r.stack[r.stack.length - 1];
    const caller = top ? top.mod : null;
    const tok = { mod, func, t0: performance.now(), children: 0, role: null, ev: null };
    if (r.entryRole === null) {
      r.entryRole = phase === "setup" ? "setup" : roleFor(func);
      r.entryTok = tok;
    }
    const role = phase === "setup" ? "setup" : r.entryRole;
    tok.role = role;
    if (caller === mod) {
      const k = `${mod}\u0000${top.func}\u0000${func}\u0000${role}`;
      r.internal.set(k, (r.internal.get(k) || 0) + 1);
    } else {
      let parent = null;
      for (let i = r.stack.length - 1; i >= 0; i--) if (r.stack[i].ev) { parent = r.stack[i].ev.id; break; }
      tok.ev = { id: nextId++, parent, from: caller || "entry", from_func: top ? top.func : null,
                 to: mod, func, role };
      r.events.push(tok.ev);
    }
    r.stack.push(tok);
    tok.run = r;
    return tok;
  } catch { return null; }
}

function exit(tok) {
  const r = tok.run;
  try {
    let i = r.stack.length - 1;
    while (i >= 0 && r.stack[i] !== tok) i--;
    if (i < 0) return;
    r.stack.length = i;
    const inclusive = (performance.now() - tok.t0) / 1000;
    const parent = r.stack[r.stack.length - 1];
    if (parent) parent.children += inclusive;
    const k = `${tok.mod}\u0000${tok.func}\u0000${tok.role}`;
    const cur = r.funcs.get(k) || [0, 0];
    cur[0] += 1;
    cur[1] += Math.max(0, inclusive - tok.children);
    r.funcs.set(k, cur);
    if (tok.ev) tok.ev.ms = inclusive * 1000;
    if (r.entryTok === tok) { r.entryRole = null; r.entryTok = null; }
  } catch { /* never break the test */ }
}

function asDict(r) {
  const internal = [];
  for (const [k, n] of r.internal) { const [mod, from, to, role] = k.split("\u0000"); internal.push({ mod, from, to, role, n }); }
  const funcs = [];
  for (const [k, [calls, secs]] of r.funcs) { const [mod, func, role] = k.split("\u0000"); funcs.push({ mod, func, role, calls, self_ms: secs * 1000 }); }
  return { events: r.events, internal, funcs };
}

globalThis.__flowscope = { enter, exit };

// the test's own before/after hooks are setup, like pytest fixtures
function inSetup(fn) {
  return function (...args) {
    const before = phase;
    phase = "setup";
    let out;
    try { out = fn.apply(this, args); } catch (e) { phase = before; throw e; }
    if (out && typeof out.then === "function") return out.finally(() => { phase = before; });
    phase = before;
    return out;
  };
}
for (const hook of ["beforeEach", "afterEach"]) {
  const orig = globalThis[hook];
  globalThis[hook] = (fn, timeout) => orig(typeof fn === "function" ? inSetup(fn) : fn, timeout);
}

const results = [];
beforeEach(() => { run = newRun(); });
afterEach(() => {
  const st = expect.getState();
  if (run) results.push({ file: st.testPath, name: st.currentTestName, ...asDict(run) });
  run = null;
});
afterAll(() => {
  const dir = process.env.FLOWSCOPE_OUT;
  if (!dir || !results.length) return;
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, `${process.pid}-${Date.now()}-${Math.random().toString(36).slice(2)}.json`), JSON.stringify(results));
});
