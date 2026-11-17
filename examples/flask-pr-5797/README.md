# Behavior diff of a real pull request

[pallets/flask#5797](https://github.com/pallets/flask/pull/5797), "push preserved contexts in correct order":
3 files changed. flowscope ran Flask's 490 tests at the parent commit and at the merge commit
(Python 3.12, pytest 8.4, Flask's tests as they were at that commit; one test fails in both runs, for a Werkzeug version reason).

Open [changes.html](changes.html). It shows 14 behaviors that changed and 475 that did not. The clearest one:
`session transactions` calls `ctx.push` 10 times where it called it 11 times.

Made with: `flow changes HEAD~1` in a checkout of the merge commit. Nothing from Flask's code is in the page,
only the names of its modules and functions and how often the tests called them. The page says what the tests ran.
It does not say whether the pull request is right.
