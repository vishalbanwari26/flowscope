"""Run every use case once and keep what the project-wide questions need.

The answers to "what is in this project", "what is inside this module" and "which tests
reach this function" all come from the same pass over the tests. It is cached outside the
project, so the second question is instant.
"""
from __future__ import annotations

import hashlib
import json
import os
from collections import Counter
from pathlib import Path

from . import modules, runner


VERSION = 2      # bump when what is saved changes, so old saved overviews are rebuilt


def cache_dir() -> Path:
    return Path(os.environ.get("FLOWSCOPE_CACHE") or Path.home() / ".cache" / "flowscope")


def _stamp(root: Path) -> list:
    """Changes when a Python file in the project is added, removed or edited."""
    skip = modules.SKIP_DIRS - {"tests", "test"}         # test files count here
    n, newest = 0, 0.0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip and not d.endswith(".egg-info")]
        for f in filenames:
            if f.endswith(".py"):
                n += 1
                newest = max(newest, (Path(dirpath) / f).stat().st_mtime)
    return [n, newest]


def _record(case: dict, r: dict) -> dict:
    """The small part of one run that the project-wide questions need."""
    ev = r["events"]
    mods = {(e["to"], e["role"]) for e in ev}
    mods |= {(e["from"], e["role"]) for e in ev if e["from"] != "entry"}
    mods |= {(f["mod"], f["role"]) for f in r["funcs"]}
    edges = Counter((e["from"], e["to"]) for e in ev)
    callers: Counter = Counter()
    for e in ev:
        who = "outside" if e["from"] == "entry" else f"{e['from']}.{e['from_func']}"   # a test or a library
        callers[(e["to"], e["func"], who)] += 1
    for i in r["internal"]:
        callers[(i["mod"], i["to"], f"{i['mod']}.{i['from']}")] += i["n"]
    return {
        "id": case["id"], "name": case["name"], "file": case["file"], "outcome": r["outcome"],
        "output": r.get("output", ""),
        "mods": sorted(mods),
        "funcs": [[f["mod"], f["func"], f["role"], f["calls"], f["self_ms"]] for f in r["funcs"]],
        "edges": [[a, b, n] for (a, b), n in edges.items()],
        "callers": [[m, fn, c, n] for (m, fn, c), n in callers.items()],
    }


def collect(root: Path, progress=None) -> dict:
    cases = runner.discover(root)
    tests = []
    for i, c in enumerate(cases, 1):
        if progress:
            progress(i, len(cases))
        tests.append(_record(c, runner.run_use_case(root, c["id"])))
    return {"project": root.name, "modules": modules.all_names(), "tests": tests}


def load(root: Path, fresh: bool = False, progress=None) -> dict:
    path = cache_dir() / (hashlib.sha1(str(root).encode()).hexdigest()[:16] + ".json")
    stamp = _stamp(root)
    if not fresh and path.exists():
        try:
            data = json.loads(path.read_text())
            if data.get("stamp") == stamp and data.get("version") == VERSION:
                return data
        except (OSError, ValueError):
            pass
    data = collect(root, progress)
    data["stamp"], data["version"] = stamp, VERSION
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data))
    except OSError:
        pass                                              # no cache is fine, only slower
    return data


class Index:
    """The totals the questions are answered from."""

    def __init__(self, data: dict) -> None:
        self.data = data
        self.tests = data["tests"]
        self.mod_tests: dict = {}        # module -> set of test numbers that reach it
        self.mod_self: Counter = Counter()   # module -> own time in the tests' actions
        self.func_tests: dict = {}       # (module, function) -> set of test numbers
        self.func_calls: Counter = Counter()
        self.callers: dict = {}          # (module, function) -> Counter of callers
        self.edge_tests: dict = {}       # (module, module) -> set of test numbers
        self.func_ms: Counter = Counter()    # (module, function) -> own time in the tests' actions
        self.func_action_tests: dict = {}    # (module, function) -> tests whose action ran it
        self.test_ms: Counter = Counter()    # test number -> own time of its action
        for i, t in enumerate(self.tests):
            for m, _role in t["mods"]:
                if m != "entry":
                    self.mod_tests.setdefault(m, set()).add(i)
            for m, fn, role, calls, ms in t["funcs"]:
                self.func_tests.setdefault((m, fn), set()).add(i)
                self.func_calls[(m, fn)] += calls
                if role != "setup":
                    self.mod_self[m] += ms
                    self.func_ms[(m, fn)] += ms
                    self.test_ms[i] += ms
                    self.func_action_tests.setdefault((m, fn), set()).add(i)
            for a, b, _n in t["edges"]:
                if a != "entry":
                    self.edge_tests.setdefault((a, b), set()).add(i)
            for m, fn, who, n in t["callers"]:
                self.callers.setdefault((m, fn), Counter())[who] += n

    @property
    def modules(self) -> list:
        return self.data["modules"]

    def failing(self) -> list:
        return [t for t in self.tests if t["outcome"] in ("failed", "error")]
