# Usage Overview

`intent` is most effective when you start simple and then add structure as your workflow grows.

Common progression:

1. Baseline generation: one config file generates baseline CI + `justfile`.
2. Quality gates: typed checks/assertions fail CI when key conditions are not met.
3. Full CI modeling: custom jobs/steps, artifacts, summaries, and dependency ordering.

## Minimal flow

```bash
intent init --from-existing
intent sync --write
intent check
```

This gives you generated, deterministic project automation with drift detection.

## Which page to read next

- Start here for first setup: [Baseline Intent](baseline-intent.md)
- Add pass/fail quality rules: [Quality Gates Intent](quality-gates-intent.md)
- Model richer pipelines: [Full CI Intent](full-ci-intent.md)
