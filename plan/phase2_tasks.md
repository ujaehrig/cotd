# Phase 2 — Fix Imports

## Tasks

### 2.1 Update imports in `cotd/catcher.py`

Change:

- `from db import ...` → `from cotd.db import ...`
- `from cleanup import ...` → `from cotd.cleanup import ...`
- `from vacation_sync import ...` → `from cotd.sync.vacation_sync import ...`

AI Prompt: Update all import statements in cotd/catcher.py to
use absolute package imports (cotd.db, cotd.cleanup,
cotd.sync.vacation_sync).

### 2.2 Update imports in `cotd/takeover.py`

Change:

- `from db import ...` → `from cotd.db import ...`

AI Prompt: Update import statements in cotd/takeover.py to use
absolute package imports.

### 2.3 Update imports in `cotd/sync/` modules

In `vacation_sync.py`:

- `from ical_sync import ...` → `from .ical_sync import ...`
- `from user_matcher import ...` → `from .user_matcher import ...`
- `from db import ...` → `from cotd.db import ...`

In `ical_sync.py` and `user_matcher.py`:

- No sibling imports to change, but check for any `from db`
  imports.

AI Prompt: Update imports in all cotd/sync/ modules. Use relative
imports within the sync subpackage and absolute imports for
cross-package dependencies.

### 2.4 Update imports in `cotd/cli/` modules

All CLI scripts import from `db`. Some import from
`vacation_sync` or `cleanup`. Update all to absolute package
imports.

AI Prompt: Update imports in all cotd/cli/ modules to use
absolute package imports (cotd.db, cotd.cleanup,
cotd.sync.vacation_sync).

### 2.5 Update imports in `cotd/migrations/` modules

All migrations import from `db`. Update to absolute package
imports.

AI Prompt: Update imports in all cotd/migrations/ modules to use
absolute package imports (cotd.db).
