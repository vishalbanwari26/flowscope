---
description: See how a test's code flows through the project, with timing
argument-hint: "[test name]"
---

Run `${CLAUDE_PLUGIN_ROOT}/bin/flow $ARGUMENTS` from the project folder. It runs the project's tests.

- No test name: it opens the viewer in the browser. Run it in the background, then tell me it is open.
- With a test name: it prints that test's flow. Explain it in plain words, using only what it printed. Quote time as shares, not milliseconds: tracing slows the code.

If it fails, show me its message.
