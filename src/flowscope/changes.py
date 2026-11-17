"""Behavior diff: what a change did to what the system does.

A code diff says which lines moved. This says which behaviors moved. It runs the tests at a
base commit and now, then compares the two runs use case by use case: the calls between
modules, the functions that ran, how much of the time they took, and whether the test still
passes. It also checks the changed lines against the traces, so code that changed and that no
test ran shows up as a blind spot.

Tests show what ran, not why. The diff cannot say whether a new call is right.
"""
from __future__ import annotations

import difflib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

from . import gaps, survey
from .brief import action_edges

MAX_PHRASES = 4


# ---------------------------------------------------------------- git

def _git(cwd, *args, check: bool = True) -> str:
    r = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True)
    if r.returncode and check:
        raise SystemExit(f"flowscope: git {' '.join(args[:2])} failed: {(r.stderr or r.stdout).strip()[:300]}")
    return r.stdout.strip()


def locate(root: Path) -> tuple:
    """(repository top, the project's folder below it)."""
    top = _git(root, "rev-parse", "--show-toplevel", check=False)
    if not top:
        raise SystemExit("flowscope: changes needs a git repository, to know what the base is.")
    top = Path(top).resolve()
    return top, root.resolve().relative_to(top)


def is_dirty(top: Path) -> bool:
    return bool(_git(top, "status", "--porcelain", "--untracked-files=no", check=False))


def resolve_base(top: Path, ref: str | None) -> str:
    """The commit to compare with. With no ref: HEAD when there are uncommitted changes, else HEAD~1.
    For a branch name the common ancestor is used, so only this branch's own changes are shown."""
    ref = ref or ("HEAD" if is_dirty(top) else "HEAD~1")
    if not _git(top, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}", check=False):
        if ref == "HEAD~1":
            raise SystemExit("flowscope: nothing to compare: the tree is clean and there is only one commit. "
                             "Change something, or name a commit or branch: flowscope changes <ref>")
        raise SystemExit(f"flowscope: {ref!r} is not a commit in this repository.")
    return _git(top, "merge-base", ref, "HEAD", check=False) or _git(top, "rev-parse", ref)


HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def changed_lines(top: Path, sha: str) -> dict:
    """File (relative to the repository) -> line ranges that differ from the base, new side."""
    out: dict = {}
    cur = None
    for line in _git(top, "diff", "-U0", "--no-renames", "--no-color", sha, "--").splitlines():
        if line.startswith("+++ "):
            cur = line[6:] if line.startswith("+++ b/") else None
            if cur:
                out.setdefault(cur, [])
        elif cur and (m := HUNK.match(line)):
            start, n = int(m.group(1)), int(m.group(2) if m.group(2) is not None else 1)
            out[cur].append((start, start + n - 1) if n else (start, start + 1))   # a pure deletion marks the lines around it
    for f in _git(top, "ls-files", "--others", "--exclude-standard", check=False).splitlines():
        if not f.startswith("explain-output/") and "/explain-output/" not in f:   # flowscope's own pages
            out[f] = [(1, 10 ** 9)]                                          # a new file is all changed
    return out


# ---------------------------------------------------------------- the base run

def _cache_path(root: Path, sha: str) -> Path:
    key = hashlib.sha1(str(root).encode()).hexdigest()[:10]
    return survey.cache_dir() / f"base-{sha[:12]}-{key}.json"


def base_run(root: Path, top: Path, prefix: Path, sha: str) -> dict:
    """The saved overview of the project at a commit: {"data", "items"}. Cached per commit.
    Runs in its own process, because the project's modules are already loaded in this one."""
    cache = _cache_path(root, sha)
    try:
        saved = json.loads(cache.read_text())
        if saved.get("version") == survey.VERSION:
            return saved
    except (OSError, ValueError):
        pass
    work = Path(tempfile.mkdtemp(prefix="flowscope-base-"))
    out = work.with_suffix(".json")
    try:
        _git(top, "worktree", "add", "--detach", "--force", str(work), sha)
        proj = work / prefix
        for name in ("node_modules",):                       # installed packages are not in git
            if (root / name).exists() and not (proj / name).exists():
                os.symlink(root / name, proj / name)
        r = subprocess.run([sys.executable, "-m", "flowscope", "_dump", str(proj), str(out)],
                           capture_output=True, text=True)
        if r.returncode or not out.exists():
            raise SystemExit("flowscope: the base commit's tests could not be run.\n" + (r.stderr or r.stdout)[-600:])
        saved = json.loads(out.read_text())
    finally:
        subprocess.run(["git", "-C", str(top), "worktree", "remove", "--force", str(work)], capture_output=True)
        shutil.rmtree(work, ignore_errors=True)
        out.unlink(missing_ok=True)
    try:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(saved))
    except OSError:
        pass
    return saved


# ---------------------------------------------------------------- the diff

def collapse(seq: list) -> list:
    """Cross-module calls in order; the same call repeated right after itself becomes one row with a count."""
    rows: list = []
    for a, b, fn, d in seq:
        if rows and rows[-1][:4] == [a, b, fn, d]:
            rows[-1][4] += 1
        else:
            rows.append([a, b, fn, d, 1])
    return rows


def align(left: list, right: list) -> list:
    """Windiff for calls: rows of (before, after, kind), kind is same, count, del, add or chg."""
    sm = difflib.SequenceMatcher(None, [tuple(x[:4]) for x in left], [tuple(x[:4]) for x in right], autojunk=False)
    rows = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        L, R = left[i1:i2], right[j1:j2]
        if tag == "equal":
            rows += [(a, b, "same" if a[4] == b[4] else "count") for a, b in zip(L, R)]
            continue
        for k in range(max(len(L), len(R))):
            a, b = (L[k] if k < len(L) else None), (R[k] if k < len(R) else None)
            rows.append((a, b, "chg" if a and b else "del" if a else "add"))
    return rows


def _call(row: list) -> str:
    who = "test" if row[0] == "entry" else row[0]
    return f"{who} → {row[1]}.{row[2]}"


def _ran(t: dict) -> dict:
    """(module, function) -> calls, for the functions the test's own action ran."""
    return {(m, f): calls for m, f, role, calls, _ms in t["funcs"] if role != "setup"}


def _same_test(b: dict, h: dict) -> dict:
    """Compare one use case before and after."""
    rows = align(collapse(b.get("seq", [])), collapse(h.get("seq", [])))
    ran_b, ran_h = _ran(b), _ran(h)
    seen = {(r[1], r[2]) for r in collapse(b.get("seq", [])) + collapse(h.get("seq", []))}
    added = sorted(k for k in ran_h if k not in ran_b)
    gone = sorted(k for k in ran_b if k not in ran_h)
    more = sorted((k, ran_b[k], ran_h[k]) for k in ran_b if k in ran_h and ran_b[k] != ran_h[k] and k not in seen)
    phrases = []
    for a, bb, kind in rows:
        if kind == "add":
            phrases.append(f"now calls {bb[1]}.{bb[2]}")
        elif kind == "del":
            phrases.append(f"no longer calls {a[1]}.{a[2]}")
        elif kind == "count":
            phrases.append(f"{a[1]}.{a[2]} {a[4]}x → {bb[4]}x")
        elif kind == "chg":
            phrases.append(f"{a[1]}.{a[2]} replaced by {bb[1]}.{bb[2]}")
    phrases += [f"{m}.{f} now runs" for m, f in added if (m, f) not in seen]
    phrases += [f"{m}.{f} no longer runs" for m, f in gone if (m, f) not in seen]
    phrases += [f"{m}.{f} {x}x → {y}x" for (m, f), x, y in more]
    inside = [(m, f, ran_b.get((m, f), 0), ran_h.get((m, f), 0)) for m, f in added + gone if (m, f) not in seen]
    inside += [(m, f, x, y) for (m, f), x, y in more]
    changed = any(k != "same" for _, _, k in rows) or bool(added or gone or more)
    return {"rows": rows, "phrases": phrases, "added": added, "gone": gone, "inside": inside[:8], "shift": None, "changed": changed}


def _pair_renamed(bt: dict, ht: dict) -> dict:
    """Tests that exist only before are matched to tests that exist only after, in the same file, when their
    call sequences are alike. Returns old id -> new id."""
    only_h = [j for j in ht if j not in bt]
    pairs: dict = {}
    for i in (i for i in bt if i not in ht):
        best = None
        for j in only_h:
            if j in pairs.values() or bt[i]["file"] != ht[j]["file"]:
                continue
            ratio = difflib.SequenceMatcher(None, [tuple(x[:3]) for x in bt[i].get("seq", [])],
                                            [tuple(x[:3]) for x in ht[j].get("seq", [])], autojunk=False).ratio()
            if ratio >= 0.6 and (best is None or ratio > best[0]):
                best = (ratio, j)
        if best:
            pairs[i] = best[1]
    return pairs


def _status(b, h, d) -> str:
    if b is None:
        return "new"
    if h is None:
        return "removed"
    ok = lambda t: t["outcome"] == "passed"
    if ok(b) and not ok(h) and h["outcome"] != "skipped":
        return "broke"
    if not ok(b) and ok(h):
        return "fixed"
    return "changed" if d["changed"] else "same"


ORDER = {"broke": 0, "changed": 1, "new": 2, "fixed": 3, "removed": 4, "same": 5}


def _edges(ix) -> set:
    out = set()
    for t in ix.tests:
        out |= {(a, b) for a, b, _n in action_edges(t) if a != "entry" and a != b}
    return out


def blind_spots(items: list, ix, changed: dict, prefix: Path) -> list:
    """Functions whose lines changed and that no test ran. Python lists every function;
    JavaScript and TypeScript only the exported ones."""
    ran = {(m, f) for m, f in ix.func_tests}
    found = []
    for it in items:
        rel, _, line = it["where"].rpartition(":")
        ranges = changed.get((prefix / rel).as_posix(), [])
        a, z = int(line), int(line) + it["size"] - 1
        hit = [(x, y) for x, y in ranges if x <= z and y >= a]
        if hit and (it["module"], it["name"]) not in ran:
            found.append({"module": it["module"], "name": it["qual"], "where": it["where"], "size": it["size"],
                          "entry": it["entry"]})
    return sorted(found, key=lambda f: (not f["entry"], -f["size"], f["module"], f["name"]))


def _public(items: list) -> set:
    return {(i["module"], i["qual"]) for i in items if not i["name"].startswith("_")}


def diff(base: dict, head: dict, changed: dict, prefix: Path) -> dict:
    """base and head are {"data", "items"}: the saved overview and the source scan."""
    bix, hix = survey.Index(base["data"]), survey.Index(head["data"])
    bt = {t["id"]: t for t in bix.tests}
    ht = {t["id"]: t for t in hix.tests}
    renamed = _pair_renamed(bt, ht)                       # a rewritten or renamed test is one use case, not two
    back = {new: old for old, new in renamed.items()}
    pairs = [(bt.get(back.get(tid, tid)), ht[tid]) for tid in ht]
    pairs += [(bt[i], None) for i in bt if i not in ht and i not in renamed]
    cases = []
    for b, h in pairs:
        tid = (h or b)["id"]
        d = _same_test(b, h) if b and h else {"rows": [], "phrases": [], "added": [], "gone": [], "inside": [], "shift": None, "changed": False}
        if b and h and b["id"] != h["id"]:
            d["phrases"].insert(0, f"renamed from: {b['name']}")
            d["changed"] = True
        t = h or b
        if b is None and h:
            d["rows"] = align([], collapse(h.get("seq", [])))
        if h is None and b:
            d["rows"] = align(collapse(b.get("seq", [])), [])
        cases.append({"id": tid, "name": t["name"], "file": t["file"], "status": _status(b, h, d),
                      "before": b["outcome"] if b else None, "after": h["outcome"] if h else None,
                      "error": ((h or {}).get("output") or "") if h and h["outcome"] in ("failed", "error") else "", **d})
    cases.sort(key=lambda c: (ORDER[c["status"]], c["file"], c["name"]))
    lead: dict = {}
    for c in cases:                                  # tests whose first change is the same are shown once, the rest listed under it
        c["same_as"] = []
        if c["status"] == "changed" and c["phrases"]:
            first = lead.setdefault(c["phrases"][0], c)
            if first is not c:
                first["same_as"].append(c["name"])
                c["dup"] = True
    eb, eh = _edges(bix), _edges(hix)
    blind = blind_spots(head["items"], hix, changed, prefix)
    sb, sh = _public(base["items"]), _public(head["items"])
    count = Counter(c["status"] for c in cases)
    result = {
        "project": head["data"]["project"], "counts": dict(count), "cases": cases, "blind": blind,
        "new_edges": sorted(eh - eb), "gone_edges": sorted(eb - eh),
        "new_modules": sorted(set(hix.mod_tests) - set(bix.mod_tests)),
        "gone_modules": sorted(set(bix.mod_tests) - set(hix.mod_tests)),
        "added_api": sorted(sh - sb), "removed_api": sorted(sb - sh),
        "files_changed": len(changed),
    }
    result["first"] = read_first(result)
    return result


def read_first(r: dict) -> list:
    """What to look at first, worst first: the diff in the order a reviewer should read it."""
    out = []
    for c in r["cases"]:
        if c["status"] == "broke":
            out.append({"kind": "broke", "text": f"{c['name']} passed before and fails now", "id": c["id"]})
    for b in r["blind"][:5]:
        out.append({"kind": "blind", "text": f"{b['module']}.{b['name']} changed and no test runs it ({b['where']})"})
    for a, b in r["new_edges"][:4]:
        out.append({"kind": "edge", "text": f"{a} now calls {b}, and did not before"})
    for c in r["cases"]:
        if c["status"] == "changed" and c["phrases"] and not c.get("dup"):
            more = f" (and {len(c['same_as'])} more behaviors)" if c["same_as"] else ""
            out.append({"kind": "changed", "text": f"{c['name']}{more}: {c['phrases'][0]}", "id": c["id"]})
    for m, q in r["added_api"][:3]:
        out.append({"kind": "api", "text": f"new public function {m}.{q}"})
    for m, q in r["removed_api"][:3]:
        out.append({"kind": "api", "text": f"public function {m}.{q} is gone"})
    return out[:8]


# ---------------------------------------------------------------- text

def headline(r: dict) -> str:
    n = r["counts"]
    moved = n.get("changed", 0) + n.get("new", 0) + n.get("broke", 0) + n.get("removed", 0) + n.get("fixed", 0)
    if not moved and not r["blind"]:
        return "No behavior changed."
    bits = [f"{n[k]} {label}" for k, label in (("broke", "broke"), ("changed", "changed"), ("new", "new"),
                                                ("fixed", "fixed"), ("removed", "removed")) if n.get(k)]
    if r["blind"]:
        bits.append(f"{len(r['blind'])} changed with no test")
    return ", ".join(bits).capitalize() + f". {n.get('same', 0)} unchanged."


def render_text(r: dict, base_label: str, head_label: str) -> str:
    out = [f"{r['project']}: {base_label} -> {head_label}", headline(r), ""]
    if r["first"]:
        out.append("Read these first:")
        out += [f"  {i}. {x['text']}" for i, x in enumerate(r["first"], 1)]
    for c in r["cases"]:
        if c["status"] == "same" or c.get("dup"):
            continue
        more = f"  (+{len(c['same_as'])} more with the same change)" if c["same_as"] else ""
        out += ["", f"{c['status'].upper():<8} {c['name']}{more}"]
        out += [f"           {p}" for p in c["phrases"][:MAX_PHRASES]]
    return "\n".join(out)


def render_md(r: dict, base_label: str, head_label: str) -> str:
    """A short comment for a pull request."""
    out = [f"**Behavior diff** ({base_label} → {head_label}): {headline(r)}", ""]
    for x in r["first"]:
        out.append(f"- {x['text']}")
    return "\n".join(out)
