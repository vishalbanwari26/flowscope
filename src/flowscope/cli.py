"""Command line: flowscope serve | list | run."""
from __future__ import annotations

import argparse
import json
import os
import sys
import webbrowser
from pathlib import Path

from . import __version__, hook, modules, report


def _runner():
    """Import the runner, which needs pytest, with a clear message when it is missing."""
    try:
        from . import runner
    except ModuleNotFoundError as e:
        if e.name != "pytest":
            raise
        sys.exit(f"flowscope: pytest is not installed for {sys.executable}.\n"
                 "Run it with the project's own Python, which has the project's test dependencies.")
    return runner


def _prepare(path: str) -> Path:
    """Make the project importable and hook it. Run from the project's own Python."""
    root = Path(path).resolve()
    if not root.is_dir():
        sys.exit(f"flowscope: {root} is not a folder")
    os.chdir(root)                      # tests often read files relative to the project root
    for p in (root / "src", root):
        if p.is_dir() and str(p) not in sys.path:
            sys.path.insert(0, str(p))
    modules.configure(root)
    hook.install()
    return root


def _find(root: Path, query: str) -> dict:
    cases = _runner().discover(root)
    exact = [c for c in cases if c["id"] == query]
    hits = exact or [c for c in cases if query.lower() in c["id"].lower() or query.lower() in c["name"].lower()]
    if not hits:
        sys.exit(f"flowscope: no use case matches {query!r}. Try: flowscope list")
    if len(hits) > 1:
        names = "\n".join(f"  {c['id']}" for c in hits[:10])
        sys.exit(f"flowscope: {len(hits)} use cases match {query!r}, be more specific:\n{names}")
    return hits[0]


def cmd_serve(args) -> None:
    runner = _runner()
    from .server import make_server
    root = _prepare(args.path)
    cases = runner.discover(root)
    if not cases:
        sys.exit("flowscope: no pytest tests found, so there are no use cases to show")
    server = make_server(root, args.port)
    url = f"http://localhost:{server.server_address[1]}/?t={server.token}"
    # flush: when output goes to a file or a pipe, Python holds it back until exit
    print(f"flowscope: {len(cases)} use cases, {len(modules.all_names())} modules in {root}", flush=True)
    print(f"open {url}", flush=True)
    print("Running a use case runs that test in this process. Press Ctrl+C to stop.", flush=True)
    if not args.no_open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")


def cmd_list(args) -> None:
    runner = _runner()
    root = _prepare(args.path)
    for c in runner.discover(root):
        print(f"{c['id']}\t{c['name']}")


def _index(args):
    """The project-wide survey: every test run once, then cached."""
    _runner()                                   # a clear message if pytest is missing
    from . import survey
    root = _prepare(args.path)

    def progress(i, n):
        if i == 1:
            print(f"flowscope: running {n} tests once to build the overview; it is saved for next time",
                  file=sys.stderr, flush=True)

    return survey.Index(survey.load(root, fresh=args.fresh, progress=progress))


def cmd_hld(args) -> None:
    from . import overview
    print(overview.hld(_index(args)))


def cmd_lld(args) -> None:
    from . import overview
    print(overview.lld(_index(args), args.module))


def cmd_scope(args) -> None:
    from . import overview
    print(overview.scope(_index(args), args.name))


def _test_or_folder(args) -> None:
    """With one optional argument, a folder means the project and anything else a test name."""
    if args.use_case and args.path == "." and Path(args.use_case).is_dir():
        args.path, args.use_case = args.use_case, None


def cmd_debug(args) -> None:
    from . import overview
    _test_or_folder(args)
    if not args.use_case:
        return print(overview.debug_all(_index(args)))
    runner = _runner()
    root = _prepare(args.path)
    print(report.render_debug(runner.run_use_case(root, _find(root, args.use_case)["id"])))


def cmd_bottleneck(args) -> None:
    from . import overview
    _test_or_folder(args)
    if not args.use_case:
        return print(overview.bottleneck(_index(args)))
    runner = _runner()
    root = _prepare(args.path)
    print(report.render_bottleneck(runner.run_use_case(root, _find(root, args.use_case)["id"])))


def cmd_gaps(args) -> None:
    """Public functions no test runs. Works with no tests and with no pytest installed."""
    from . import gaps
    root = _prepare(args.path)                  # also puts the project on sys.path, so tests import
    names = modules.configure(root).names
    items = gaps.scan(root, names)
    tested, n_tests = None, 0
    try:
        has_tests = bool(_runner().discover(root))
    except SystemExit:
        has_tests = False                        # pytest missing: treat as no tests, and say so
        print("flowscope: pytest is not installed here, so every function is shown as untested.",
              file=sys.stderr)
    if has_tests:
        ix = _index(args)
        tested, n_tests = {(m, f) for m, f in ix.func_tests}, len(ix.tests)
    print(gaps.render(items, tested, n_tests))


def cmd_run(args) -> None:
    runner = _runner()
    root = _prepare(args.path)
    case = _find(root, args.use_case)
    result = runner.run_use_case(root, case["id"])
    print(json.dumps(result, indent=1) if args.json else report.render(result, args.setup, args.depth))


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(
        prog="flowscope",
        description="Pick a test, see how the code flows through your modules. "
                    "Run it with the project's own Python so its tests can import their dependencies.")
    ap.add_argument("--version", action="version", version=f"flowscope {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("serve", help="open the viewer in a browser")
    s.add_argument("path", nargs="?", default=".")
    s.add_argument("--port", type=int, default=0, help="default: any free port")
    s.add_argument("--no-open", action="store_true", help="print the URL, do not open a browser")
    s.set_defaults(fn=cmd_serve)

    s = sub.add_parser("list", help="list the use cases (tests)")
    s.add_argument("path", nargs="?", default=".")
    s.set_defaults(fn=cmd_list)

    s = sub.add_parser("run", help="run one use case and print its flow")
    s.add_argument("use_case", help="a test id, or part of its name")
    s.add_argument("path", nargs="?", default=".")
    s.add_argument("--json", action="store_true", help="print the raw recording")
    s.add_argument("--setup", action="store_true", help="include setup calls")
    s.add_argument("--depth", type=int, default=3, help="how many levels of calls to print (default 3)")
    s.set_defaults(fn=cmd_run)

    fresh = {"action": "store_true", "help": "run the tests again instead of using the saved overview"}

    s = sub.add_parser("hld", help="the project's modules, and which tests reach them")
    s.add_argument("path", nargs="?", default=".")
    s.add_argument("--fresh", **fresh)
    s.set_defaults(fn=cmd_hld)

    s = sub.add_parser("lld", help="the functions that ran inside one module")
    s.add_argument("module")
    s.add_argument("path", nargs="?", default=".")
    s.add_argument("--fresh", **fresh)
    s.set_defaults(fn=cmd_lld)

    s = sub.add_parser("scope", help="which tests reach a module or a function")
    s.add_argument("name", help="a module, or module.function")
    s.add_argument("path", nargs="?", default=".")
    s.add_argument("--fresh", **fresh)
    s.set_defaults(fn=cmd_scope)

    s = sub.add_parser("debug", help="what went wrong in a failing test; with no test, list the failing ones")
    s.add_argument("use_case", nargs="?", help="a test id, or part of its name")
    s.add_argument("path", nargs="?", default=".")
    s.add_argument("--fresh", **fresh)
    s.set_defaults(fn=cmd_debug)

    s = sub.add_parser("bottleneck", help="where the time goes: across all tests, or in one test")
    s.add_argument("use_case", nargs="?", help="a test id, or part of its name")
    s.add_argument("path", nargs="?", default=".")
    s.add_argument("--fresh", **fresh)
    s.set_defaults(fn=cmd_bottleneck)

    s = sub.add_parser("gaps", help="public functions no test runs, entry points first; works with no tests")
    s.add_argument("path", nargs="?", default=".")
    s.add_argument("--fresh", **fresh)
    s.set_defaults(fn=cmd_gaps)

    args = ap.parse_args(argv)
    args.fn(args)
