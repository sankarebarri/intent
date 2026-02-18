# Django and FastAPI Integrations

## Django Example

Use gates for migrations + system checks:

```toml
[commands]
audit = "python scripts/django_audit.py"

[checks]
gates = [
  { kind = "threshold", command = "audit", path = "migrations.pending", max = 0, name = "migrations" },
  { kind = "threshold", command = "audit", path = "checks.critical", max = 0, name = "critical checks" },
  { kind = "threshold", command = "audit", path = "checks.warnings", max = 5, name = "warning budget" }
]
```

Expected JSON output from `django_audit.py`:

```json
{"migrations":{"pending":0},"checks":{"critical":0,"warnings":2}}
```

## FastAPI Example

Use assertions for API schema + test/coverage output:

```toml
[commands]
quality = "python scripts/fastapi_quality.py"

[checks]
assertions = [
  { command = "quality", path = "tests.failed", op = "eq", value = 0 },
  { command = "quality", path = "coverage.percent", op = "gte", value = 85 },
  { command = "quality", path = "openapi.valid", op = "eq", value = true }
]
```

## Team Rollout Pattern

1. Start with baseline `intent sync --write`.
2. Add one gate/assertion at a time.
3. Enable `intent check --strict` in CI.
4. Add summary and artifacts once checks stabilize.
