# Development Approach

## Overview

Refactor the flat cotd project into a hierarchical Python package.
This is a structural change — no business logic modifications.

## Phases

### Phase 1 — Scaffold the Package

Create the `cotd/` directory structure with `__init__.py` files.
Move all Python source files into their target locations. Update
`pyproject.toml` with entry points and dependency changes. Remove
PEP 723 script headers.

### Phase 2 — Fix Imports

Update all import statements across the codebase to use the new
package paths. Apply the import convention: absolute across
subpackages, relative within.

### Phase 3 — Update Tests

Update all test files to import from the new package paths.
Verify all 215 tests pass.

### Phase 4 — Update Deployment Artifacts

Update the Dockerfile to install the full package and use the
`cotd-takeover` entry point. Update `setup.sh` crontab line.
Update `run.sh`. Update `lefthook.yml` if needed. Update GitHub
Actions workflows if needed.

### Phase 5 — Verify and Clean Up

Run ruff, ty, and the full test suite. Remove old root-level
`.py` files if any remain. Verify entry points work.
