---
name: explain
description: Explain a Python (pytest) or JavaScript/TypeScript (Jest or Vitest) project on one HTML page, from its tests. For stakeholders who do not read code, for an engineer learning the system, or for presenting the project in an interview. Use when asked to explain, document or present how a codebase works.
---

# Explain a project from its tests

## Setup

Run `flowscope --version` from the project folder. If it is not found, stop and tell me to install flowscope into the project's own Python environment (it must see the project's test dependencies); the steps are in the README at github.com/vishalbanwari26/flowscope. Do not install it yourself.

It runs the project's tests in place and sends nothing over the network. Works on Python (pytest) and JavaScript/TypeScript (Jest or Vitest) projects.

Make a one-page explanation of this project. The reader is whoever I name: `stakeholders` (people who do not read code, the default), `learn` (an engineer learning the system) or `interview` (I will present this project).

First, from the project folder, run `flowscope hld`, `flowscope bottleneck`, `flowscope debug` and `flowscope gaps`. The first may run every test once. If the project has no tests, stop and offer the addtests skill.

The page draws the architecture and the request flow itself, from the tests. You write two texts: a **summary** (two short paragraphs) and **notes** (the written sections). Notes use `## Heading` lines for sections, `- ` lines for bullets, and backticks for code.

## stakeholders

Plain words, no module names unless needed, what users or the business get. Summary: what the system does, then what stands out. Notes (one `## Points to raise` section): one line each on risk, slow spots, untested areas. Say "untested", never "broken". Use only the command output.

## learn (an engineer learning this system)

Read the code first: the entry points, the modules the flow output names, and any config, models or schema they use. The page already shows the diagram and a call sequence, so the notes must add what the tests cannot show. Sections, in this order:

- `## Architecture`: one paragraph. The components, what each one is responsible for, and how they are layered.
- `## How a request moves`: the main use case step by step, with the data that changes hands, citing `file:line` for each step.
- `## State and data`: where state lives (globals, files, a database, caches), what is saved, what is lost on restart.
- `## Patterns and gotchas`: patterns you can see in the code, and anything that would surprise a newcomer. Each with `file:line`.
- `## Reading order`: five to eight modules or functions, entry points first, one line on why each. End with "run `flowscope run "<test name>"` to watch it".

## interview (the engineer will present this project)

Read the code first, as for learn. The summary is a two-minute architecture overview. Sections, in this order:

- `## Components and responsibilities`: one bullet per component.
- `## Request flow, step by step`: the main use case, in words a listener can follow, citing `file:line`.
- `## Design decisions`: each decision with its reason. The reasons come from me, see rule 1.
- `## Bottlenecks and scaling`: the slowest part from the flow output, what would break first under load (from the code: shared state, locks, blocking calls, single process), and what I would change.
- `## Failure modes`: what happens on bad input, missing data or a crash, as far as the code shows, and what the tests do and do not prove.
- `## Questions to expect`: five questions an interviewer would ask about this design, each with a draft answer from the facts above. Where the answer needs my judgment, write `- Question to answer yourself: ...`.

## Rules that matter more than style

1. The tests and the code show what the system does, not why it was built that way. Do not invent reasons, trade-offs, scale numbers or alternatives that were not considered. For learn and interview, before you write the notes, ask me up to four short questions about why: why this split into parts, the main trade-off, what breaks first under load, what I would change. Put my answers in the notes in my words, marked `(your answer)`. If I skip one, write it as `- Question to answer yourself: ...`.
2. Facts about the code come from the command output or from code you read, each with `file:line`. Mark anything you inferred as `(inferred)`.
3. Quote shares, not milliseconds. Never say the system is correct or safe because the tests pass.

## Output

Save the texts to `explain-output/summary.txt` and `explain-output/notes.txt`, then run:

`flowscope brief --for <reader> --summary @explain-output/summary.txt --notes @explain-output/notes.txt`

It writes `explain-output/explain.html`. Tell me the path and show me the summary and notes so I can read them before I use or send the page. Point out what I should check first, especially anything marked `(inferred)`. Suggest adding `explain-output/` to `.gitignore` if it is not there.
