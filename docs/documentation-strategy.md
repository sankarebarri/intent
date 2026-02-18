# Documentation Strategy

## Tools Used

- `MkDocs`: static docs site generator
- `Material for MkDocs`: navigation, search, and readable defaults
- `mike`: versioned docs publishing (`0.1.3`, future versions, `latest`)

## Why These Tools Fit intent-cli

- Project docs are markdown-first.
- CLI and schema-heavy content benefits from structured nav and reference pages.
- Versioned docs are needed as config schema evolves.

## Content Model

1. **Getting Started**
   Fast onboarding, baseline generation, drift checks.
2. **Configuration**
   Typed schema sections with examples.
3. **CLI Reference**
   Commands, flags, and exit-code behavior.
4. **Examples**
   Practical patterns (metrics, gates, file generation, baseline deltas).
5. **Integrations**
   Django/FastAPI and tool ecosystem integration.
6. **Comparison**
   Tradeoffs vs raw YAML, pre-commit, tox/nox.
7. **Releases**
   Versioned notes starting from `0.1.3`.

## Maintenance Flow

1. Update docs when schema/CLI changes are merged.
2. Keep one example per feature in `docs/examples/`.
3. Keep compatibility pointer in root `documentation.md`.
4. Publish versioned docs from tags/releases.
