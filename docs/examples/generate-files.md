# Generate Files and Drift

## Baseline Generation

```toml
[python]
version = "3.12"

[commands]
test = "pytest -q"
lint = "ruff check ."
```

Run:

```bash
intent sync --write
```

This creates tool-owned:

- `.github/workflows/ci.yml`
- `justfile`

## Drift Detection

Run:

```bash
intent check --strict
```

Use in CI to block stale generated files.

## Explain Mapping

Run:

```bash
intent sync --show-json --explain
```

Use this output for tooling/debugging when teammates ask how a field in `intent.toml` maps to generated YAML/recipes.
