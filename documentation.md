# Intent Documentation

Extended reference for configuring and using `intent`.

## What Intent Does

- Uses `intent.toml` as the source of truth.
- Validates Python version compatibility with `pyproject.toml`.
- Generates tool-owned files:
  - `.github/workflows/ci.yml`
  - `justfile`
- Refuses unsafe overwrites of non tool-owned generated files.

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

[ci]
install = "-e .[dev]"
python_versions = ["3.11", "3.12"]
triggers = ["push", "pull_request"]

[policy]
strict = false
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
- `[ci].python_versions`
  - Optional
  - Non-empty array of Python versions for CI matrix
  - If omitted, CI uses `[python].version`
- `[ci].triggers`
  - Optional
  - Non-empty array of workflow triggers
  - If omitted, CI defaults to `["push"]`
- `[policy].strict`
  - Optional
  - Default: `false`
  - Controls default strictness for `intent check`

## Command Reference

- `intent --version`
  - Print CLI version
- `intent init`
  - Create starter `intent.toml`
- `intent init --from-existing`
  - Infer Python version from existing `pyproject.toml` when possible
- `intent init --force`
  - Overwrite existing `intent.toml`
- `intent show`
  - Print resolved config and pyproject inspection summary
- `intent show --format json`
  - Machine-readable resolved config
- `intent sync`
  - Print config + version checks
- `intent sync --show-ci`
  - Preview rendered CI workflow
- `intent sync --show-just`
  - Preview rendered justfile
- `intent sync --dry-run`
  - Show what would be written
- `intent sync --write`
  - Write generated files
- `intent check`
  - Detect drift without writing
- `intent check --strict`
  - Strict version compatibility behavior
- `intent check --no-strict`
  - Override strict default to non-strict
- `intent check --format json`
  - Machine-readable drift report
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
