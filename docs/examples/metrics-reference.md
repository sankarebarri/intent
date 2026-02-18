# Metrics Reference

Use this page to design stable JSON outputs for `checks.assertions` and summary metrics.

## Metric path catalog

| Use case | JSON path | Type | Typical assertion |
| --- | --- | --- | --- |
| Test failures | `tests.failed` | integer | `eq 0` |
| Coverage percent | `coverage.percent` | number | `gte 85` |
| Lint error count | `lint.errors` | integer | `eq 0` |
| Security criticals | `security.critical` | integer | `eq 0` |
| Pending migrations | `migrations.pending` | integer | `eq 0` |
| P95 latency (ms) | `latency.p95_ms` | number | `lte 250` |

## Real command definitions

```toml
[commands]
quality = "python scripts/quality_report.py"
security = "python scripts/security_report.py"
```

Example output of `quality`:

```json
{
  "tests": {"failed": 0, "passed": 128},
  "coverage": {"percent": 91.4},
  "lint": {"errors": 0, "warnings": 3},
  "migrations": {"pending": 0},
  "latency": {"p95_ms": 183.7}
}
```

Example output of `security`:

```json
{
  "security": {"critical": 0, "high": 1, "medium": 4}
}
```

## Assertions against those commands

```toml
[checks]
assertions = [
  { command = "quality", path = "tests.failed", op = "eq", value = 0 },
  { command = "quality", path = "coverage.percent", op = "gte", value = 85 },
  { command = "quality", path = "lint.errors", op = "eq", value = 0 },
  { command = "quality", path = "migrations.pending", op = "eq", value = 0 },
  { command = "quality", path = "latency.p95_ms", op = "lte", value = 250 },
  { command = "security", path = "security.critical", op = "eq", value = 0 }
]
```

## Command to generated CI step mapping

When commands are declared in `intent.toml`, generated CI jobs include corresponding run steps.

| intent command id | Generated CI step intent |
| --- | --- |
| `quality` | Run command and evaluate configured assertions |
| `security` | Run command and evaluate configured assertions |

Typical generated step shape:

```yaml
- name: Run quality
  run: python scripts/quality_report.py
```

The exact job layout can vary with your `ci` and jobs configuration, but command IDs stay stable and are reused by checks/summary.

## `intent check --format json` excerpt

Passing example:

```json
{
  "ok": true,
  "assertions": [
    {
      "command": "quality",
      "path": "coverage.percent",
      "op": "gte",
      "expected": 85,
      "actual": 91.4,
      "passed": true
    },
    {
      "command": "security",
      "path": "security.critical",
      "op": "eq",
      "expected": 0,
      "actual": 0,
      "passed": true
    }
  ]
}
```

Failing example:

```json
{
  "ok": false,
  "assertions": [
    {
      "command": "quality",
      "path": "latency.p95_ms",
      "op": "lte",
      "expected": 250,
      "actual": 301.8,
      "passed": false,
      "message": "latency regression"
    }
  ]
}
```

## Troubleshooting tips

1. Keep command JSON payloads deterministic and machine-readable.
2. Prefer stable keys (`coverage.percent`) over human text parsing.
3. Use one command per report domain if payloads become too large.
4. Start with strict critical gates and gradually add warning/perf thresholds.
