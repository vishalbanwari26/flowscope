"""JavaScript and TypeScript projects that test with Jest.

The Python side stays the same: a survey of every test, kept as the same records, so the
overview, the page and the commands work unchanged. Only the recording differs. A Babel
plugin wraps the project's functions, and a Jest setup file writes down, per test, which
function called which and for how long (see js/).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from . import modules

JS_DIR = Path(__file__).parent / "js"
ANSI = re.compile(r"\x1b\[[0-9;]*m")
BABEL_CONFIGS = ("babel.config.js", "babel.config.cjs", "babel.config.mjs", "babel.config.json",
                 "babel.config.ts", ".babelrc", ".babelrc.js", ".babelrc.cjs", ".babelrc.json")


def _node() -> str:
    node = os.environ.get("FLOWSCOPE_NODE") or shutil.which("node")
    if not node:
        raise SystemExit("flowscope: Node.js was not found. Install it, or set FLOWSCOPE_NODE.")
    return node


def _jest(root: Path) -> list:
    local = root / "node_modules" / ".bin" / "jest"
    if not local.exists():
        raise SystemExit(f"flowscope: Jest is not installed in {root}. Run npm install first.")
    return [str(local)]


def _resolve(root: Path, package: str):
    """The path of a package as the project sees it, or None."""
    r = subprocess.run([_node(), "-p", f"require.resolve({json.dumps(package)})"], cwd=root,
                       capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else None


def _has_babel_config(root: Path) -> bool:
    if any((root / f).exists() for f in BABEL_CONFIGS):
        return True
    try:
        return "babel" in json.loads((root / "package.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False


def _jest_flags(root: Path, tmp: Path) -> list:
    """Command line flags that add our recorder and Babel plugin to the project's own Jest setup.
    The project's configuration is still read as usual; only the two settings below change."""
    shown = subprocess.run(_jest(root) + ["--showConfig"], cwd=root, capture_output=True, text=True)
    try:
        cfg = json.loads(shown.stdout)["configs"][0]
    except (ValueError, KeyError, IndexError):
        raise SystemExit("flowscope: could not read the Jest configuration.\n" + (shown.stderr or shown.stdout)[-600:])
    babel_jest = _resolve(root, "babel-jest") or "babel-jest"
    opts: dict = {"plugins": [str(JS_DIR / "babel-plugin.js")]}
    if not _has_babel_config(root):                      # ts-jest and similar: Babel needs presets to read the code
        presets = [p for p in (_resolve(root, "@babel/preset-env"), _resolve(root, "@babel/preset-typescript")) if p]
        if len(presets) < 2:
            raise SystemExit("flowscope: this project has no Babel configuration. Install @babel/preset-env and "
                             "@babel/preset-typescript, or add a babel.config.js, so flowscope can read the code.")
        opts["presets"] = presets
    transform = {r"\.(jsx?|tsx?|mjs|cjs|mts|cts)$": [babel_jest, opts]}
    for pattern, path, o in cfg.get("transform", []):
        transform.setdefault(pattern, [path, o])         # other file types keep the project's transformer
    flags = ["--transform", json.dumps(transform), "--cacheDirectory", str(tmp / "cache")]
    for f in list(cfg.get("setupFilesAfterEnv", [])) + [str(JS_DIR / "runtime.js")]:
        flags += ["--setupFilesAfterEnv", f]
    return flags


def framework(root: Path) -> str:
    """"vitest" or "jest"."""
    try:
        pkg = json.loads((root / "package.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "jest"
    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
    return "vitest" if "vitest" in deps and "jest" not in deps else "jest"


def _read_traces(out: Path) -> dict:
    traces: dict = {}
    for f in sorted(out.glob("*.json")) if out.exists() else []:
        for r in json.loads(f.read_text()):
            traces[(r["file"], r["name"])] = r
    return traces


def _vitest_runs(root: Path, tmp: Path) -> list:
    report = tmp / "report.json"
    r = subprocess.run([_node(), str(JS_DIR / "vitest-run.mjs"), str(root), str(tmp / "modules.json"),
                        str(tmp / "out"), str(report)],
                       cwd=root, capture_output=True, text=True)
    try:
        rows = json.loads(report.read_text())
    except (OSError, ValueError):
        raise SystemExit("flowscope: Vitest did not produce a result. Run it yourself to see why.\n"
                         + ANSI.sub("", (r.stderr or r.stdout))[-600:])
    traces = _read_traces(tmp / "out")
    pairs = []
    for row in rows:
        file = Path(row["file"])
        rel = file.relative_to(root).as_posix() if file.is_relative_to(root) else file.name
        outcome = {"pass": "passed", "fail": "failed", "error": "error"}.get(row["state"], "skipped")
        tr = traces.get((row["file"], row["name"]), {})
        result = {"outcome": outcome, "events": tr.get("events", []), "internal": tr.get("internal", []),
                  "funcs": tr.get("funcs", []), "call_ms": row.get("duration")}
        if outcome in ("failed", "error"):
            result["output"] = ANSI.sub("", row.get("error", ""))[-2000:]
        pairs.append(({"id": f"{rel}::{row['name']}", "name": row["title"], "file": file.name}, result))
    return pairs


def collect_runs(root: Path) -> list:
    """Run every test once. Returns (case, result) pairs shaped like the Python runner's."""
    root = root.resolve()
    names = {f: n for f, n in modules.configure(root).names.items() if n}
    with tempfile.TemporaryDirectory(prefix="flowscope-") as t:
        tmp = Path(t)
        (tmp / "modules.json").write_text(json.dumps(names))
        if framework(root) == "vitest":
            return _vitest_runs(root, tmp)
        flags = _jest_flags(root, tmp)
        env = dict(os.environ, FLOWSCOPE_MODULES=str(tmp / "modules.json"), FLOWSCOPE_OUT=str(tmp / "out"))
        report = tmp / "report.json"
        subprocess.run(_jest(root) + flags + ["--no-cache", "--json", f"--outputFile={report}"],
                       cwd=root, env=env, capture_output=True, text=True)
        try:
            data = json.loads(report.read_text())
        except (OSError, ValueError):
            raise SystemExit("flowscope: Jest did not produce a result. Run it yourself to see why.")
        traces = _read_traces(tmp / "out")
    pairs = []
    for suite in data.get("testResults", []):
        file = Path(suite["name"])
        rel = file.relative_to(root).as_posix() if file.is_relative_to(root) else file.name
        for a in suite.get("assertionResults", []):
            status = a["status"]
            outcome = "passed" if status == "passed" else "failed" if status == "failed" else "skipped"
            tr = traces.get((suite["name"], a["fullName"]), {})
            result = {"outcome": outcome, "events": tr.get("events", []), "internal": tr.get("internal", []),
                      "funcs": tr.get("funcs", []), "call_ms": a.get("duration")}
            if outcome == "failed":
                result["output"] = ANSI.sub("", "\n".join(a.get("failureMessages", [])))[-2000:]
            pairs.append(({"id": f"{rel}::{a['fullName']}", "name": a["title"], "file": file.name}, result))
        if suite.get("status") == "failed" and not suite.get("assertionResults"):
            msg = ANSI.sub("", suite.get("message", ""))[-2000:]
            pairs.append(({"id": f"{rel}::(suite)", "name": "test file failed to run", "file": file.name},
                          {"outcome": "error", "events": [], "internal": [], "funcs": [], "output": msg}))
    return pairs


def scan(root: Path, names: dict) -> list:
    """The public functions of the project's JavaScript and TypeScript files, like gaps.scan."""
    files = [f for f, m in sorted(names.items()) if m]
    with tempfile.TemporaryDirectory(prefix="flowscope-") as t:
        listing = Path(t) / "files.json"
        listing.write_text(json.dumps(files))
        r = subprocess.run([_node(), str(JS_DIR / "scan.js"), str(root), str(listing)],
                           capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit("flowscope: could not read the source files.\n" + r.stderr[-600:])
    return [{"module": names[i["file"]], "name": i["name"], "qual": i["qual"],
             "where": f"{Path(i['file']).relative_to(root)}:{i['line']}", "entry": i["entry"], "size": i["size"]}
            for i in json.loads(r.stdout)]
