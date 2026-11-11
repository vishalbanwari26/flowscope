"""The profile hook: which project functions run, how long they take, and whether each
belongs to a test's setup or to its action.

Cross-module calls are kept one by one, in order, so they can be replayed. Calls that
stay inside a module are only counted per function pair, for drill-down.
"""
from __future__ import annotations

import sys
import threading
import time

from . import modules

ACTIVE = None   # the Run being recorded, or None
PHASE = None    # pytest phase of the running test: "setup", "call" or "teardown"
_tls = threading.local()   # per thread: the open entry call and its role, and the timed stack


class Run:
    def __init__(self, name: str) -> None:
        self.name = name
        self.events: list = []     # cross-module calls, in order
        self.internal: dict = {}   # (module, caller_func, func, role) -> count
        self.funcs: dict = {}      # (module, func, role) -> [calls, self_seconds]

    def as_dict(self) -> dict:
        return {
            "events": self.events,
            "internal": [{"mod": m, "from": a, "to": b, "role": r, "n": n}
                         for (m, a, b, r), n in self.internal.items()],
            "funcs": [{"mod": m, "func": f, "role": r, "calls": c, "self_ms": s * 1000}
                      for (m, f, r), (c, s) in self.funcs.items()],
        }


def start_run(name: str) -> Run:
    global ACTIVE
    ACTIVE = Run(name)
    return ACTIVE


def end_run() -> Run:
    global ACTIVE, PHASE
    run, ACTIVE, PHASE = ACTIVE, None, None
    return run


def set_phase(phase) -> None:
    global PHASE
    PHASE = phase


SETUP_PREFIXES = ("add_", "set_", "seed", "generate", "create", "build", "make", "load",
                  "reset", "insert", "populate", "register", "init")


def role_for(func_name: str) -> str:
    """Is a call from outside the project part of the test's setup, or of its action?

    Judged by the function called, not by who called it: a test helper often does both
    (build a store, then run the detector), so the caller says nothing."""
    if PHASE in ("setup", "teardown"):
        return "setup"                      # fixtures
    if func_name == "__init__" or func_name.startswith(SETUP_PREFIXES):
        return "setup"                      # constructors and builders
    return "action"


def _finish(frame) -> None:
    """A timed call returned: record its inclusive time and its own (self) time."""
    st = getattr(_tls, "stack", None)
    if not st:
        return
    i = len(st) - 1
    while i >= 0 and st[i][0] is not frame:
        i -= 1
    if i < 0:
        return
    rec = st[i]
    del st[i:]
    inclusive = time.perf_counter() - rec[1]
    if st:
        st[-1][2] += inclusive              # the parent was busy in this call, not in itself
    _, _, children, run, mod, func, role, ev = rec
    cur = run.funcs.setdefault((mod, func, role), [0, 0.0])
    cur[0] += 1
    cur[1] += max(0.0, inclusive - children)
    if ev is not None:
        ev["ms"] = inclusive * 1000


def on_event(frame, event, arg):
    code = frame.f_code
    callee = modules.module_of(code.co_filename)   # cached, so library code costs one lookup
    if callee is None or code.co_name.startswith("<"):
        return   # not project code; lambdas and comprehensions count under their function
    if event == "return":
        try:
            _finish(frame)
        except Exception:
            pass
        if getattr(_tls, "frame", None) is frame:       # the entry call finished
            _tls.frame = None
            _tls.role = None
        return
    if event != "call":
        return
    try:
        run = ACTIVE
        if run is None:
            return
        back = frame.f_back
        while back and back.f_code.co_name.startswith("<") and back.f_code.co_name != "<module>":
            back = back.f_back
        caller = modules.module_of(back.f_code.co_filename) if back else None
        caller_func = back.f_code.co_name if caller else None

        role = getattr(_tls, "role", None)
        if role is None:
            if caller is None:                          # entry into project code from outside
                role = role_for(code.co_name)
                _tls.role, _tls.frame = role, frame
            else:
                role = "setup" if PHASE in ("setup", "teardown") else "action"

        ev = None
        if caller == callee:
            k = (callee, caller_func, code.co_name, role)
            run.internal[k] = run.internal.get(k, 0) + 1
        else:
            ev = {"from": caller or "entry", "from_func": caller_func, "to": callee,
                  "func": code.co_name, "role": role}
            run.events.append(ev)
        st = _tls.__dict__.setdefault("stack", [])
        st.append([frame, time.perf_counter(), 0.0, run, callee, code.co_name, role, ev])
    except Exception:
        pass  # a failing profile hook would be removed by Python; never let that happen


def install() -> None:
    """Hook this thread and every thread started afterwards."""
    threading.setprofile(on_event)
    sys.setprofile(on_event)
