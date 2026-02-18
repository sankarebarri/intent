# Configuration Schema

## Minimal Example

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
```

## Top-Level Sections

- `[intent]`: schema controls
- `[python]`: project Python version
- `[commands]`: command catalog used by CI/checks/justfile
- `[checks]`: assertions and gates
- `[ci]`: triggers, matrix, jobs, artifacts, summary
- `[plugins]`: optional check/generate hooks
- `[policy]`: strictness defaults/packs

## Notes

- `[commands]` is required and non-empty.
- All generated files are ownership-protected by marker.
- Custom workflows remain possible with `run` escape hatches.
