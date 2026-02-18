# CLI Command Reference

## Core

- `intent init`
- `intent sync`
- `intent check`
- `intent show`
- `intent doctor`
- `intent reconcile`
- `intent lint-workflow`

## Common Flags

- `intent sync --write`
- `intent sync --dry-run`
- `intent sync --show-json`
- `intent sync --show-json --explain`
- `intent sync --explain`
- `intent check --strict`
- `intent check --format json`
- `intent lint-workflow --strict`

## Exit Code Patterns

- `0`: success
- `1`: drift/failures found
- `2`: config/usage errors
