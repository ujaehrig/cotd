# Phase 1 — Scaffold the Package

## Tasks

### 1.1 Create directory structure

Create:

- `cotd/__init__.py`
- `cotd/sync/__init__.py`
- `cotd/cli/__init__.py`
- `cotd/migrations/__init__.py`

AI Prompt: Create the cotd package directory structure with empty
`__init__.py` files for the root package and each subpackage
(sync, cli, migrations).

### 1.2 Move core files to `cotd/`

Move to `cotd/`:

- `catcher.py`
- `db.py`
- `cleanup.py`
- `takeover_app.py` → `cotd/takeover.py` (rename)

AI Prompt: Move the core Python files (catcher.py, db.py,
cleanup.py) into cotd/. Move takeover_app.py to cotd/takeover.py.

### 1.3 Move sync files to `cotd/sync/`

Move to `cotd/sync/`:

- `vacation_sync.py`
- `ical_sync.py`
- `user_matcher.py`

AI Prompt: Move vacation_sync.py, ical_sync.py, and
user_matcher.py into cotd/sync/.

### 1.4 Move CLI files to `cotd/cli/`

Move to `cotd/cli/`:

- `manage_tenants.py`
- `manage_users.py`
- `manage_vacations.py`
- `cleanup_selection_history.py`
- `user_statistics.py`

AI Prompt: Move all management scripts and the statistics/cleanup
CLIs into cotd/cli/.

### 1.5 Move migration files to `cotd/migrations/`

Move to `cotd/migrations/`:

- `migrate_vacations.py`
- `migrate_weighted_selection.py`
- `migrate_to_tenants.py`
- `migrate_selection_history_tenant.py`
- `migrate_ical_support.py`
- `migrate_takeover.py`
- `migrate_channel_id.py`
- `migrate_remove_auth.py`
- `migrate_vacation_upsert.py`

AI Prompt: Move all migrate_*.py files into cotd/migrations/.

### 1.6 Update pyproject.toml

- Add `[project.scripts]` entry points
- Move Flask from dev to regular dependencies
- Remove PEP 723 inline script metadata from all moved files

AI Prompt: Update pyproject.toml to define entry points for all
runnable scripts. Move flask from dev dependencies to regular
dependencies. Then remove PEP 723 script headers and hashbangs
from all Python files in the cotd package.

### 1.7 Delete old root-level Python files

Remove the original `.py` files from the project root now that
they live inside `cotd/`.

AI Prompt: Delete all Python files from the project root that
have been moved into the cotd/ package. Do not delete schema.sql,
schema_tenants.sql, setup.sh, run.sh, or any config files.
