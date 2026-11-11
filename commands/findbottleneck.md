---
description: Where the time goes, across all tests or in one test
argument-hint: "[test name]"
---

Run `${CLAUDE_PLUGIN_ROOT}/bin/flow bottleneck $ARGUMENTS` from the project folder. With no test name it ranks the functions where all the tests spend their time.

Show me the output, then say in two or three plain sentences where the time goes. Quote shares, not milliseconds: tracing slows the code. A function's own time includes waiting on the disk, the network or another program, so call a big share a place to look, not a proven problem.
