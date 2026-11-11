# flowscope

Pick a test. See how the code flows through your modules, and where the time goes.

When an AI writes much of your code, you can end up with a project whose tests pass and
whose flow you cannot explain. flowscope turns each test into a use case you can click. It
runs that test with a tracer attached and shows the calls as a map of your modules.

Status: early. Tried on two small Python projects, tested on Python 3.12 only.

## Use it in Claude Code

```bash
claude plugin marketplace add /path/to/flowscope
claude plugin install flowscope@flowscope
```

Then, in a Python project that has pytest tests:

- `/flow` opens the viewer in your browser.
- `/flow some test name` prints that test's flow, and Claude explains it.

Nothing is installed in your project. flowscope runs with the project's own Python
(`.venv`, `venv`, a uv project, or `python3`) and is read from the plugin folder. To use a
different Python, set `FLOWSCOPE_PYTHON`. The launcher is a bash script, so macOS and Linux.

## Use it without Claude Code

```bash
cd your-project
/path/to/flowscope/bin/flow                  # open the viewer
/path/to/flowscope/bin/flow some test name   # print one flow
```

Or install it into the project's environment and use the full command line:

```bash
pip install /path/to/flowscope
flowscope serve             # the viewer
flowscope list              # the use cases
flowscope run "some test"   # one flow as text; --setup shows setup calls, --json the raw data
```

## What you see

- **Use cases from your tests.** Every pytest test is a use case, named after the test.
- **A flow map.** Modules are boxes. A line lights up where a call crosses from one module
  into another. The calls replay one step at a time.
- **Inside a module.** Click a box to see the functions that ran inside it.
- **Setup and action, separated.** A test spends most of its calls building data. Those are
  hidden by default so you see what the test is about. A toggle shows them.
- **Time.** Each module and function shows its share of the time. Darker means more.

## How it decides what is setup

It judges by the function called, not by who called it. A test helper often builds data and
runs the code under test in the same function, so the caller tells you nothing.

| The call is | Counts as |
|---|---|
| made during a pytest fixture | setup |
| a constructor (`__init__`) | setup |
| named like a builder: `add_*`, `set_*`, `seed*`, `generate*`, `create*`, `build*`, `make*`, `load*`, `reset*`, `insert*`, `populate*`, `register*`, `init*` | setup |
| anything else the test calls | action |
| made by a function that setup or action already called | the same as that function |

This is a guess and it can be wrong. If a test is about a loader, the loader is filed as
setup. Use "With setup" when the map looks too thin.

## About the times

The tracer runs on every function call, so it slows the code. On the one project where this
was measured, tests ran 1.3 to 4.3 times slower with tracing on, median 2.6. Functions that
make many calls look a little slower than they are. Read the times as shares of the total,
not as real milliseconds.

## Safety

- **It runs your tests, in place.** A test that writes files will write them. Start from a
  clean git tree and check `git status` afterwards.
- **Localhost only.** The server listens on 127.0.0.1, checks the Host header, and needs the
  random token in the URL it prints. Without that, any web page open in your browser could
  ask it to run tests.
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

If `import flowscope` fails on macOS after an editable install, the venv's `.pth` files may
have the macOS `hidden` flag, which Python skips. `chflags -R nohidden .venv` clears it.

## License

MIT
