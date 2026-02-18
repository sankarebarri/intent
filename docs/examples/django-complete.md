# Complete Django Example

This example shows a full Django CI intent with typed assertions, artifacts, and summary metrics.

## Project setup assumptions

- Django project uses `manage.py`
- `pytest` (or `pytest-django`) is used for tests
- `scripts/django_audit.py` prints a JSON report used by checks

## `intent.toml` (copy/paste ready)

```toml
version = 1

[project]
name = "django-service"

[ci]
python = ["3.11", "3.12"]
on = ["push", "pull_request"]

[commands]
lint = "ruff check ."
format_check = "black --check ."
django_check = "python manage.py check --deploy --fail-level WARNING"
migrations_check = "python manage.py makemigrations --check --dry-run"
test = "pytest -q --maxfail=1 --junitxml=reports/junit.xml"
coverage = "pytest -q --cov=. --cov-report=term --cov-report=json:reports/coverage.json"
audit = "python scripts/django_audit.py"

[checks]
assertions = [
  { command = "audit", path = "migrations.pending", op = "eq", value = 0, message = "unapplied migrations" },
  { command = "audit", path = "checks.critical", op = "eq", value = 0, message = "critical checks must be zero" },
  { command = "audit", path = "checks.warnings", op = "lte", value = 5, message = "too many warnings" },
  { command = "audit", path = "tests.failed", op = "eq", value = 0, message = "tests failed" },
  { command = "audit", path = "coverage.percent", op = "gte", value = 85, message = "coverage below threshold" }
]

[ci.artifacts]
items = [
  { path = "reports/junit.xml", name = "django-junit", retention_days = 7, when = "always" },
  { path = "reports/coverage.json", name = "django-coverage", retention_days = 7, when = "always" },
  { path = "reports/django-audit.json", name = "django-audit", retention_days = 14, when = "always" }
]

[ci.summary]
enabled = true
metrics = [
  { label = "Coverage %", command = "audit", path = "coverage.percent", precision = 2 },
  { label = "Django warnings", command = "audit", path = "checks.warnings", precision = 0 },
  { label = "Pending migrations", command = "audit", path = "migrations.pending", precision = 0 }
]
```

## Supporting script: `scripts/django_audit.py`

```python
#!/usr/bin/env python3
import json
from pathlib import Path

# In real projects, gather these values from command outputs.
report = {
    "migrations": {"pending": 0},
    "checks": {"critical": 0, "warnings": 2},
    "tests": {"failed": 0, "passed": 128},
    "coverage": {"percent": 89.41},
}

Path("reports").mkdir(parents=True, exist_ok=True)
Path("reports/django-audit.json").write_text(
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
python manage.py check --deploy --fail-level WARNING
python manage.py makemigrations --check --dry-run
pytest -q --maxfail=1 --junitxml=reports/junit.xml
python scripts/django_audit.py
intent check
```

## Expected result

- Generated baseline files are in sync with `intent.toml`
- Assertions pass:
  - `migrations.pending == 0`
  - `checks.critical == 0`
  - `checks.warnings <= 5`
  - `tests.failed == 0`
  - `coverage.percent >= 85`
- Artifacts are available in CI
- Summary includes coverage/warnings/migration values

## Failure mode and fix

Example failure payload:

```json
{
  "migrations": {"pending": 2},
  "checks": {"critical": 1, "warnings": 9},
  "tests": {"failed": 3, "passed": 120},
  "coverage": {"percent": 78.0}
}
```

Result: `intent check` fails with assertion errors.

Fixes:

1. Apply migrations and commit migration files.
2. Resolve critical Django checks first.
3. Reduce warnings or adjust acceptable threshold.
4. Fix failing tests and increase coverage before merge.
