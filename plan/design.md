# Package Restructuring Design

## Problem

The cotd project started as a simple bash script replacement and grew
into 21 Python files at the root level — a mix of the main catcher
script, a Flask webapp, library modules, management CLIs, and
migration scripts. The flat structure causes:

- **Cognitive load:** 21 `.py` files plus SQL, shell, and config files
  in one directory.
- **Import confusion:** No clear boundary between runnable scripts and
  importable libraries. Several files serve both roles.
- **Deployment boundary blur:** The Dockerfile needs only
  `takeover_app.py` + `db.py`, but this isn't obvious from the
  structure.
- **Testing ambiguity:** No package boundary for tests to target.
- **Growth friction:** Adding features means more files in an already
  crowded root.

## Target Layout

```
cotd/
  __init__.py
  catcher.py            # main selection logic
  db.py                 # database access
  cleanup.py            # cleanup utilities
  takeover.py           # Flask webapp (renamed from takeover_app.py)
  sync/
    __init__.py
    vacation_sync.py
    ical_sync.py
    user_matcher.py
  cli/
    __init__.py
    manage_tenants.py
    manage_users.py
    manage_vacations.py
    cleanup_selection_history.py
    user_statistics.py
  migrations/
    __init__.py
    migrate_vacations.py
    migrate_weighted_selection.py
    migrate_to_tenants.py
    migrate_selection_history_tenant.py
    migrate_ical_support.py
    migrate_takeover.py
    migrate_channel_id.py
    migrate_remove_auth.py
    migrate_vacation_upsert.py
tests/                  # stays where it is
schema.sql              # stays at project root
schema_tenants.sql      # stays at project root
setup.sh                # stays at project root
run.sh                  # stays at project root
pyproject.toml
Dockerfile
```

## Entry Points

Defined in `pyproject.toml` under `[project.scripts]`:

| Entry point | Module function | Purpose |
|---|---|---|
| `cotd` | `cotd.catcher:main` | Daily catcher selection |
| `cotd-takeover` | `cotd.takeover:main` | Flask takeover webapp |
| `cotd-tenants` | `cotd.cli.manage_tenants:main` | Tenant management |
| `cotd-users` | `cotd.cli.manage_users:main` | User management |
| `cotd-vacations` | `cotd.cli.manage_vacations:main` | Vacation management |
| `cotd-stats` | `cotd.cli.user_statistics:main` | Selection statistics |
| `cotd-cleanup` | `cotd.cli.cleanup_selection_history:main` | History cleanup |
| `cotd-sync` | `cotd.sync.vacation_sync:main` | Vacation iCal sync |

Migrations have no entry points. Run via:
`uv run python -m cotd.migrations.migrate_to_tenants`

## Key Decisions

- **No `src/` layout.** The project is a deployed application, not a
  distributed PyPI package. Flat package at the root keeps `uv run`
  working without extra install ceremony.
- **Drop PEP 723 inline script metadata.** Dependencies declared once
  in `pyproject.toml`. Remove `# /// script` blocks and
  `#!/usr/bin/env -S uv run --script` hashbangs from all files.
- **Move Flask to regular dependencies.** It is a production
  dependency (takeover webapp is containerized). Without PEP 723
  headers, `uv sync --no-dev` must include it.
- **Absolute imports across subpackages, relative within.** Example:
  `from cotd.db import get_db_connection` (cross-package),
  `from .ical_sync import ICalParser` (within `sync/`).
- **Dockerfile installs the full package.** Uses `cotd-takeover`
  entry point. No cherry-picking of individual files.
- **Crontab** changes from `uv run catcher.py` to `uv run cotd`.
- **SQL schemas and shell scripts stay at project root.** They are
  operational artifacts, not Python code.
- **`setup.sh` stays as a shell script.** Only the crontab line
  updates.

## Import Convention

Cross-subpackage (absolute):

```python
from cotd.db import DATABASE_PATH, get_db_connection
from cotd.cleanup import cleanup_old_selection_history
```

Within a subpackage (relative):

```python
# Inside cotd/sync/vacation_sync.py
from .ical_sync import ICalParser
from .user_matcher import UserMatcher
```

## Dependency Changes

- Flask moves from `[dependency-groups]` dev to
  `[project.dependencies]`.
- PEP 723 `# /// script` blocks removed from all files.
- `freezegun` stays as dev dependency (test-only).
