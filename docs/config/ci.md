# CI Jobs, Artifacts, Summary

## Typed Jobs and Steps

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
matrix = { python-version = ["3.11", "3.12"] }
steps = [
  { uses = "actions/setup-python@v5", with = { python-version = "${{ matrix.python-version }}" } },
  { command = "test" }
]
```

## Artifacts

```toml
[ci]
artifacts = [
  { name = "junit", path = "reports/junit.xml", retention_days = 7, when = "on-failure" }
]
```

## Summary and Metrics

```toml
[ci.summary]
enabled = true
title = "Quality Report"
include_assertions = true
metrics = [
  { label = "score", command = "eval", path = "metrics.score", baseline_path = "metrics.score", precision = 3 }
]
```

## Baseline Source

```toml
[ci.summary.baseline]
source = "file"
file = "baseline.json"
on_missing = "fail" # or "skip"
```

Behavior:

- `source = "current"`: baseline values from current payload.
- `source = "file"`: baseline values read from external JSON.
- `on_missing = "fail"`: metric fails when baseline is missing/unavailable.
- `on_missing = "skip"`: metric is reported without delta and does not fail.
