# Complete FastAPI Example

This example shows a full FastAPI CI intent with typed assertions, artifacts, and summary metrics.

## Project setup assumptions

- FastAPI app lives in package `app`
- Test suite uses `pytest`
- `scripts/fastapi_quality.py` prints a JSON report used by checks

## `intent.toml` (copy/paste ready)

```toml
version = 1

[project]
name = "fastapi-service"

[ci]
python = ["3.10", "3.11", "3.12"]
on = ["push", "pull_request"]

[commands]
lint = "ruff check ."
format_check = "black --check ."
test = "pytest -q --maxfail=1 --junitxml=reports/junit.xml"
coverage = "pytest -q --cov=app --cov-report=term --cov-report=json:reports/coverage.json"
openapi = "python scripts/validate_openapi.py"
quality = "python scripts/fastapi_quality.py"

[checks]
assertions = [
  { command = "quality", path = "tests.failed", op = "eq", value = 0, message = "tests must pass" },
  { command = "quality", path = "coverage.percent", op = "gte", value = 90, message = "coverage gate" },
  { command = "quality", path = "openapi.valid", op = "eq", value = true, message = "OpenAPI must be valid" },
  { command = "quality", path = "latency.p95_ms", op = "lte", value = 250, message = "p95 latency too high" }
]

[ci.artifacts]
items = [
  { path = "reports/junit.xml", name = "fastapi-junit", retention_days = 7, when = "always" },
  { path = "reports/coverage.json", name = "fastapi-coverage", retention_days = 7, when = "always" },
  { path = "reports/fastapi-quality.json", name = "fastapi-quality", retention_days = 14, when = "always" }
]

[ci.summary]
enabled = true
metrics = [
  { label = "Coverage %", command = "quality", path = "coverage.percent", precision = 2 },
  { label = "Tests failed", command = "quality", path = "tests.failed", precision = 0 },
  { label = "p95 latency (ms)", command = "quality", path = "latency.p95_ms", precision = 1 }
]
```

## Supporting script: `scripts/fastapi_quality.py`

```python
#!/usr/bin/env python3
import json
from pathlib import Path

# In real projects, gather these values from test/coverage/openapi steps.
report = {
    "tests": {"failed": 0, "passed": 212},
    "coverage": {"percent": 92.73},
    "openapi": {"valid": True},
    "latency": {"p95_ms": 187.4},
}

Path("reports").mkdir(parents=True, exist_ok=True)
Path("reports/fastapi-quality.json").write_text(
    json.dumps(report, indent=2),
    encoding="utf-8",
)
print(json.dumps(report))
```

## Command pipeline

```bash
intent sync --write
intent check
```

Optional local pre-check run:

```bash
ruff check .
black --check .
pytest -q --maxfail=1 --junitxml=reports/junit.xml
pytest -q --cov=app --cov-report=json:reports/coverage.json
python scripts/validate_openapi.py
python scripts/fastapi_quality.py
intent check
```

## Expected result

- Generated baseline files are in sync with `intent.toml`
- Assertions pass:
  - `tests.failed == 0`
  - `coverage.percent >= 90`
  - `openapi.valid == true`
  - `latency.p95_ms <= 250`
- Artifacts are uploaded and retained per config
- Summary includes test/coverage/latency values

## Failure mode and fix

Example failure payload:

```json
{
  "tests": {"failed": 4, "passed": 198},
  "coverage": {"percent": 83.9},
  "openapi": {"valid": false},
  "latency": {"p95_ms": 312.2}
}
```

Result: `intent check` fails with assertion errors.

Fixes:

1. Repair broken tests.
2. Add/restore coverage in changed modules.
3. Fix schema/route validation issues in OpenAPI generation.
4. Investigate slow endpoints or relax threshold if justified.
