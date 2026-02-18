# Full CI Intent

Use full CI modeling when you need explicit jobs, dependencies, artifacts, and step summaries.

## Example `intent.toml`

```toml
version = 1

[project]
name = "backend-platform"

[ci]
python = ["3.11", "3.12"]
on = ["push", "pull_request"]

[commands]
lint = "ruff check ."
test = "pytest -q --junitxml=reports/junit.xml"
quality = "python scripts/quality_report.py"

[checks]
assertions = [
  { command = "quality", path = "coverage.percent", op = "gte", value = 85 },
  { command = "quality", path = "tests.failed", op = "eq", value = 0 }
]

[ci.artifacts]
items = [
  { path = "reports/junit.xml", name = "junit", retention_days = 7, when = "always" }
]

[ci.summary]
enabled = true
```

## Result

`intent sync --write` generates a baseline workflow and task runner config, then `intent check` validates drift and configured assertions.

This pattern is a good base for larger Django/FastAPI setups where teams want standardized CI behavior.
