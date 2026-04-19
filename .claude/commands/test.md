Run the Briefer test suite using red-green testing discipline.

## Running tests

Always run tests with:

```bash
uv run pytest
```

For a specific file or test:

```bash
uv run pytest tests/test_foo.py
uv run pytest tests/test_foo.py::test_specific_case
```

## Red-green testing

All feature additions, changes, and bug fixes require red-green testing:

1. **Write a failing test** that captures the expected behavior
2. **Verify it fails** — run `uv run pytest` and confirm the new test is red
3. **Implement the change** to make it pass
4. **Verify it passes** — run `uv run pytest` and confirm all tests are green

Never skip the red step. A test that was never red gives no confidence it's actually testing the right thing.

## Now run the tests

Run the full test suite and report results:

```bash
uv run pytest
```
