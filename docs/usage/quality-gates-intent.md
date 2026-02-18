# Quality Gates Intent

Use typed assertions when you want reliable, machine-checkable pass/fail rules instead of long shell one-liners.

## Example `intent.toml`

```toml
version = 1

[project]
name = "api-service"

[commands]
quality = "python scripts/quality_report.py"

[checks]
assertions = [
  { command = "quality", path = "tests.failed", op = "eq", value = 0, message = "tests must pass" },
  { command = "quality", path = "coverage.percent", op = "gte", value = 85, message = "coverage too low" },
  { command = "quality", path = "security.critical", op = "eq", value = 0 }
]
```

## Example command output contract

`quality_report.py` should print JSON like:

```json
{
  "tests": {"failed": 0},
  "coverage": {"percent": 91.2},
  "security": {"critical": 0}
}
```

## Run checks

```bash
intent check
```

If any assertion fails, `intent check` exits non-zero with assertion details.
