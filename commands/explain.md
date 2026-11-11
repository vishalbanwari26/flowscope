---
description: Explain this system on one page, for stakeholders, for learning it, or for an interview
argument-hint: "[stakeholders | learn | interview]"
---

Make a one-page explanation of this project. The reader is `$ARGUMENTS` (if I gave nothing, use stakeholders: people who do not read code).

First, from the project folder, run `${CLAUDE_PLUGIN_ROOT}/bin/flow hld`, `${CLAUDE_PLUGIN_ROOT}/bin/flow bottleneck`, `${CLAUDE_PLUGIN_ROOT}/bin/flow debug` and `${CLAUDE_PLUGIN_ROOT}/bin/flow gaps`. The first may run every test once. If the project has no tests, stop and offer `/addtests`.

Then write two things from what they printed, and nothing else:

- **summary**: two short paragraphs. What the system does, in terms of the use case names. Then what stands out: where the time goes, what fails, what no test covers.
- **notes**: a list of lines that each start with `- `.

How they differ by reader:

- **stakeholders**: plain words, no module names unless needed, what users or the business get. Notes are "Points to raise": one line each on risk, slow spots, untested areas. Say "untested", never "broken".
- **learn** (an engineer learning this system): name the modules and what each one is for. Notes are "Where to start reading": a reading order of five to eight modules or functions, entry points first, one line on why each.
- **interview** (the engineer will present this project): summary reads as a two-minute architecture overview. Notes are "Talking points": the flow of the main use case, the slowest part and what you would do about it, what is not tested and why that matters.

Rules that matter more than style:

1. The tests show what ran, not why it was built that way. Do not invent reasons, trade-offs, scale numbers or alternatives that were not considered. For learn and interview, before you write the notes, ask me up to three short questions about why: why this split into modules, what the main trade-off was, what I would change. Put my answers in the notes in my words. If I skip a question, write it into the notes as `- Question to answer yourself: ...`.
2. Use only the command output and my answers. Quote shares, not milliseconds.
3. Never say the system is correct or safe because the tests pass.

Save the summary and the notes to files in `explain-output/` (`summary.txt`, `notes.txt`), then run:

`${CLAUDE_PLUGIN_ROOT}/bin/flow brief --for <reader> --summary @explain-output/summary.txt --notes @explain-output/notes.txt`

It writes `explain-output/explain.html`. Tell me the path and show me the summary and notes so I can read them before I use or send the page. Point out anything I should check first. Suggest adding `explain-output/` to `.gitignore` if it is not already there.
