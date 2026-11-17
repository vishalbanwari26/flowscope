"""The behavior diff: `flowscope changes` on a small git repository that is changed after a commit."""
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from flowscope import changes

ROOT = Path(__file__).resolve().parent.parent
SRC = str(ROOT / "src")
GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@t"]


def run(cwd, *cmd):
    return subprocess.run(list(cmd), cwd=cwd, capture_output=True, text=True, check=True).stdout


def flowscope(cwd, cache, *args):
    env = {**os.environ, "PYTHONPATH": SRC, "FLOWSCOPE_CACHE": str(cache)}
    return subprocess.run([sys.executable, "-m", "flowscope", *args], cwd=cwd, env=env, capture_output=True, text=True)


@pytest.fixture
def shop(tmp_path):
    """A copy of the example shop, committed. Tests change it afterwards."""
    proj = tmp_path / "shop"
    shutil.copytree(ROOT / "examples" / "shop", proj, ignore=shutil.ignore_patterns("explain-output", "__pycache__"))
    run(proj, "git", "init", "-q")
    run(proj, "git", "add", "-A")
    run(proj, *GIT, "commit", "-qm", "base")
    return proj


def test_an_unchanged_project_has_no_behavior_change(shop, tmp_path):
    r = flowscope(shop, tmp_path / "c", "changes", "HEAD", "--text")
    assert r.returncode == 0, r.stderr
    assert "No behavior changed." in r.stdout
    assert "only one commit" in flowscope(shop, tmp_path / "c", "changes").stderr


def test_new_call_extra_lookups_and_untested_function_are_found(shop, tmp_path):
    (shop / "audit.py").write_text("LOG = []\n\n\ndef record(event, detail):\n    LOG.append((event, detail))\n")
    orders = (shop / "orders.py").read_text()
    (shop / "orders.py").write_text(orders.replace("import mailer\n", "import audit\nimport mailer\n")
                                    .replace("    order_id = next(_ids)\n", "    order_id = next(_ids)\n    audit.record('order', order_id)\n"))
    pricing = (shop / "pricing.py").read_text()
    (shop / "pricing.py").write_text(pricing.replace("for item, qty in cart.items())",
                                                     "for item, qty in cart.items() if price_of(item) is not None)")
                                     + "\n\ndef apply_coupon(total, code):\n    return total - 500 if code == 'SAVE5' else total\n")
    r = flowscope(shop, tmp_path / "c", "changes", "--text")
    assert r.returncode == 0, r.stderr
    out = r.stdout
    assert "orders now calls audit, and did not before" in out
    assert "pricing.apply_coupon changed and no test runs it" in out        # changed, no test runs it
    assert "catalog.price_of 3x → 6x" in out                               # the lookup now runs twice per item
    assert "now calls audit.record" in out
    page = flowscope(shop, tmp_path / "c", "changes")
    html = (shop / "explain-output" / "changes.html").read_text()
    assert page.returncode == 0 and "Read these first" in html and 'class="c add"' in html


def test_a_test_that_starts_failing_is_called_broke(shop, tmp_path):
    p = (shop / "stock.py").read_text()
    (shop / "stock.py").write_text(p.replace("if STOCK.get(item, 0) < qty:", "if STOCK.get(item, 0) < qty - 1000:"))
    r = flowscope(shop, tmp_path / "c", "changes", "--text")
    assert "BROKE" in r.stdout and "order for more than is in stock is refused" in r.stdout


def test_markdown_comment_is_short_and_leads_with_the_verdict(shop, tmp_path):
    (shop / "mailer.py").write_text('def receipt(order_id, amount):\n    return f"Order {order_id}"\n')
    r = flowscope(shop, tmp_path / "c", "changes", "--md")
    assert r.stdout.startswith("**Behavior diff**")


def test_changed_lines_are_read_from_git(shop):
    p = (shop / "pricing.py").read_text().splitlines()
    p[7] = "    return 20 if sum(cart.values()) >= 10 else 0"
    (shop / "pricing.py").write_text("\n".join(p) + "\n")
    top, _ = changes.locate(shop)
    got = changes.changed_lines(top, changes.resolve_base(top, "HEAD"))
    assert got["pricing.py"] == [(8, 8)]


def test_alignment_marks_added_removed_and_counted_calls():
    a = [["entry", "o", "place", 0, 1], ["o", "s", "reserve", 1, 1], ["o", "p", "total", 1, 3]]
    b = [["entry", "o", "place", 0, 1], ["o", "s", "reserve", 1, 1], ["o", "a", "log", 1, 1], ["o", "p", "total", 1, 5]]
    kinds = [k for _, _, k in changes.align(a, b)]
    assert kinds == ["same", "same", "add", "count"]


def _t(tid, name, seq, funcs=()):
    return {"id": tid, "name": name, "file": "t.py", "outcome": "passed", "seq": seq, "output": "",
            "funcs": [list(f) for f in funcs], "mods": [], "edges": [], "callers": []}


def test_calls_inside_one_module_are_counted_and_a_rewritten_test_is_matched():
    seq = [["entry", "a", "run", 0], ["a", "b", "go", 1]]
    before = _t("t.py::old", "old name", seq, [("b", "step", "call", 11, 1.0)])
    after = _t("t.py::new", "new name", seq, [("b", "step", "call", 10, 1.0)])
    base = {"data": {"project": "p", "modules": [], "tests": [before]}, "items": []}
    head = {"data": {"project": "p", "modules": [], "tests": [after]}, "items": []}
    r = changes.diff(base, head, {}, Path("."))
    assert len(r["cases"]) == 1                                   # matched, not one removed and one new
    c = r["cases"][0]
    assert c["status"] == "changed" and c["name"] == "new name"
    assert c["inside"] == [("b", "step", 11, 10)] and "renamed from: old name" in c["phrases"]
