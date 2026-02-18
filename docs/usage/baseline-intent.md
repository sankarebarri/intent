# Baseline Intent

Use this mode when you want fast, predictable project automation with almost no schema overhead.

## Example `intent.toml`

```toml
version = 1

[project]
name = "my-app"

[ci]
python = ["3.11"]
on = ["push", "pull_request"]

[commands]
lint = "ruff check ."
test = "pytest -q"
```

## Generate baseline files

```bash
intent sync --write
```

Generated baseline typically includes:

- `.github/workflows/ci.yml`
- `justfile`

## Keep generated files in sync

```bash
intent check
```

`intent check` fails if generated files drift from `intent.toml`.
