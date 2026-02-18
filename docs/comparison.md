# intent vs Other Tools

`intent` is not a replacement for every tool below. It is a coordination layer for config generation + drift control + typed policy checks.

| Capability | intent-cli | Raw GitHub Actions | pre-commit | tox/nox |
| --- | --- | --- | --- | --- |
| Single source config for CI + task runner | Strong | Manual | No | Partial |
| Deterministic generated files with ownership marker | Yes | No | No | No |
| Built-in drift detection | Yes (`intent check`) | Manual scripts | Hook-only | Manual |
| Typed checks/assertions and gates on JSON output | Yes | Manual | Manual | Manual |
| Typed artifacts and summaries | Yes | Manual YAML | No | No |
| Typed job/step modeling | Yes | Native but hand-authored | No | Session model only |
| Explain mapping from config -> generated blocks | Yes (`sync --explain`) | No | No | No |
| Best fit | Team-wide CI standardization | Fully custom CI | Local commit policy | Python env/test orchestration |

## Practical Positioning

- Use `intent` to standardize and guard generated automation.
- Use `tox`/`nox` for environment/session orchestration.
- Use `pre-commit` for local commit-time checks.
- Keep raw GitHub YAML only where direct hand-control is required.
