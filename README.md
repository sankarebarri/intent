# Intent

Intent keeps project automation config in sync from a single `intent.toml`.

- Source of truth: `intent.toml`
- Reads: `intent.toml`, `pyproject.toml`
- Generates tool-owned files: `.github/workflows/ci.yml`, `justfile`

Full reference: [`documentation.md`](documentation.md)

## Install

From PyPI:

```bash
python -m pip install intent
```

From source:

```bash
python -m pip install -e .
```

## Quick Start

1. Initialize config:

```bash
intent init
```

2. Generate files:

```bash
intent sync --write
```

3. Verify drift in CI/pre-commit:

```bash
intent check --strict
```

## Minimal `intent.toml`

```toml
[intent]
schema_version = 1

[python]
version = "3.12"

[commands]
test = "pytest -q"
lint = "ruff check ."

[ci]
install = "-e .[dev]"

[policy]
pack = "default"
strict = false
```

## Common Commands

| Command | Purpose |
| --- | --- |
| `intent init` | Create starter config. |
| `intent init --from-existing` | Infer Python version from `pyproject.toml` when possible. |
| `intent init --starter tox` | Generate tool-owned `tox.ini` starter (reuses existing `intent.toml`). |
| `intent init --starter nox` | Generate tool-owned `noxfile.py` starter (reuses existing `intent.toml`). |
| `intent sync` | Show config + version checks. |
| `intent sync --dry-run` | Preview file changes without writing. |
| `intent sync --write` | Write generated files. |
| `intent sync --write --adopt` | Adopt matching non-owned generated files. |
| `intent sync --write --force` | Force-overwrite non-owned generated files. |
| `intent check` | Detect drift without writing. |
| `intent check --format json` | Machine-readable drift report. |
| `intent doctor` | Diagnose issues with actionable fixes. |
| `intent reconcile --plan` | Preview Python-version reconciliation. |
| `intent reconcile --apply --allow-existing` | Apply reconciliation including existing-file edits. |

## Safety Model

- Writes only tool-owned files in normal sync flow.
- Refuses unsafe overwrite unless explicitly requested.
- Supports explicit ownership modes: `strict`, `adopt`, `force`.
- Uses stable error codes (`INTENTxxx`) for automation.

## Pre-commit Hook

```yaml
repos:
  - repo: local
    hooks:
      - id: intent-check
        name: intent check
        entry: intent check --strict
        language: system
        pass_filenames: false
```

## Release Note

Current package version in this repo is `0.1.0` (`pyproject.toml`).
If `0.1.0` is already published on PyPI, bump version before upload.

## License

MIT
