# flowscope

Pick a test. See which parts of your code it runs, in what order, and where the time goes.

When an AI writes much of your code, you can end up with a project whose tests pass and
whose flow you cannot explain. flowscope turns each test into a use case you can click.
It runs that test with a tracer attached and shows the calls as a map of your modules.

Status: early. It has been tried on two small Python projects, tested on Python 3.12 only.

## What you get

- **Use cases from your tests.** Every pytest test is a use case, named after the test.
- **A flow map.** Modules are boxes. A line lights up where a call crosses from one module
  to another. The calls replay one step at a time so you can follow them.
- **Inside a module.** Click a box to see the functions that ran inside it.
- **Setup and action, separated.** A test spends most of its calls building data. Those are
  hidden by default, so you see what the test is actually about. A toggle shows them.
- **Time.** Each module and function shows its share of the time. Darker means more.
- **A text version.** `flowscope run` prints the same flow in the terminal, which is what you
  want inside a terminal session with no browser.

## Install

Run flowscope with the project's own Python. The tests have to import the project's
dependencies, so flowscope must live in the same environment.

```bash
# inside the project, with its virtual environment active
pip install /path/to/flowscope
```

With uv, without installing anything permanently:

```bash
uv run --with /path/to/flowscope flowscope serve
```

It is not on PyPI yet.

### As a Claude Code plugin

The repository is also a Claude Code plugin. It adds a `/flow` command and a skill that
tells Claude how to run flowscope on a project safely.

```bash
claude plugin marketplace add /path/to/flowscope
claude plugin install flowscope@flowscope
```

To try it for one session without installing: `claude --plugin-dir /path/to/flowscope`.

## Use

```bash
flowscope serve            # open the viewer for the project in the current folder
flowscope list             # list the use cases
flowscope run "ambiguous"  # run one and print its flow; --setup shows setup calls, --json the raw data
```

`serve` prints a URL with a random token. Open that URL.

## How it decides what is setup

It judges by the function called, not by who called it. A test helper often builds data
and runs the code under test in the same function, so the caller tells you nothing.

| The call is | Counts as |
|---|---|
| made during a pytest fixture | setup |
| a constructor (`__init__`) | setup |
| named like a builder: `add_*`, `set_*`, `seed*`, `generate*`, `create*`, `build*`, `make*`, `load*`, `reset*`, `insert*`, `populate*`, `register*`, `init*` | setup |
| anything else the test calls | action |
| made by a function that setup or action already called | the same as that function |

This is a guess and it can be wrong. If a test is about a loader, the loader is filed as
setup. Use the "With setup" toggle when the map looks too thin.

## About the times

The tracer runs on every function call, so it slows the code. On the one project where this
was measured, tests ran 1.3 to 4.3 times slower with tracing on, median 2.6. Functions that
make many calls look a little slower than they are. Read the times as shares of the total,
not as real milliseconds.

## Safety

- **It runs your tests, in place.** A test that writes files will write them. Start from a
  clean git tree and check `git status` afterwards.
- **Localhost only.** The server listens on 127.0.0.1, checks the Host header, and needs the
  token printed at startup. Without that, any web page open in your browser could ask it to
  run tests.
- It never sends anything over the network.

## Limits

- Python and pytest only.
- A module is a file. Two files with the same name get a longer name.
- Function level, not line level. A function with no calls inside it shows as one box.
- It only shows what the tests run. A module no test touches is listed as not touched.
- Code that runs in other processes is not seen.

## Develop

```bash
uv venv && uv pip install -e . pytest
.venv/bin/python -m pytest
```

## License

MIT
