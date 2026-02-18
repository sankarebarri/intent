# Troubleshooting

## `intent check` says files are missing or out of date

Run:

```bash
intent sync --write
```

## Generated file exists but is not tool-owned

Use one of:

- keep it user-owned and remove from intent control
- `intent sync --write --adopt` if contents already match
- `intent sync --write --force` for explicit replacement

## Summary metric baseline unavailable

If using `[ci.summary.baseline]` with `source = "file"`:

- ensure baseline file path exists and contains valid JSON
- use `on_missing = "skip"` if missing baseline should not fail checks

## Workflow lint warnings

Run:

```bash
intent lint-workflow
```

Use strict mode in CI when needed:

```bash
intent lint-workflow --strict
```
