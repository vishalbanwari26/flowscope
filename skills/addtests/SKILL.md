---
name: addtests
description: Write small pytest tests for Python code that has none, one use case at a time, entry points first, so the project has use cases to trace and explain. Use when a project has no tests or a part is untested.
---

# Add tests for untested code

## Setup

Run `flowscope --version` from the project folder. If it is not found, stop and tell me to install flowscope into the project's own Python environment (it must see the project's test dependencies); the steps are in the README at github.com/vishalbanwari26/flowscope. Do not install it yourself.

It runs the project's tests in place and sends nothing over the network. Python and pytest projects only.

Run `flowscope gaps` from the project folder. It lists the public functions no test runs, entry points first (`main`, routes, CLI commands). If I named a module or function, work on that. Otherwise start with the top entry point.

Write the tests like this:

1. Read the function and what it calls. Pick one thing a user does with it, such as one request, one command, or one call with ordinary input. That is one use case.
2. Write one small pytest test for it, named for what the user does (`test_creating_an_order_rejects_empty_cart`), not for the function.
3. Run it. If it passes, check that it can fail: change an expected value, see it fail, change it back. A test that cannot fail shows nothing.
4. Assert the behavior you can see in the code, the docstring, or the README. If you can only see what the code happens to do today, say so in a comment on the test: `# records current behavior, not confirmed as intended`.
5. Use real inputs. Mock only the network, the clock, and other programs. Do not mock the project's own modules, because the point is to see them run.

Do one use case at a time. After each one, run `flowscope run "<test name>"` and show me the flow, so I see the new test doing its job. Then ask whether to continue with the next entry point.

Do not touch the project's source code. If a function cannot be tested without changing it, say so and stop on that one.
