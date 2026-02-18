# Getting Started

## Install

```bash
python -m pip install intent-cli
```

## Initialize

```bash
intent init
```

## Generate Baseline Files

```bash
intent sync --write
```

Generated files:

- `.github/workflows/ci.yml`
- `justfile`

## Check Drift

```bash
intent check --strict
```

## Typical Team Flow

1. Update `intent.toml`.
2. Run `intent sync --write`.
3. Commit `intent.toml` + generated files.
4. Run `intent check --strict` in CI.
