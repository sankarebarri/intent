# Metrics, Assertions, and Gates

## Example: JSON Metric Assertions

`scripts/eval.py` prints:

```json
{"metrics":{"score":0.92,"latency_p95_ms":140},"status":"ok"}
```

Config:

```toml
[commands]
eval = "python scripts/eval.py"

[checks]
assertions = [
  { command = "eval", path = "metrics.score", op = "gte", value = 0.9 },
  { command = "eval", path = "metrics.latency_p95_ms", op = "lt", value = 200 },
  { command = "eval", path = "status", op = "eq", value = "ok" }
]
```

## Example: Convenience Gates

```toml
[commands]
audit = "python scripts/audit.py"

[checks]
gates = [
  { kind = "threshold", command = "audit", path = "errors.critical", max = 0 },
  { kind = "threshold", command = "audit", path = "errors.warning", max = 10 },
  { kind = "equals", command = "audit", path = "status", value = "pass" }
]
```

## Example: Deltas with File Baseline

Current payload: `metrics.json`  
Baseline payload: `baseline.json`

```toml
[commands]
eval = "cat metrics.json"

[ci.summary]
enabled = true
metrics = [
  { label = "score", command = "eval", path = "metrics.score", baseline_path = "metrics.score", precision = 3 }
]

[ci.summary.baseline]
source = "file"
file = "baseline.json"
on_missing = "skip"
```
