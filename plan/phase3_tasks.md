# Phase 3 — Update Tests

## Tasks

### 3.1 Update test imports

All test files import from the old flat module names
(e.g., `from catcher import ...`). Update to the new package
paths (e.g., `from cotd.catcher import ...`).

AI Prompt: Update all import statements in tests/ to use the new
cotd package paths. For example, `from catcher import X` becomes
`from cotd.catcher import X`, `from takeover_app import X`
becomes `from cotd.takeover import X`, etc.

### 3.2 Update test fixtures referencing file paths

Some test fixtures reference `Path(__file__).parent.parent`
to find schema files. Verify these still resolve correctly
after the move, since the test files themselves haven't moved.

AI Prompt: Check all test files for path references like
`Path(__file__).parent.parent / "schema_tenants.sql"` and verify
they still resolve correctly. The tests stay in tests/ and the
schema files stay at the project root, so the relative paths
should still work.

### 3.3 Run the full test suite

Run `uv run pytest -v` and fix any remaining import or path
issues.

AI Prompt: Run the full test suite and fix any failures caused by
the restructuring.
