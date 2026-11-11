"""The call tree of one run, and its plain-text form for the terminal."""
from __future__ import annotations

MAX_DEPTH = 30      # a recursive function would otherwise make the tree as deep as the recursion


def build_tree(events: list, keep=lambda e: True) -> list:
    """Calls as a tree: each call under the call that made it.

    Calls to the same function from the same place are merged into one node with a count
    and a summed time, so a loop that calls a helper 15 times is one line, "x15"."""
    by_id = {e["id"]: e for e in events}
    kids: dict = {}
    for e in events:
        if not keep(e):
            continue
        p = e.get("parent")
        while p is not None and p in by_id and not keep(by_id[p]):
            p = by_id[p].get("parent")          # a hidden parent: hang it on the nearest visible one
        kids.setdefault(p, []).append(e)

    def merge(group: list, depth: int) -> list:
        nodes: dict = {}
        for e in group:
            n = nodes.setdefault((e["to"], e["func"], e["role"]),
                                 {"mod": e["to"], "func": e["func"], "role": e["role"],
                                  "n": 0, "ms": 0.0, "ids": []})
            n["n"] += 1
            n["ms"] += e.get("ms", 0.0)
            n["ids"].append(e["id"])
        out = []
        for n in nodes.values():
            below = [c for i in n.pop("ids") for c in kids.get(i, [])]
            n["kids"] = merge(below, depth + 1) if below and depth < MAX_DEPTH else []
            out.append(n)
        return out

    return merge(kids.get(None, []), 0)


def fmt_ms(v: float) -> str:
    if v < 0.05:
        return "<0.1 ms"
    return f"{v:.1f} ms" if v < 10 else f"{round(v)} ms"


def pct(v: float, total: float) -> str:
    p = 100 * v / total if total else 0
    return "<1%" if p < 1 else f"{round(p)}%"


HOT = 0.2           # a call with at least this share of the time is always opened up


def _lines(nodes: list, total: float, depth: int, max_depth: int, out: list) -> None:
    shown = nodes[:12]
    for n in shown:
        tag = "[setup] " if n["role"] == "setup" else ""
        times = f" x{n['n']}" if n["n"] > 1 else ""
        label = f"{'  ' * depth}{tag}{n['mod']}.{n['func']}(){times}"
        # follow the heavy path past the depth limit, so the place the time goes is never hidden
        opened = depth + 1 < max_depth or (n["ms"] / total >= HOT and depth < 12)
        below = f"  [+{_count(n['kids'])} below]" if n["kids"] and not opened else ""
        out.append(f"  {label:<58} {pct(n['ms'], total):>5} {fmt_ms(n['ms']):>9}{below}")
        if n["kids"] and opened:
            _lines(n["kids"], total, depth + 1, max_depth, out)
    if len(nodes) > len(shown):
        out.append(f"  {'  ' * depth}... {len(nodes) - len(shown)} more")


def _count(nodes: list) -> int:
    return sum(1 + _count(n["kids"]) for n in nodes)


def render_bottleneck(result: dict) -> str:
    """Follow the call that took most of the time at each step, down to where it is really spent."""
    has_action = any(x["role"] != "setup" for x in result["events"] + result["internal"])
    only_setup = bool(result["events"]) and not has_action
    keep = (lambda x: True) if only_setup else (lambda x: x["role"] != "setup")
    tree = build_tree(result["events"], keep)
    out = [f"{result['name']}  [{result['outcome']}]"]
    if not tree:
        return "\n".join(out + ["", "No calls into the project were recorded, so there is no time to look at."])
    total = sum(n["ms"] for n in tree) or 1.0
    path, level = [], tree
    while level:
        node = max(level, key=lambda n: n["ms"])
        path.append(node)
        if not node["kids"]:
            break
        best = max(node["kids"], key=lambda n: n["ms"])
        if best["ms"] < 0.5 * node["ms"]:              # most of the time is the function's own
            break
        level = node["kids"]
    out += ["", "Heaviest path (at each step, the call that took most of the time):"]
    for d, n in enumerate(path):
        times = f" x{n['n']}" if n["n"] > 1 else ""
        out.append(f"  {'  ' * d}{n['mod']}.{n['func']}(){times}   {pct(n['ms'], total)}")
    last = path[-1]
    own = last["ms"] - sum(k["ms"] for k in last["kids"])
    out += ["", f"The time ends up in {last['mod']}.{last['func']}() itself: {pct(own, total)} of the total "
                "is its own work or waiting on something it calls outside the project."]
    funcs = sorted((f for f in result["funcs"] if keep(f)), key=lambda f: -f["self_ms"])[:3]
    fsum = sum(f["self_ms"] for f in result["funcs"] if keep(f)) or 1.0
    out += ["", "Most own time: " + ", ".join(f"{f['mod']}.{f['func']} {pct(f['self_ms'], fsum)}" for f in funcs)]
    return "\n".join(out + ["", "Times are measured with tracing on, which slows the code. Read them as shares."])


def error_lines(output: str, limit: int = 6) -> list:
    """The lines pytest prints for what went wrong: the ones that start with 'E'."""
    lines = [" ".join(l.split()) for l in (output or "").splitlines() if l.startswith("E ")]
    return [l for l in lines if len(l) > 1][:limit]            # drop blank "E" lines, squeeze spaces


def render_debug(result: dict) -> str:
    """What went wrong in one test, and the last calls it made before it stopped."""
    out = [f"{result['name']}  [{result['outcome']}]"]
    if result["outcome"] == "passed":
        return "\n".join(out + ["", "This test passes, so there is nothing to debug. "
                                    "To see what it runs: flowscope run <name>"])
    if result["outcome"] == "skipped":
        return "\n".join(out + ["", "This test was skipped, so it did not run."])
    errors = error_lines(result.get("output", ""), 8)
    out += ["", "What went wrong:"] + (["  " + l for l in errors] if errors else
                                       ["  (no error line captured, the end of pytest's output is below)"])
    last = result["events"][-6:]
    if last:
        out += ["", "The last calls into the project before it stopped (newest last):"]
        out += [f"  {e['from']} -> {e['to']}.{e['func']}()" for e in last]
    elif not errors:
        out += ["", result.get("output", "")[-600:]]
    return "\n".join(out + ["", "The full flow of this test: flowscope run <name>"])


def render(result: dict, show_setup: bool = False, depth: int = 3) -> str:
    has_action = any(x["role"] != "setup" for x in result["events"] + result["internal"])
    only_setup = bool(result["events"]) and not has_action     # hiding it would leave nothing
    show_all = show_setup or only_setup
    keep = (lambda x: True) if show_all else (lambda x: x["role"] != "setup")
    events = [e for e in result["events"] if keep(e)]
    funcs = [f for f in result["funcs"] if keep(f)]
    internal = [i for i in result["internal"] if keep(i)]
    total = sum(f["self_ms"] for f in funcs) or 1.0
    tree = build_tree(result["events"], keep)
    root_ms = sum(n["ms"] for n in tree) or 1.0

    lines = [f"{result['name']}  [{result['outcome']}]"]
    hidden = len(result["events"]) - len(events)
    lines.append(f"{len(events)} calls"
                 + (f"  ({hidden} setup calls hidden, use --setup to show)" if hidden else ""))
    if only_setup and not show_setup:
        lines.append("Every call recorded here is setup-style (constructors, builders), "
                     "so they are shown. The test is probably about one of them.")
    lines += ["", "What it calls (share of the time, calls made inside are indented):"]
    _lines(tree, root_ms, 0, depth, lines)

    mods: dict = {}
    for f in funcs:
        mods[f["mod"]] = mods.get(f["mod"], 0.0) + f["self_ms"]
    if mods:
        lines += ["", "Own time by module (not counting the modules it calls):"]
        for m, ms in sorted(mods.items(), key=lambda kv: -kv[1])[:8]:
            lines.append(f"  {m:<24} {pct(ms, total)}")
        if len(mods) > 8:
            lines.append(f"  ... {len(mods) - 8} more modules")

    if any(i["from"] != i["to"] for i in internal):
        lines += ["", "To see the functions inside a module: flowscope lld <module>"]

    if result.get("output"):
        lines += ["", "pytest output (tail):", result["output"]]
    lines += ["", "Times are measured with tracing on, which slows the code. Read them as shares."]
    return "\n".join(lines)
