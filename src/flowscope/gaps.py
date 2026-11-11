"""What has no test: the project's public functions, entry points first.

This reads the source, it does not run anything, so it works on a project with no tests.
When there are tests, a function that the tests ran is left out.
"""
from __future__ import annotations

import ast
from pathlib import Path

# Decorators that register a function as something the outside world calls:
# Flask and FastAPI routes, click commands, task queues.
ENTRY_DECORATORS = {"route", "get", "post", "put", "delete", "patch", "command", "group",
                    "task", "websocket"}
TOP = 25


def _is_entry(node: ast.AST) -> bool:
    if node.name == "main":
        return True
    for d in node.decorator_list:
        target = d.func if isinstance(d, ast.Call) else d
        if isinstance(target, ast.Attribute) and target.attr in ENTRY_DECORATORS:
            return True
    return False


def _public(name: str) -> bool:
    return not name.startswith("_")


def scan_file(path: Path, module: str, root: Path) -> list:
    """The public functions and methods defined at the top of one file."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return []
    found = []

    def add(node, qual):
        found.append({"module": module, "name": node.name, "qual": qual,
                      "where": f"{path.relative_to(root)}:{node.lineno}",
                      "entry": _is_entry(node), "size": node.end_lineno - node.lineno + 1})

    funcs = (ast.FunctionDef, ast.AsyncFunctionDef)
    for node in tree.body:
        if isinstance(node, funcs) and _public(node.name):
            add(node, node.name)
        elif isinstance(node, ast.ClassDef) and _public(node.name):
            for sub in node.body:
                if isinstance(sub, funcs) and _public(sub.name):
                    add(sub, f"{node.name}.{sub.name}")
    return found


def scan(root: Path, names: dict) -> list:
    """names maps an absolute filename to its module name (from modules.ModuleMap)."""
    from . import jsbackend, modules
    if modules.is_js_project(root):
        return jsbackend.scan(root, names)
    items = []
    for filename, module in sorted(names.items()):
        if module:
            items += scan_file(Path(filename), module, root)
    return items


def rank(items: list) -> list:
    """Entry points first, then the biggest functions: they hold the most behaviour."""
    return sorted(items, key=lambda i: (not i["entry"], -i["size"], i["module"], i["name"]))


def render(items: list, tested: set | None, n_tests: int) -> str:
    """tested is a set of (module, function name) the tests ran, or None when there are no tests."""
    if not items:
        return "No public functions found."
    todo = rank([i for i in items if tested is None or (i["module"], i["name"]) not in tested])
    if tested is None:
        head = f"No tests. {len(items)} public functions. Start with the entry points:"
    elif not todo:
        return f"Every one of the {len(items)} public functions is run by at least one of the {n_tests} tests."
    else:
        head = (f"{len(todo)} of {len(items)} public functions are not run by any of the {n_tests} tests. "
                "Biggest first, entry points on top:")
    out = [head]
    for i in todo[:TOP]:
        tag = "entry" if i["entry"] else "     "
        out.append(f"  {tag}  {i['module']}.{i['qual']}   {i['where']}  ({i['size']} lines)")
    if len(todo) > TOP:
        out.append(f"  ... and {len(todo) - TOP} more")
    out.append("A function with the same name in two classes counts as run if either one ran.")
    return "\n".join(out)
