# Phase 4 — Update Deployment Artifacts

## Tasks

### 4.1 Update Dockerfile

Replace the current file-copy approach with a full package
install:

```dockerfile
COPY pyproject.toml uv.lock ./
COPY cotd/ cotd/
RUN uv sync --no-dev
CMD ["uv", "run", "cotd-takeover"]
```

AI Prompt: Rewrite the Dockerfile to install the full cotd
package and use the cotd-takeover entry point instead of copying
individual files and running uv run --script.

### 4.2 Update setup.sh

Change the crontab line from:

```
uv run catcher.py
```

to:

```
uv run cotd
```

AI Prompt: Update setup.sh to use the cotd entry point in the
crontab line.

### 4.3 Update run.sh

Change from `uv run catcher.py` to `uv run cotd`.

AI Prompt: Update run.sh to use the cotd entry point.

### 4.4 Update lefthook.yml

Check if file globs need updating now that Python files are
under `cotd/` instead of the root.

AI Prompt: Update lefthook.yml glob patterns to match the new
file locations under cotd/.

### 4.5 Update GitHub Actions workflows

Check if `docker.yml` path triggers need updating (it currently
watches `takeover_app.py` and `db.py`).

AI Prompt: Update .github/workflows/docker.yml path triggers to
watch the new file locations under cotd/.
