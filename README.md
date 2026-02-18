# Intent

Intent keeps project automation config in sync from a single `intent.toml`.

- Source of truth: `intent.toml`
- Reads: `intent.toml`, `pyproject.toml`
- Generates baseline tool-owned files: `.github/workflows/ci.yml`, `justfile`

Full reference: [`documentation.md`](documentation.md)

## Install

From PyPI:

```bash
python -m pip install intent-cli
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

This bootstraps a baseline CI workflow and `justfile` from your `intent.toml`.
If you configure `[checks].assertions`, `intent check` evaluates typed JSON assertions on command output.
If you configure `[checks].gates`, Intent compiles high-level threshold/equality gates into typed assertions.
If you configure `[[ci.jobs]]`, Intent generates workflow jobs from typed job/step definitions instead of the baseline single-job template.
If you configure `[[ci.artifacts]]`, Intent generates upload steps for `actions/upload-artifact`.
If you configure `[ci.summary]`, Intent can publish a built-in markdown summary to `GITHUB_STEP_SUMMARY`.

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
eval = "cat metrics.json"

[checks]
assertions = [
  { command = "eval", path = "summary.score", op = "gte", value = 0.9 }
]

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
| `intent sync --show-json` | Print resolved sync config as JSON. |
| `intent sync --show-json --explain` | Include generated-file mapping details in JSON. |
| `intent sync --explain` | Show text mapping from intent config to generated blocks. |
| `intent sync --dry-run` | Preview file changes without writing. |
| `intent sync --write` | Write generated files. |
| `intent sync --write --adopt` | Adopt matching non-owned generated files. |
| `intent sync --write --force` | Force-overwrite non-owned generated files. |
| `intent check` | Detect drift without writing. |
| `intent check --format json` | Machine-readable drift report. |
| `intent lint-workflow` | Lint generated workflow semantics and print actionable warnings. |
| `intent lint-workflow --strict` | Fail when workflow lint warnings are found. |
| `intent doctor` | Diagnose issues with actionable fixes. |
| `intent reconcile --plan` | Preview Python-version reconciliation. |
| `intent reconcile --apply --allow-existing` | Apply reconciliation including existing-file edits. |

## Typed CI Jobs

```toml
[commands]
lint = "ruff check ."
test = "pytest -q"

[[ci.jobs]]
name = "lint"
steps = [{ uses = "actions/checkout@v4" }, { command = "lint" }]

[[ci.jobs]]
name = "test"
needs = ["lint"]
timeout_minutes = 20
matrix = { python-version = ["3.11", "3.12"] }
steps = [
  { uses = "actions/setup-python@v5", with = { python-version = "${{ matrix.python-version }}" } },
  { command = "test", continue_on_error = false }
]
```

## CI Artifacts

```toml
[ci]
artifacts = [
  { name = "junit", path = "reports/junit.xml", retention_days = 7, when = "on-failure" },
  { name = "coverage", path = "coverage.xml", when = "always" }
]
```

## CI Summary

```toml
[ci.summary]
enabled = true
title = "Quality Report"
include_assertions = true
metrics = [
  { label = "score", command = "eval", path = "metrics.score", baseline_path = "metrics.prev_score", precision = 3 }
]
```

Optional baseline source for metric deltas:

```toml
[ci.summary.baseline]
source = "file"
file = "baseline.json"
on_missing = "fail" # or "skip"
```

## Checks Gates (Convenience Layer)

```toml
[commands]
audit = "cat audit.json"

[checks]
gates = [
  { kind = "threshold", command = "audit", path = "migrations.pending", max = 0 },
  { kind = "equals", command = "audit", path = "status", value = "ok" }
]
```

## Safety Model

- Writes only tool-owned files in normal sync flow.
- Refuses unsafe overwrite unless explicitly requested.
- Supports explicit ownership modes: `strict`, `adopt`, `force`.
- Uses stable error codes (`INTENTxxx`) for automation.
- Supports typed quality assertions via `[checks].assertions` in `intent.toml`.

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

## License

MIT
