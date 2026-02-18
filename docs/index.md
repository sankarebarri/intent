# intent-cli Docs

`intent-cli` keeps automation config in sync from a single `intent.toml`.

- Source of truth: `intent.toml`
- Generates tool-owned baseline files:
  - `.github/workflows/ci.yml`
  - `justfile`
- Detects and blocks drift with `intent check`
- Supports typed checks/gates, typed CI jobs/steps, artifacts, and summaries

## Why Use It

- Teams get consistent CI and task-runner setup quickly.
- Config drift is explicit and detectable.
- Advanced workflows can still stay declarative.

## Docs Structure

- Start with **Getting Started**
- Then use **Configuration** and **CLI Reference**
- See **Examples** and **Integrations** for real project patterns
- Use **Comparison** to evaluate fit against other tools
