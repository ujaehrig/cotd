# Phase 5 — Verify and Clean Up

## Tasks

### 5.1 Run ruff check and format

Run `uv run ruff check cotd/ tests/` and
`uv run ruff format cotd/ tests/`. Fix any issues.

AI Prompt: Run ruff check and format on the entire cotd package
and tests directory. Fix any linting or formatting errors.

### 5.2 Run ty check

Run `uv run ty check cotd/` and fix any type errors.

AI Prompt: Run ty type checker on the cotd package and fix any
errors.

### 5.3 Run full test suite

Run `uv run pytest -v` and verify all 215 tests pass.

AI Prompt: Run the full test suite and verify all tests pass.

### 5.4 Verify entry points

Test that each entry point works:

```bash
uv run cotd --help
uv run cotd-takeover --help  # (or just start/stop)
uv run cotd-tenants --help
uv run cotd-users --help
uv run cotd-vacations --help
uv run cotd-stats --help
uv run cotd-cleanup --help
uv run cotd-sync --help
```

AI Prompt: Verify that all defined entry points are callable
via uv run.

### 5.5 Verify no stale root-level Python files remain

Check that no `.py` files remain at the project root that
should have been moved.

AI Prompt: List all .py files at the project root and verify
none of them should have been moved into the cotd package.

### 5.6 Docker build smoke test

Run `docker build .` to verify the Dockerfile still builds.

AI Prompt: Build the Docker image and verify it completes
without errors.
