# intent/cli.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

import typer

from . import __version__
from .config import IntentConfigError, load_intent
from .fs import GENERATED_MARKER, OwnershipError, write_generated_file
from .pyproject_reader import PyprojectPythonStatus, read_pyproject_python
from .render_ci import render_ci
from .render_just import render_just
from .versioning import (
    check_requires_python_range,
    max_lower_bound,
    parse_pep440_version,
)

app = typer.Typer(help="Intent CLI", invoke_without_command=True)

ERR_USAGE_CONFLICT = "INTENT001"
ERR_CONFIG_NOT_FOUND = "INTENT002"
ERR_CONFIG_INVALID = "INTENT003"
ERR_OWNERSHIP = "INTENT004"
ERR_INIT_EXISTS = "INTENT005"
ERR_VERSION = "INTENT101"
ERR_FILE_MISSING = "INTENT201"
ERR_FILE_UNOWNED = "INTENT202"
ERR_FILE_OUTDATED = "INTENT203"


@app.callback()
def _root(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", help="Show version and exit", is_eager=True),
) -> None:
    if version:
        typer.echo(__version__)
        raise typer.Exit(code=0)

    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit(code=0)


def _preview_status(path: Path, new_content: str) -> str:
    if not path.exists():
        return f"Would write {path}"

    existing = path.read_text(encoding="utf-8")
    if GENERATED_MARKER not in existing:
        return f"Cannot update {path}: exists but is not tool-owned (missing marker)"
    if existing == new_content:
        return f"No changes to {path}"
    return f"Would update {path}"


def _generated_drift_status(path: Path, new_content: str) -> tuple[bool, str, str | None]:
    if not path.exists():
        return False, f"{path} is missing", ERR_FILE_MISSING

    existing = path.read_text(encoding="utf-8")
    if GENERATED_MARKER not in existing:
        return False, f"{path} exists but is not tool-owned (missing marker)", ERR_FILE_UNOWNED
    if existing != new_content:
        return False, f"{path} is out of date", ERR_FILE_OUTDATED
    return True, f"{path} is up to date", None


def _check_versions(cfg_python: str, strict: bool) -> tuple[bool, str, str | None]:
    """
    Semantics:
    - If incompatible -> fail
    - If compatible but pyproject is broader than intent -> warn (or fail if strict)
    """
    status, pyproject_version = read_pyproject_python()

    if status == PyprojectPythonStatus.FILE_MISSING:
        return True, "note: pyproject.toml not found; version cross-check skipped", None
    if status == PyprojectPythonStatus.PROJECT_MISSING:
        return True, "note: pyproject.toml has no [project] table; version cross-check skipped", None
    if status == PyprojectPythonStatus.REQUIRES_PYTHON_MISSING:
        return True, "note: [project].requires-python not set; version cross-check skipped", None
    if status == PyprojectPythonStatus.INVALID:
        if strict:
            return False, "invalid requires-python value in pyproject.toml", ERR_VERSION
        return True, "note: invalid requires-python value; version cross-check skipped", None

    if pyproject_version is None:
        return True, "note: [project].requires-python not set; version cross-check skipped", None

    spec = pyproject_version.strip()

    # Simple spec: no operators => treat as equality
    if not any(ch in spec for ch in "<>,="):
        spec_version = parse_pep440_version(spec)
        cfg_version = parse_pep440_version(cfg_python)
        if spec_version is None:
            if strict:
                return False, f"Unsupported requires_python spec (strict): {spec}", ERR_VERSION
            return True, f"note: Unsupported requires_python spec (skipping): {spec}", None
        if cfg_version is not None and spec_version == cfg_version:
            return True, f"pyproject requires_python matches intent ({spec})", None
        return False, f"Version mismatch (simple spec): intent={cfg_python} vs pyproject={spec}", ERR_VERSION

    # Range-ish spec: best-effort compatibility check
    result = check_requires_python_range(cfg_python, spec)
    if result is False:
        return False, f"Version mismatch (range): intent {cfg_python} does not satisfy {spec}", ERR_VERSION
    if result is None:
        if strict:
            return False, f"Unsupported requires_python spec (strict): {spec}", ERR_VERSION
        return True, f"note: Unsupported requires_python spec (skipping): {spec}", None

    # Compatible. Now detect "precision drift": pyproject broader than intent.
    intent_parsed = parse_pep440_version(cfg_python)
    if intent_parsed is None:
        return True, f"note: could not parse intent python.version ({cfg_python})", None
    lower = max_lower_bound(spec)

    if lower is not None and lower < intent_parsed:
        msg = (
            f"pyproject requires_python ({spec}) is broader than intent ({cfg_python}); "
            "consider tightening pyproject to match intent"
        )
        if strict:
            return False, msg, ERR_VERSION
        return True, f"note: {msg}", None

    return True, f"Version ok (range): intent {cfg_python} satisfies {spec}", None


def _render_intent_template(python_version: str) -> str:
    lines = [
        "[intent]",
        "schema_version = 1",
        "",
        "[python]",
        f'version = "{python_version}"',
        "",
        "[commands]",
        'test = "pytest -q"',
        'lint = "ruff check ."',
        "",
        "[ci]",
        'install = "-e .[dev]"',
        "",
        "[policy]",
        "strict = false",
        "",
    ]
    return "\n".join(lines)


def _infer_init_python_version(from_existing: bool) -> tuple[str, str]:
    default_version = "3.12"
    if not from_existing:
        return default_version, "default"

    status, raw = read_pyproject_python()
    if status != PyprojectPythonStatus.OK or raw is None:
        return default_version, "default"

    spec = raw.strip()
    if not spec:
        return default_version, "default"

    if not any(ch in spec for ch in "<>,="):
        parsed = parse_pep440_version(spec)
        if parsed is None:
            return default_version, "default"
        return f"{parsed.major}.{parsed.minor}", "pyproject"

    lower = max_lower_bound(spec)
    if lower is not None:
        return f"{lower.major}.{lower.minor}", "pyproject"

    if spec.startswith("==") and "," not in spec:
        parsed = parse_pep440_version(spec[2:].strip())
        if parsed is not None:
            return f"{parsed.major}.{parsed.minor}", "pyproject"

    return default_version, "default"


@app.command()
def init(
    intent_path: str = "intent.toml",
    from_existing: bool = False,
    force: bool = False,
) -> None:
    """
    Create a starter intent.toml.

    --from-existing: infer python version from pyproject.toml when possible.
    --force:         overwrite an existing intent.toml.
    """
    path = Path(intent_path)
    if path.exists() and not force:
        typer.echo(
            f"[{ERR_INIT_EXISTS}] Refusing to overwrite existing file: {path} (use --force)",
            err=True,
        )
        raise typer.Exit(code=2)

    python_version, source = _infer_init_python_version(from_existing)
    content = _render_intent_template(python_version)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    typer.echo(f"Wrote {path}")
    if from_existing:
        typer.echo(f"python.version = {python_version} ({source})")


@app.command()
def show(
    intent_path: str = "intent.toml",
    output_format: Literal["text", "json"] = typer.Option("text", "--format"),
) -> None:
    """
    Show resolved Intent config and related inspection info.
    """
    path = Path(intent_path)
    try:
        cfg = load_intent(path)
    except FileNotFoundError as e:
        if output_format == "json":
            typer.echo(
                json.dumps(
                    {
                        "ok": False,
                        "error": {"kind": "config", "message": f"{e}"},
                        "code": ERR_CONFIG_NOT_FOUND,
                    }
                )
            )
            raise typer.Exit(code=2)
        typer.echo(f"[{ERR_CONFIG_NOT_FOUND}] Error: {e}", err=True)
        raise typer.Exit(code=2)
    except IntentConfigError as e:
        if output_format == "json":
            typer.echo(
                json.dumps(
                    {
                        "ok": False,
                        "error": {"kind": "config", "message": f"{e}"},
                        "code": ERR_CONFIG_INVALID,
                    }
                )
            )
            raise typer.Exit(code=2)
        typer.echo(f"[{ERR_CONFIG_INVALID}] Config error: {e}", err=True)
        raise typer.Exit(code=2)

    pyproject_status, pyproject_requires_python = read_pyproject_python()
    resolved = {
        "ok": True,
        "intent_path": str(path),
        "schema_version": cfg.schema_version,
        "python_version": cfg.python_version,
        "policy_strict": cfg.policy_strict,
        "ci_install": cfg.ci_install,
        "commands": cfg.commands,
        "pyproject": {
            "status": pyproject_status.value,
            "requires_python": pyproject_requires_python,
        },
    }

    if output_format == "json":
        typer.echo(json.dumps(resolved))
        raise typer.Exit(code=0)

    typer.echo(f"Intent path: {path}")
    typer.echo(f"Schema version: {cfg.schema_version}")
    typer.echo(f"Python version: {cfg.python_version}")
    typer.echo(f"Policy strict: {cfg.policy_strict}")
    typer.echo(f"CI install: {cfg.ci_install}")
    typer.echo("Commands:")
    for name, cmd in cfg.commands.items():
        typer.echo(f"  {name} -> {cmd}")
    typer.echo(f"Pyproject status: {pyproject_status.value}")
    if pyproject_requires_python is not None:
        typer.echo(f"Pyproject requires-python: {pyproject_requires_python}")


@app.command()
def sync(
    intent_path: str = "intent.toml",
    show_ci: bool = False,
    show_just: bool = False,
    write: bool = False,
    dry_run: bool = False,
) -> None:
    """
    Show config + versions. Optionally preview generated files, or write them.

    --dry-run: show what would be written/updated (no writes)
    --write:   write tool-owned generated files
    """
    if write and dry_run:
        typer.echo(f"[{ERR_USAGE_CONFLICT}] Error: --write and --dry-run cannot be used together", err=True)
        raise typer.Exit(code=2)

    path = Path(intent_path)

    try:
        cfg = load_intent(path)
    except FileNotFoundError as e:
        typer.echo(f"[{ERR_CONFIG_NOT_FOUND}] Error: {e}", err=True)
        raise typer.Exit(code=2)
    except IntentConfigError as e:
        typer.echo(f"[{ERR_CONFIG_INVALID}] Config error: {e}", err=True)
        raise typer.Exit(code=2)

    typer.echo(f"Intent python version: {cfg.python_version}")
    typer.echo("Intent commands:")
    for name, cmd in cfg.commands.items():
        typer.echo(f"  {name} -> {cmd}")

    ok_versions, msg_versions, _ = _check_versions(cfg.python_version, strict=False)
    typer.echo(msg_versions)

    ci_path = Path(".github/workflows/ci.yml")
    just_path = Path("justfile")
    ci_content = render_ci(cfg)
    just_content = render_just(cfg)

    if show_ci:
        typer.echo("\n--- ci.yml (preview) ---\n")
        typer.echo(ci_content)

    if show_just:
        typer.echo("\n--- justfile (preview) ---\n")
        typer.echo(just_content)

    if dry_run:
        typer.echo("\n--- dry-run ---")
        typer.echo(_preview_status(ci_path, ci_content))
        typer.echo(_preview_status(just_path, just_content))
        raise typer.Exit(code=0)

    if write:
        try:
            ci_changed = write_generated_file(ci_path, ci_content)
            just_changed = write_generated_file(just_path, just_content)
        except OwnershipError as e:
            typer.echo(f"[{ERR_OWNERSHIP}] {e}", err=True)
            raise typer.Exit(code=1)

        typer.echo(f"Wrote {ci_path}" if ci_changed else f"No changes to {ci_path}")
        typer.echo(f"Wrote {just_path}" if just_changed else f"No changes to {just_path}")


@app.command()
def check(
    intent_path: str = "intent.toml",
    strict: bool | None = typer.Option(None, "--strict/--no-strict"),
    output_format: Literal["text", "json"] = typer.Option("text", "--format"),
) -> None:
    """
    Check drift without writing.

    Exit codes:
      0 = OK
      1 = drift / mismatch found
      2 = config/usage error
    """
    path = Path(intent_path)

    try:
        cfg = load_intent(path)
    except FileNotFoundError as e:
        if output_format == "json":
            typer.echo(
                json.dumps(
                    {
                        "ok": False,
                        "error": {"kind": "config", "message": f"{e}"},
                        "code": ERR_CONFIG_NOT_FOUND,
                    }
                )
            )
            raise typer.Exit(code=2)
        typer.echo(f"[{ERR_CONFIG_NOT_FOUND}] Error: {e}", err=True)
        raise typer.Exit(code=2)
    except IntentConfigError as e:
        if output_format == "json":
            typer.echo(
                json.dumps(
                    {
                        "ok": False,
                        "error": {"kind": "config", "message": f"{e}"},
                        "code": ERR_CONFIG_INVALID,
                    }
                )
            )
            raise typer.Exit(code=2)
        typer.echo(f"[{ERR_CONFIG_INVALID}] Config error: {e}", err=True)
        raise typer.Exit(code=2)

    drift = False
    effective_strict = cfg.policy_strict if strict is None else strict

    ok_versions, msg_versions, versions_code = _check_versions(
        cfg.python_version,
        strict=effective_strict,
    )
    ci_path = Path(".github/workflows/ci.yml")
    just_path = Path("justfile")

    ci_ok, ci_msg, ci_code = _generated_drift_status(ci_path, render_ci(cfg))
    just_ok, just_msg, just_code = _generated_drift_status(just_path, render_just(cfg))

    if output_format == "json":
        if not ok_versions:
            drift = True
        if not ci_ok:
            drift = True
        if not just_ok:
            drift = True

        payload = {
            "ok": not drift,
            "strict": effective_strict,
            "intent_path": str(path),
            "versions": {
                "ok": ok_versions,
                "message": msg_versions,
                "code": versions_code,
            },
            "files": [
                {
                    "path": str(ci_path),
                    "ok": ci_ok,
                    "message": ci_msg,
                    "code": ci_code,
                },
                {
                    "path": str(just_path),
                    "ok": just_ok,
                    "message": just_msg,
                    "code": just_code,
                },
            ],
        }
        typer.echo(json.dumps(payload))
        raise typer.Exit(code=1 if drift else 0)

    if not ok_versions:
        drift = True
        typer.echo(f"✗ [{versions_code}] {msg_versions}", err=True)
    else:
        if msg_versions.startswith("note:"):
            typer.echo(msg_versions)
        else:
            typer.echo(f"✓ {msg_versions}")

    if ci_ok:
        typer.echo(f"✓ {ci_msg}")
    else:
        drift = True
        typer.echo(f"✗ [{ci_code}] {ci_msg}", err=True)

    if just_ok:
        typer.echo(f"✓ {just_msg}")
    else:
        drift = True
        typer.echo(f"✗ [{just_code}] {just_msg}", err=True)

    if drift:
        typer.echo("\nHint: run `intent sync --write` to update generated files.", err=True)
        raise typer.Exit(code=1)

    raise typer.Exit(code=0)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
