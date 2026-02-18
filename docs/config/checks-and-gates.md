# Checks and Gates

`intent` supports two ways to declare quality rules:

- `checks.assertions`: low-level, explicit operator comparisons
- `checks.gates`: higher-level convenience layer

## Assertions

```toml
[commands]
eval = "cat metrics.json"

[checks]
assertions = [
  { command = "eval", path = "metrics.score", op = "gte", value = 0.9, message = "score regression gate" }
]
```

Fields:

- `command`: key from `[commands]`
- `path`: JSON path in command stdout JSON
- `op`: `eq`, `ne`, `gt`, `gte`, `lt`, `lte`, `in`, `not_in`
- `value`: expected value
- `message`: optional note

## Gates

```toml
[commands]
audit = "cat audit.json"

[checks]
gates = [
  { name = "migrations", kind = "threshold", command = "audit", path = "migrations.pending", max = 0 },
  { name = "warnings", kind = "threshold", command = "audit", path = "checks.warnings", max = 5 },
  { name = "status", kind = "equals", command = "audit", path = "status", value = "ok" }
]
```

Gate kinds:

- `threshold`: use `min` and/or `max`
- `equals`: use `value`

## When To Use Which

- Use `gates` for common thresholds/equality.
- Use `assertions` for advanced operators and custom logic.

Both can coexist in one project.
