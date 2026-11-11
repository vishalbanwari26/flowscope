"""Which source files are the project's own code, and what each module is called.

The hook asks about every Python call in the process, library code included, so the
answer is cached per filename.
"""
from __future__ import annotations

import os
from collections import Counter
from pathlib import Path

# Folders that are never the project's own code. Matched against the path below the
# project root only, so a root that lives under a folder called "build" still works.
SKIP_DIRS = {".git", ".hg", ".venv", "venv", "env", ".env", "site-packages", "node_modules",
             "__pycache__", "build", "dist", ".tox", ".nox", ".mypy_cache", ".pytest_cache",
             ".ruff_cache", "tests", "test", "coverage", ".next", ".turbo", "__tests__", "__mocks__"}

PY_EXT = {".py"}
JS_EXT = {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".mts", ".cts"}


def is_js_project(root) -> bool:
    """A package.json that uses Jest or Vitest is a JavaScript or TypeScript project."""
    import json
    if os.environ.get("FLOWSCOPE_LANG") == "python":
        return False
    try:
        pkg = json.loads((Path(root) / "package.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
    return ("jest" in deps or "jest" in pkg or "vitest" in deps
            or any((Path(root) / f"{n}.config{e}").exists() for n in ("jest", "vitest")
                   for e in (".js", ".ts", ".cjs", ".mjs", ".mts", ".json")))


def is_project_file(rel: Path, exts=PY_EXT) -> bool:
    """rel is a path below the project root."""
    if rel.suffix not in exts:
        return False
    if exts is not PY_EXT:                           # JavaScript and TypeScript
        if any(part in SKIP_DIRS for part in rel.parts[:-1]):
            return False
        n = rel.name
        return not (".test." in n or ".spec." in n or n.endswith(".d.ts") or ".config." in n
                    or n.startswith("setupTests") or n.startswith("jest."))
    if any(part in SKIP_DIRS or part.endswith(".egg-info") for part in rel.parts[:-1]):
        return False
    name = rel.name
    return not (name in ("conftest.py", "setup.py") or name.startswith("test_")
                or name.endswith("_test.py"))


def _parts(rel: Path, root_name: str) -> list[str]:
    parts = list(rel.with_suffix("").parts)
    if parts and parts[0] == "src":
        parts = parts[1:]
    if parts and parts[-1] in ("__init__", "index"):
        parts = parts[:-1] or [root_name]       # a package is named after its folder
    return parts or [root_name]


class ModuleMap:
    def __init__(self, root) -> None:
        self.root = Path(root).resolve()
        self.names: dict = {}                    # filename -> module name, or None if not ours
        self.exts = JS_EXT if is_js_project(self.root) else PY_EXT
        files = self._walk()
        labels = {p: _parts(p.relative_to(self.root), self.root.name) for p in files}
        suffixes = Counter(".".join(parts[-k:]) for parts in labels.values()
                           for k in range(1, len(parts) + 1))
        for p, parts in labels.items():          # shortest name that is unique in the project
            for k in range(1, len(parts) + 1):
                candidate = ".".join(parts[-k:])
                if suffixes[candidate] == 1:
                    break
            self.names[str(p)] = candidate

    def _walk(self) -> list:
        found = []
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.endswith(".egg-info")]
            for f in filenames:
                p = Path(dirpath) / f
                if is_project_file(p.relative_to(self.root), self.exts):
                    found.append(p)
        return found

    def lookup(self, filename: str):
        try:
            return self.names[filename]
        except KeyError:
            pass
        name = None
        p = Path(filename)
        try:
            rel = p.relative_to(self.root)
        except ValueError:
            rel = None
        if rel is not None and is_project_file(rel, self.exts):   # created after startup, or not walked
            name = ".".join(_parts(rel, self.root.name)[-1:])
        self.names[filename] = name
        return name

    def all_names(self) -> list:
        return sorted({n for n in self.names.values() if n})


_map = None


def configure(root) -> ModuleMap:
    global _map
    _map = ModuleMap(root)
    return _map


def module_of(filename: str):
    return _map.lookup(filename) if _map else None


def all_names() -> list:
    return _map.all_names() if _map else []
