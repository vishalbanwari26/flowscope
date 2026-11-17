# Behavior diff on every pull request

Add this to `.github/workflows/behavior-diff.yml`. It runs your tests at the base and at the pull request,
then comments with what changed in how the system behaves, and keeps the side-by-side page as an artifact.

```yaml
name: behavior diff
on: pull_request
permissions:
  contents: read
  pull-requests: write
jobs:
  diff:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0              # the base commit has to be there
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -e . pytest   # install your project and its test dependencies the way you always do
      - uses: vishalbanwari26/flowscope@main
```

For a JavaScript or TypeScript project, set up Node and run `npm ci` instead, and use Jest or Vitest as usual.

- The comment is updated in place on every push, not repeated.
- Inputs: `base` (default: the pull request's base branch), `comment` (`false` to only keep the page),
  `flowscope` (what to `pip install`, default the version that comes with the action).
- A pull request from a fork has a read-only token, so the comment is skipped. The page is still an artifact.
- It runs every test twice (once at the base, once now), so it adds the length of your test suite to the check.
  The Flask suite (490 tests) takes about four minutes per side with tracing on.
- This has not been run on a GitHub runner yet. Run `flow changes <base>` locally first to see the result.
