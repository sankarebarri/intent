# Intent Documentation

Extended reference for configuring and using `intent`.

## What Intent Does

- Uses `intent.toml` as the source of truth.
- Validates Python version compatibility with `pyproject.toml`.
- Generates tool-owned files:
  - `.github/workflows/ci.yml`
  - `justfile`
- These generated files are baseline automation scaffolding you can extend as needed.
- Refuses unsafe overwrites of non-tool-owned generated files.

## Configuration Reference

Example:

```toml
[intent]
schema_version = 1

[python]
version = "3.12"

[commands]
test = "pytest -q"
lint = "ruff check ."
eval = "cat metrics.json"

[ci]
install = "-e .[dev]"
cache = "pip"
python_versions = ["3.11", "3.12"]
triggers = ["push", "pull_request"]

[policy]
pack = "default"
strict = false

[plugins]
check = ["./scripts/intent-check.sh"]
generate = ["./scripts/intent-generate.sh"]

[checks]
assertions = [
  { command = "eval", path = "metrics.score", op = "gte", value = 0.9, message = "score gate" }
]
```

Fields:

- `[intent].schema_version`
  - Current supported value: `1`
- `[python].version`
  - Required
  - Simple numeric version string such as `3.12`
- `[commands]`
  - Required non-empty table
  - Key = step name, value = shell command
- `[ci].install`
  - Optional
  - Default: `-e .[dev]`
- `[ci].cache`
  - Optional
  - Supported values: `none`, `pip`
  - Default: `none`
- `[ci].python_versions`
  - Optional
  - Non-empty array of Python versions for CI matrix
  - If omitted, CI uses `[python].version`
- `[ci].triggers`
  - Optional
  - Non-empty array of workflow triggers
  - If omitted, CI defaults to `["push"]`
- `[checks].assertions`
  - Optional
  - Array of assertion tables evaluated during `intent check`
  - Each assertion supports:
    - `command`: command key from `[commands]` (required)
    - `path`: JSON path into command stdout payload (required)
    - `op`: `eq`, `ne`, `gt`, `gte`, `lt`, `lte`, `in`, `not_in` (required)
    - `value`: expected value for comparison (required)
    - `message`: optional failure context
  - Commands referenced by assertions must exit `0` and emit valid JSON to stdout
- `[ci].jobs`
  - Optional
  - Non-empty array of job tables (`[[ci.jobs]]`)
  - When present, CI generation uses these typed jobs instead of the baseline single `ci` job template
  - Job fields:
    - `name` (required)
    - `runs_on` (optional, default `ubuntu-latest`)
    - `needs` (optional array of job names)
    - `if` (optional string)
    - `timeout_minutes` (optional positive integer)
    - `continue_on_error` (optional boolean)
    - `matrix` (optional table of non-empty arrays with scalar values)
    - `steps` (required non-empty array of step tables)
  - Step fields:
    - Exactly one of `run`, `command`, `uses` is required
    - `command` must reference a key in `[commands]`
    - `name`, `if`, `continue_on_error`, `working_directory` (all optional)
    - `env` (optional table of string values)
    - `with` (optional table of string values, used with `uses`)
- `[ci].artifacts`
  - Optional
  - Non-empty array of artifact tables (`[[ci.artifacts]]`)
  - Artifact fields:
    - `name` (required)
    - `path` (required)
    - `retention_days` (optional positive integer)
    - `when` (optional: `always`, `on-failure`, `on-success`; default `always`)
  - Renders upload steps using `actions/upload-artifact@v4`
- `[ci].summary`
  - Optional
  - Summary/report controls for workflow and `intent check --format json`
  - Fields:
    - `enabled` (optional boolean, default `true`)
    - `title` (optional string, default `Intent CI Summary`)
    - `include_assertions` (optional boolean, default `true`)
    - `metrics` (optional array of metric tables)
  - Metric fields:
    - `label` (required)
    - `command` (required, must reference `[commands]`)
    - `path` (required JSON path into command stdout JSON)
    - `baseline_path` (optional JSON path for delta calculation)
    - `precision` (optional integer >= 0)
  - When enabled:
    - baseline CI gets a summary step that writes markdown to `GITHUB_STEP_SUMMARY`
    - custom-job CI gets an additional `intent_summary` job
    - `intent check --format json` includes `report.summary_markdown` and `report.metrics`
- `[policy].pack`
  - Optional
  - Supported values: `default`, `strict`
  - Provides team policy presets for default behavior
- `[policy].strict`
  - Optional
  - Default: `false`
  - Controls default strictness for `intent check`
  - If both are set, explicit `strict` overrides `pack` defaults
- `[plugins].check`
  - Optional
  - Array of shell commands to run during `intent check`
  - Any non-zero exit fails with `INTENT301`
- `[plugins].generate`
  - Optional
  - Array of shell commands to run after `intent sync --write`
  - Any non-zero exit fails with `INTENT301`

## Checks Assertions Examples

Minimal metric threshold:

```toml
[commands]
eval = "cat metrics.json"

[checks]
assertions = [
  { command = "eval", path = "metrics.score", op = "gte", value = 0.9 }
]
```

## CI Jobs Examples

Typed jobs with dependencies and matrix:

```toml
[commands]
lint = "ruff check ."
test = "pytest -q"

[[ci.jobs]]
name = "lint"
steps = [
  { uses = "actions/checkout@v4" },
  { command = "lint" }
]

[[ci.jobs]]
name = "test"
needs = ["lint"]
timeout_minutes = 20
matrix = { python-version = ["3.11", "3.12"] }
steps = [
  { uses = "actions/setup-python@v5", with = { python-version = "${{ matrix.python-version }}" } },
  { command = "test", env = { PYTHONUNBUFFERED = "1" }, working_directory = "." }
]
```

Step-level shell escape hatch:

```toml
[[ci.jobs]]
name = "smoke"
steps = [
  { run = "echo custom shell logic && ./scripts/smoke.sh" }
]
```

Artifacts:

```toml
[ci]
artifacts = [
  { name = "junit", path = "reports/junit.xml", retention_days = 7, when = "on-failure" },
  { name = "coverage", path = "coverage.xml", when = "always" }
]
```

Summary/report configuration:

```toml
[ci.summary]
enabled = true
title = "Quality Report"
include_assertions = true
metrics = [
  { label = "score", command = "eval", path = "metrics.score", baseline_path = "metrics.prev_score", precision = 3 },
  { label = "latency_p95_ms", command = "eval", path = "perf.latency_p95", precision = 1 }
]
```

Multiple assertions with list membership and array indexing:

```toml
[commands]
eval = "cat eval.json"

[checks]
assertions = [
  { command = "eval", path = "summary.status", op = "in", value = ["ok", "warn"] },
  { command = "eval", path = "runs[0].latency_ms", op = "lt", value = 200, message = "p95 latency regression" },
  { command = "eval", path = "summary.dataset", op = "not_in", value = ["deprecated", "unknown"] }
]
```

## Command Reference

- `intent --version`
  - Print CLI version
- `intent init`
  - Create starter `intent.toml`
- `intent init --from-existing`
  - Infer Python version from existing `pyproject.toml` when possible
- `intent init --force`
  - Overwrite existing `intent.toml`
- `intent init --starter tox`
  - Also generate a tool-owned `tox.ini` starter file
  - Reuses existing `intent.toml` unless `--force` is provided
- `intent init --starter nox`
  - Also generate a tool-owned `noxfile.py` starter file
  - Reuses existing `intent.toml` unless `--force` is provided
- `intent show`
  - Print resolved config and pyproject inspection summary
- `intent show --format json`
  - Machine-readable resolved config
- `intent sync`
  - Print config + version checks
- `intent sync --show-json`
  - Emit resolved sync config as machine-readable JSON
- `intent sync --show-json --explain`
  - Include mapping details from intent fields to generated file blocks in JSON
- `intent sync --explain`
  - Print text mapping from intent fields to generated file blocks
- `intent sync --show-ci`
  - Preview rendered CI workflow
- `intent sync --show-just`
  - Preview rendered justfile
- `intent sync --dry-run`
  - Show what would be written
- `intent sync --write`
  - Write generated files
  - Then run optional `[plugins].generate` hooks
- `intent sync --write --adopt`
  - Adopt non-owned generated files only when existing body matches
- `intent sync --write --force`
  - Explicitly overwrite non-owned generated files
  - `--show-json` and `--explain` cannot be combined with `--write`
- `intent check`
  - Detect drift without writing
  - Also run optional `[plugins].check` hooks
  - Also run optional `[checks].assertions` gates
- `intent check --strict`
  - Strict version compatibility behavior
- `intent check --no-strict`
  - Override strict default to non-strict
- `intent check --format json`
  - Machine-readable drift report
- `intent doctor`
  - Diagnose common issues with actionable fix hints
- `intent reconcile --plan`
  - Show Python version reconciliation plan
- `intent reconcile --apply`
  - Apply safe reconciliation for missing files
- `intent reconcile --apply --allow-existing`
  - Allow edits to existing version files during reconcile apply

## Reconcile Behavior

`intent reconcile` coordinates Python versions across:

- `pyproject.toml` (`[project].requires-python`)
- `.python-version`
- `.tool-versions` (`python ...` entry)

Rules:

- `--plan` prints alignment/drift and suggested actions.
- `--apply` writes missing files.
- Existing-file edits are skipped unless `--allow-existing` is set.

## Unsupported `requires-python` Specs

When `pyproject.toml` contains an unsupported or invalid `requires-python` value:

- non-strict checks (`intent check` or `--no-strict`) emit a note and skip enforcement
- strict checks (`intent check --strict`) fail with `INTENT101`

## Stable Error Codes

- `INTENT001`: invalid option combination
- `INTENT002`: missing intent config file
- `INTENT003`: invalid intent config content
- `INTENT004`: ownership violation while writing generated files
- `INTENT005`: `init` overwrite refused without `--force`
- `INTENT101`: Python version compatibility/spec check failure
- `INTENT201`: generated file missing
- `INTENT202`: generated file not tool-owned
- `INTENT203`: generated file out of date
- `INTENT301`: plugin hook command failed
- `INTENT401`: check assertion failed

## Safety Model

- `intent` writes only tool-owned generated files for normal sync.
- It refuses overwrite if generated marker is missing.
- Writes are atomic.
- Reconcile updates to existing canonical/version files require explicit opt-in (`--allow-existing`).

## Troubleshooting

- `intent check` says CI file is out of date:
  - Run `intent sync --write`
- Pre-commit blocks commit due to drift:
  - Run `intent sync --write` and stage generated files
- Commit fails due to pre-commit cache permissions in restricted environments:
  - Use `PRE_COMMIT_HOME=/tmp/pre-commit git commit -m "..."` in that environment
