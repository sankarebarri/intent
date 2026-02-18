# Integrations with Other Tools

## pre-commit

Use drift checks as a local guard:

```yaml
repos:
  - repo: local
    hooks:
      - id: intent-check
        name: intent check
        entry: intent check --strict
        language: system
        pass_filenames: false
```

## tox / nox

- Keep environment orchestration in `tox`/`nox`.
- Keep CI generation + policy in `intent`.
- Use `intent init --starter tox|nox` when bootstrapping.

## GitHub Actions

- `intent` generates baseline YAML.
- Teams can still maintain custom jobs via `[[ci.jobs]]`.
- Use `intent lint-workflow` for semantic linting.

## Platform/Internal Tooling

Use:

```bash
intent sync --show-json --explain
```

This makes schema-to-generated mapping explicit for wrappers, templates, or audits.
