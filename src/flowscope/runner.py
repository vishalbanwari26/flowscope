"""Find a project's tests (its use cases) and run one with the hook on."""
from __future__ import annotations

import contextlib
import io
import threading

import pytest

from . import hook

_lock = threading.Lock()    # one use case at a time, so the active run is unambiguous
_cache: list = []


class _Collect:
    def __init__(self) -> None:
        self.ids: list = []

    def pytest_collection_modifyitems(self, items) -> None:
        self.ids = [i.nodeid for i in items]


class Outcome:
    """pytest plugin: the real result (pytest exits 0 on skip) and the test phase."""

    def __init__(self) -> None:
        self.outcome = "unknown"
        self.call_ms = None      # how long the test body took, as pytest measured it

    def pytest_runtest_setup(self, item) -> None:
        hook.set_phase("setup")

    def pytest_runtest_call(self, item) -> None:
        hook.set_phase("call")

    def pytest_runtest_teardown(self, item) -> None:
        hook.set_phase("teardown")

    def pytest_runtest_logreport(self, report) -> None:
        if report.when == "call":
            self.call_ms = report.duration * 1000
        if report.failed:
            self.outcome = "failed"
        elif report.skipped:
            self.outcome = "skipped"
        elif report.when == "call" and self.outcome == "unknown":
            self.outcome = "passed"


def _pytest(args: list, plugin) -> tuple:
    """Run pytest in-process, keeping its output out of the terminal."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        pytest.main(args + ["-q", "-p", "no:cacheprovider"], plugins=[plugin])
    return out.getvalue()


def label(nodeid: str) -> str:
    return nodeid.split("::")[-1].removeprefix("test_").replace("_", " ")


def discover(root) -> list:
    """Every collected test is a use case. The name is the test function, made readable."""
    if not _cache:
        c = _Collect()
        _pytest(["--collect-only", "--rootdir", str(root)], c)
        for nid in c.ids:
            parts = nid.split("::")
            _cache.append({"id": nid, "name": label(nid), "file": parts[0].split("/")[-1]})
    return _cache


def run_use_case(root, nodeid: str) -> dict:
    with _lock:
        oc = Outcome()
        run = hook.start_run(nodeid)
        captured = {}

        def target() -> None:             # new thread: the profile hook is on from the start
            captured["out"] = _pytest([nodeid, "--rootdir", str(root)], oc)

        t = threading.Thread(target=target)
        t.start()
        t.join()
        hook.end_run()
    outcome = "error" if oc.outcome == "unknown" else oc.outcome
    result = {"id": nodeid, "name": label(nodeid), "outcome": outcome,
              "passed": outcome == "passed", "call_ms": oc.call_ms}
    result.update(run.as_dict())
    if outcome != "passed":
        result["output"] = captured.get("out", "")[-2000:]
    return result
