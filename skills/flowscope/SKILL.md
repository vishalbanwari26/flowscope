---
name: flowscope
description: Show how a Python project's code flows for each test, module by module, with timing. Use when the user wants to understand how code they did not write (or an AI wrote) works, what a test really exercises, which modules a use case touches, or where the time goes in a test.
---

# flowscope

flowscope runs one pytest test with a tracer attached and reports which project modules and
functions ran, in what order, and how the time split. Each test is a "use case".

It works on Python projects with pytest tests. It runs the tests in the user's own
environment, because the tests have to import the project's dependencies.

## Before you run anything

1. **Find the project root and its Python.** The root is the folder with the tests. Look for
   `.venv/` or `venv/`, or a `uv.lock` (use `uv run`). If you cannot tell which environment
   the project uses, ask the user. Do not use the system Python.
2. **Tell the user it runs their tests in place.** A test that writes files will write them.
   Run `git status --short` first and remember the result. If the tree is not clean, say so
   before you run.
3. **Check whether flowscope is installed in that environment:**
   `<python> -m flowscope --version`. If it is missing, ask before installing it. The source
   is this plugin's folder, which is two levels above this skill's folder (the one that
   contains `.claude-plugin/`).
   - uv project: `uv run --with <plugin folder> flowscope ...` needs no install.
   - Otherwise: `<python> -m pip install <plugin folder>`.

## Run it

Pick the form that fits where you are.

**Text, works anywhere including a terminal with no browser:**

```bash
<python> -m flowscope list <root>                # all use cases
<python> -m flowscope run "<part of a name>" <root>
```

Add `--setup` to include setup calls. If several tests match, it lists them: pick one.

**Browser, when the user wants to click around:**

```bash
<python> -m flowscope serve <root> --no-open     # run in the background
```

It prints a URL with a token. Open it with a browser tool if you have one, or give the URL
to the user. Stop the server when you are done.

## Read the result

- Each step is a call that crossed from one module into another. `entry` is the test itself.
- "Setup hidden" lines are calls that build the test's data. They are hidden because they are
  usually not what the test is about. flowscope guesses setup from the function name
  (`__init__`, `add_*`, `generate*`, `load*`, and similar), so check it when the map looks
  too thin, and use `--setup` to see everything.
- "Own time by module" is each module's share of the time, not counting the functions it calls.
  Times are measured with tracing on, which slows the code several times over. Report shares,
  never milliseconds as if they were real.
- "Inside <module>" lists calls between functions of the same module.

## After you run it

Run `git status --short` again and tell the user if anything changed. Then explain the flow in
plain words, using only what flowscope recorded.

## Do not

- Say a module is unused because no test touched it. It only means no test touched it.
- Describe what a function does from its name. If you need that, read the code.
- Call a test slow or fast from these numbers.
- Run it on a project you were not asked to look at.
