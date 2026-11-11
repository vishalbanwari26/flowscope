# flowscope

**Run `/explain` in a Python or JavaScript/TypeScript project. Get a one-page explanation of how it works, made from your tests.**

It runs your tests with a tracer, sees which parts of the code each one uses and where the time
goes, and writes one HTML page you can open offline, mail or print to PDF.

![Terminal: flow hld lists the modules of a real project, flow brief writes the page. Then the page scrolls: an architecture diagram, a call sequence, and written sections with file and line references](assets/demo-explain.gif)

The demo ran on a real project with 63 tests (Mnemos, an agent-memory framework). The page is the
`learn` kind. Inside Claude Code, `/explain learn` runs these steps and writes the text for you.

## Use it

```bash
claude plugin marketplace add vishalbanwari26/flowscope
claude plugin install flowscope@flowscope
```

Other agents (Codex, Cursor, Gemini CLI and others that read skills): install the CLI into your
project's Python environment, then add the skills.

```bash
pip install git+https://github.com/vishalbanwari26/flowscope
npx skills add vishalbanwari26/flowscope
```

The skills are `explain` and `addtests`. Ask your agent to "explain this project for an interview".
(I have not run `npx skills add` myself yet.)

Then, inside a project that has pytest tests (Python) or Jest or Vitest tests (JavaScript or TypeScript):

| Type | For | You get |
|---|---|---|
| `/explain` | people who do not read code | what the system does, where it is slow, what no test covers |
| `/explain learn` | an engineer learning the system | architecture, request flow, where state lives, a reading order |
| `/explain interview` | presenting your own project | components, design decisions, bottlenecks, questions to expect |

No tests? `/addtests` writes some first.

## Examples

Made from the five tests in [`examples/shop`](examples/shop). Open them in your browser:

- [stakeholders.html](https://vishalbanwari.tech/flowscope/examples/shop/explain-output/stakeholders.html)
- [learn.html](https://vishalbanwari.tech/flowscope/examples/shop/explain-output/learn.html)
- [interview.html](https://vishalbanwari.tech/flowscope/examples/shop/explain-output/interview.html)

## What to know

- The tests show what ran and for how long. They do not show why you built it that way. For `learn`
  and `interview`, `/explain` reads your code, cites `file:line`, marks guesses `(inferred)`, and
  asks you the "why" questions. Read the page before you send it.
- It runs your tests in place. Start from a clean git tree.
- Nothing leaves your machine.
- Python (pytest) and JavaScript/TypeScript (Jest or Vitest). Early: Python was tried on five projects
  (3.12). JavaScript/TypeScript is new: it was tried on two small examples
  ([Jest](examples/jsshop), [Vitest](examples/tsshop-vitest)) and one real Vitest project with 121 tests.
  It needs `npm install` done, and for Jest a Babel setup. For JavaScript the per-test view
  (`/flow`, the viewer) is not there yet, and `/addtests` writes pytest tests only.

More: [every command, the viewer, and how it works](docs/reference.md).

MIT
