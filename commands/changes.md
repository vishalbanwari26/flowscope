---
description: Show what a change did to the system's behavior, side by side, not to its lines
argument-hint: "[commit or branch to compare with]"
---

Show me what my change did to how the system behaves. The base is `$ARGUMENTS` (if I gave nothing: my uncommitted changes against the last commit, or the last commit against the one before it on a clean tree).

From the project folder, run `${CLAUDE_PLUGIN_ROOT}/bin/flow changes $ARGUMENTS --text`, then `${CLAUDE_PLUGIN_ROOT}/bin/flow changes $ARGUMENTS`. The first prints the summary. The second writes `explain-output/changes.html`, one page with every changed use case before and after, side by side. It runs the tests at the base commit and now, so it can take a while on a big suite.

Then tell me:

1. The headline and the "Read these first" list, as the command printed them.
2. For each item on that list, one line on what it means, from the code you read, citing `file:line`. Mark anything you inferred as `(inferred)`.
3. What I should do about changes no test runs: offer to write a test with `/addtests`.
4. For each changed behavior, ask me **why** it changed. Do not guess a reason. If I answer, add my words to the pull request text, marked `(your answer)`.

Rules: the diff shows what the tests ran, not whether the change is right. Say "no test runs it", never "broken". Do not say a change is safe because the tests pass. Show the path of the page, and suggest adding `explain-output/` to `.gitignore` if it is not there.
