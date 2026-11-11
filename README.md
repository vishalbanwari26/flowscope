# flowscope

**`/explain`: turn your project's tests into a one-page explanation of how the system works.**

Run it in a Python project. It runs your tests with a tracer attached, sees which parts of the
code each one uses and where the time goes, and writes one HTML page you can mail, open offline
or print to PDF. Pick who it is for:

| Command | For | The page adds |
|---|---|---|
| `/explain` | Stakeholders who do not read code | Plain sentences about what the system does, a diagram, where it is slow, what no test covers, points to raise |
| `/explain learn` | An engineer learning the system (a new hire, or you after an AI wrote most of it) | What lives where, with each module's busiest functions and who calls it, and a reading order |
| `/explain interview` | You, presenting your own project | A two-minute architecture overview, the use cases to walk through, and talking points |

![The explain page for the shop example: a two-paragraph summary, five use cases with sentences about which parts they use, a diagram of how the parts call each other, a bar chart where catalog.price_of takes 100% of the time, and sections for what no test covers and what fails](assets/brief.png)

The sample page for [`examples/shop`](examples/shop) is [`assets/brief-example.html`](assets/brief-example.html).
Download it and open it in a browser.

**What it can and cannot tell you.** The tests show what ran, in what order, and for how long.
They do not show why you built it that way. For `learn` and `interview`, `/explain` asks you
three short questions about the why and puts your answers in your words. It does not invent
trade-offs or scale numbers. The numbers on the page come from the tests. The sentences are
Claude's reading of them, so read the page before you send it or present it.

Status: early. Tried on five Python projects, tested on Python 3.12 only.

## Install

```bash
claude plugin marketplace add vishalbanwari26/flowscope
claude plugin install flowscope@flowscope
```

Then run `/explain` inside a Python project that has pytest tests. No tests? `/addtests` writes
some, one use case at a time.

Without Claude Code:

```bash
cd your-project
/path/to/flowscope/bin/flow brief --for interview --summary "..." --notes "- first point"
```

`flow brief` writes `explain-output/explain.html`. `--out` moves it. Add `explain-output/` to
`.gitignore`. `--summary` and `--notes` take text or `@file`; note lines starting `- ` become a list.

## The engineer's tools

`/explain` is built from these. Each answers one question and works on its own.

### Trace one test

The example is [`examples/shop`](examples/shop): a tiny checkout with four modules and five tests.
One call, `catalog.price_of`, pretends to be a database lookup and is slow. The three commands
below find it without anyone reading the code.

![Terminal: flow hld lists the shop's modules, flow run shows one test's call tree, flow bottleneck shows catalog.price_of taking about 100% of the time](assets/demo-cli.gif)

The viewer shows the same test. Each module's share of the time is a chip, and the call tree
shows which call made which.

![The viewer with the test "small order gets a receipt" selected: catalog takes 99% of the time, and the call tree shows orders.place calling stock.reserve, pricing.total and mailer.receipt](assets/viewer-flow.png)

Click a chip to see the functions inside that module.

![The viewer after clicking the catalog chip: one function, price_of, called once, 99% of the time](assets/viewer-module.png)

Under the call tree there is a graph of the busiest modules, closed by default because it gets
crowded on big projects. Each arrow is one module calling another. `entry` is the test itself.
The darker the box, the bigger its share of the time.

![The module graph for the same test: entry calls orders, orders calls stock, pricing and mailer, pricing calls catalog, which is shaded dark for 99% of the time](assets/viewer-graph.png)

Try it yourself:

```bash
cd examples/shop
../../bin/flow hld
../../bin/flow run "small order"
../../bin/flow bottleneck
```

### The commands

In a Python project that has pytest tests:

| Command | It answers | You get |
|---|---|---|
| `/hld` | What is this project made of? Which modules do the tests reach? | A ranked list of modules and the main links between them |
| `/lld <module>` | What runs inside this module? | The functions that ran, how often, and who called them |
| `/flow <test>` | What does this test run? | A short call tree with time shares |
| `/scope <name>` | Which tests reach this module or function? | A list of tests, with pass or fail |
| `/debug [test]` | Why does it fail? | The error, and the last calls before it stopped. With no test, every failing test and its reason |
| `/findbottleneck [test]` | Where does the time go? | The functions that take most of it, or one test's heaviest path |
| `/addtests [target]` | There are no tests, or this part has none | Claude writes one small test per use case, entry points first, and shows each one's flow |
| `/flowscope` | Show me | Opens the viewer in your browser |

`/hld`, `/lld`, `/scope`, `/debug` and `/findbottleneck` with no test need every test run once.
The first one does that and says so. The result is saved, so the next one is instant. It is
rebuilt when you edit a Python file.

Nothing is installed in your project. flowscope runs with the project's own Python (`.venv`,
`venv`, a uv project, or `python3`) and is read from the plugin folder. To use a different
Python, set `FLOWSCOPE_PYTHON`. The launcher is a bash script, so macOS and Linux.

### Use them without Claude Code

```bash
cd your-project
/path/to/flowscope/bin/flow                    # open the viewer
/path/to/flowscope/bin/flow hld                # the same commands, without the slash
/path/to/flowscope/bin/flow run "some test"
```

Or install it into the project's environment and call `flowscope` directly:

```bash
pip install /path/to/flowscope
flowscope serve | list | run | hld | lld | scope | debug | bottleneck | gaps | brief
```

`flowscope run "some test" --depth 5` prints more levels. `--setup` includes setup calls.
`--fresh` on the project-wide commands ignores the saved result.

### The viewer

Pick a test on the left. On the right, from top to bottom:

- **Where the time goes.** A few chips, one per busy module, shaded by its share of the time.
  Click one to see the functions inside it.
- **What it calls.** A tree: each call sits under the call that made it. Repeated calls are
  merged ("x15"). Only the branches that hold the time are open; click the rest.
- **A graph** of the busiest modules, closed by default.

## How it decides what is setup

A test spends most of its calls building data. Those are hidden by default, so you see what the
test is about. It judges by the function called, not by who called it, because a test helper
often builds data and runs the code under test in the same function.

| The call is | Counts as |
|---|---|
| made during a pytest fixture | setup |
| a constructor (`__init__`) | setup |
| named like a builder: `add_*`, `set_*`, `seed*`, `generate*`, `create*`, `build*`, `make*`, `load*`, `reset*`, `insert*`, `populate*`, `register*`, `init*` | setup |
| anything else the test calls | action |
| made by a function that setup or action already called | the same as that function |

This is a guess. When it would hide every call a test makes, flowscope shows them instead and
says so: the test is probably about a constructor or a loader. "With setup" shows everything.

## About the times

The tracer runs on every function call, so it slows the code. On the one project where this was
measured, tests ran 1.3 to 4.3 times slower with tracing on, median 2.6. Functions that make many
calls look a little slower than they are. The first call in a test is also slower (start-up).
Read the times as shares of the total, not as real milliseconds.

A function's own time includes waiting on anything it calls outside the project: the disk, the
network, another program. A big share is a place to look, not proof of a problem.

## Safety

- **It runs your tests, in place.** A test that writes files will write them. Start from a clean
  git tree and check `git status` afterwards.
- **Localhost only.** The viewer's server listens on 127.0.0.1, checks the Host header, and needs
  the random token in the URL it prints. Without that, any web page open in your browser could ask
  it to run tests.
- It never sends anything over the network. The saved result is in `~/.cache/flowscope`
  (set `FLOWSCOPE_CACHE` to move it) and holds test and function names and timings.

## Limits

- `/explain` describes what the tests run. It does not know your design decisions, load or scale, or code no test runs. Do not present the page as a full architecture review.
- Python and pytest only. A project with no tests has no use cases: `/addtests` helps write some.
- `gaps` (behind `/addtests`) reads the source. It lists top-level functions and class methods, not nested ones.
- A module is a file. Two files with the same name get a longer name.
- Function level, not line level.
- It only shows what the tests run. "No test reaches it" means untested, not unused.
- Code that runs in other processes is not seen.
- The viewer runs every test in one server process, so module state carries over between runs. A test that relies on leftover state (a counter, a cache) can pass the first time and fail the second. `flow run` starts a fresh process each time.
- Calls made by library code that the project's own functions never touch are not shown.

## Develop

```bash
uv venv && uv pip install -e . pytest
.venv/bin/python -m pytest
```

If `import flowscope` fails on macOS after an editable install, the venv's `.pth` files may have
the macOS `hidden` flag, which Python skips. `chflags -R nohidden .venv` clears it. The tests do
not depend on the editable install.

## License

MIT
