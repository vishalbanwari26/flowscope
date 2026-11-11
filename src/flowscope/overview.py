"""Plain-text answers to the project-wide questions: hld, lld, scope, debug."""
from __future__ import annotations

from .report import error_lines, fmt_ms, pct
from .survey import Index

TOP = 15


def _names(items: list, width: int = 88, cap: int = 40) -> list:
    """Wrap a list of names into lines."""
    lines, line = [], "  "
    for name in items[:cap]:
        if len(line) + len(name) + 2 > width:
            lines.append(line.rstrip(", "))
            line = "  "
        line += name + ", "
    lines.append(line.rstrip(", "))
    if len(items) > cap:
        lines.append(f"  ... and {len(items) - cap} more")
    return lines


def hld(ix: Index) -> str:
    n = len(ix.tests)
    failed = len(ix.failing())
    total = sum(ix.mod_self.values()) or 1.0
    ranked = sorted(ix.mod_tests, key=lambda m: (-len(ix.mod_tests[m]), m))
    out = [f"{ix.data['project']}: {n} tests{f' ({failed} fail)' if failed else ''}, {len(ix.modules)} modules", "",
           "Modules, by how many tests reach them:"]
    for m in ranked[:TOP]:
        out.append(f"  {m:<28} {len(ix.mod_tests[m]):>4} tests   {pct(ix.mod_self.get(m, 0.0), total):>4} of the time")
    if len(ranked) > TOP:
        out.append(f"  ... {len(ranked) - TOP} more")
    untouched = sorted(set(ix.modules) - set(ix.mod_tests))
    out += ["", f"No test reaches ({len(untouched)}):" if untouched else "Every module is reached by a test."]
    if untouched:
        out += _names(untouched)
    links = sorted(ix.edge_tests.items(), key=lambda kv: -len(kv[1]))
    if links:
        out += ["", "Main links (one module calling another):"]
        out += [f"  {a} -> {b}  ({len(t)} tests)" for (a, b), t in links[:10]]
    out += ["", "Next: lld <module> for the functions inside one, scope <name> for the tests that reach it."]
    return "\n".join(out)


def _resolve_module(ix: Index, name: str):
    if name in ix.modules or name in ix.mod_tests:
        return name, []
    hits = sorted(m for m in set(ix.modules) | set(ix.mod_tests) if name.lower() in m.lower())
    return (hits[0], []) if len(hits) == 1 else (None, hits)


def lld(ix: Index, name: str) -> str:
    mod, options = _resolve_module(ix, name)
    if mod is None:
        return (f"No module matches {name!r}. Did you mean:\n" + "\n".join(f"  {m}" for m in options[:10])
                if options else f"No module matches {name!r}. Run hld to see the modules.")
    total = sum(ix.mod_self.values()) or 1.0
    reached = ix.mod_tests.get(mod, set())
    out = [f"{mod}: reached by {len(reached)} of {len(ix.tests)} tests, "
           f"{pct(ix.mod_self.get(mod, 0.0), total)} of the time"]
    if not reached:
        out += ["", "No test runs anything in this module."]
        return "\n".join(out)
    funcs = sorted((k for k in ix.func_tests if k[0] == mod),
                   key=lambda k: (-len(ix.func_tests[k]), -ix.func_calls[k], k[1]))
    out += ["", "Functions that ran (most tests first):"]
    for k in funcs[:TOP]:
        who = ", ".join(f"{c} x{n}" for c, n in ix.callers.get(k, {}).most_common(3)) or "-"
        out.append(f"  {k[1]:<30} {len(ix.func_tests[k]):>4} tests  {ix.func_calls[k]:>5} calls   called by {who}")
    if len(funcs) > TOP:
        out.append(f"  ... {len(funcs) - TOP} more")
    into = sorted(((b, t) for (a, b), t in ix.edge_tests.items() if a == mod and b != mod),
                  key=lambda x: -len(x[1]))
    if into:
        out += ["", "It calls into: " + ", ".join(f"{b} ({len(t)} tests)" for b, t in into[:8])]
    out += ["", '"outside" means called from a test, or from a library calling back into this project.']
    return "\n".join(out)


def _mark(t: dict) -> str:
    return {"passed": "ok  ", "failed": "FAIL", "error": "ERR ", "skipped": "skip"}.get(t["outcome"], "?   ")


def scope(ix: Index, query: str) -> str:
    mod, func, options = None, None, []
    if query in ix.modules or query in ix.mod_tests:
        mod = query
    elif "." in query and (query.rsplit(".", 1)[0] in ix.modules or query.rsplit(".", 1)[0] in ix.mod_tests):
        mod, func = query.rsplit(".", 1)
    else:
        hits = sorted(k for k in ix.func_tests if k[1] == query)
        if len(hits) == 1:
            mod, func = hits[0]
        elif hits:
            options = [f"{m}.{f}" for m, f in hits]
        else:
            hits = sorted(m for m in set(ix.modules) | set(ix.mod_tests) if query.lower() in m.lower())
            if len(hits) == 1:
                mod = hits[0]
            else:
                options = hits
    if mod is None:
        return (f"{query!r} matches more than one:\n" + "\n".join(f"  {o}" for o in options[:15])
                if options else f"Nothing called {query!r}. Run hld to see the modules.")
    label = f"{mod}.{func}" if func else mod
    idx = ix.func_tests.get((mod, func), set()) if func else ix.mod_tests.get(mod, set())
    if func and (mod, func) not in ix.func_tests:
        known = sorted(f for m, f in ix.func_tests if m == mod)
        return (f"No test runs {label}." + (f" Functions in {mod} that tests do run:\n" + "\n".join(_names(known))
                                              if known else ""))
    if not idx:
        return f"No test runs {label}. That says it is untested, not that it is unused."
    out = [f"Tests that reach {label} ({len(idx)} of {len(ix.tests)}):"]
    for i in sorted(idx)[:25]:
        t = ix.tests[i]
        out.append(f"  [{_mark(t)}] {t['file']}: {t['name']}")
    if len(idx) > 25:
        out.append(f"  ... {len(idx) - 25} more")
    return "\n".join(out)


def bottleneck(ix: Index) -> str:
    total = sum(ix.func_ms.values())
    if not total:
        return "No time was recorded. Either no test calls into the project, or only setup does."
    out = [f"Where the time goes across {len(ix.tests)} tests (what they do, not their setup):", ""]
    for (m, fn), ms in ix.func_ms.most_common(8):
        out.append(f"  {m + '.' + fn:<44} {pct(ms, total):>5}   in {len(ix.func_action_tests[(m, fn)])} tests")
    out += ["", "Slowest tests (compare them with each other, not with a stopwatch):"]
    for i, ms in ix.test_ms.most_common(5):
        t = ix.tests[i]
        acts = [(f[4], f[0], f[1]) for f in t["funcs"] if f[2] != "setup"]
        own, mod, fn = max(acts)
        out += [f"  {t['file']}: {t['name'][:60]}",
                f"      {fmt_ms(ms)} with tracing, {pct(own, ms)} of it in {mod}.{fn}"]
    out += ["", "A function's own time includes waiting on what it calls outside the project: the disk,",
            "the network, another program. A big share is a place to look, not proof of a problem.",
            "", "Next: findbottleneck <test> for one test's heaviest path."]
    return "\n".join(out)


def debug_all(ix: Index) -> str:
    bad = ix.failing()
    if not bad:
        return f"All {len(ix.tests)} tests pass or are skipped. Nothing to debug."
    out = [f"{len(bad)} of {len(ix.tests)} tests fail:"]
    for t in bad[:20]:
        first = (error_lines(t["output"], 1) or ["(no error line captured)"])[0]
        out += [f"  {t['file']}: {t['name']}", f"      {first[:110]}"]
    if len(bad) > 20:
        out.append(f"  ... {len(bad) - 20} more")
    out += ["", "Next: debug <name> for one test, with the last calls before it stopped."]
    return "\n".join(out)
