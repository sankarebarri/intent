# intent/cli.py
from __future__ import annotations

from pathlib import Path

import typer

from . import __version__
from .config import IntentConfigError, load_intent
from .fs import GENERATED_MARKER, OwnershipError, write_generated_file
from .pyproject_reader import PyprojectPythonStatus, read_pyproject_python
from .render_ci import render_ci
from .render_just import render_just
from .versioning import check_requires_python_range, max_lower_bound, parse_version

app = typer.Typer(help="Intent CLI", invoke_without_command=True)


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
    if existing == new_content:
        return f"No changes to {path}"
    return f"Would update {path}"


def _generated_drift_status(path: Path, new_content: str) -> tuple[bool, str]:
    if not path.exists():
        return False, f"{path} is missing"

    existing = path.read_text(encoding="utf-8")
    if GENERATED_MARKER not in existing:
        return False, f"{path} exists but is not tool-owned (missing marker)"
    if existing != new_content:
        return False, f"{path} is out of date"
    return True, f"{path} is up to date"


def _check_versions(cfg_python: str, strict: bool) -> tuple[bool, str]:
    """
    Semantics:
    - If incompatible -> fail
    - If compatible but pyproject is broader than intent -> warn (or fail if strict)
    """
    status, pyproject_version = read_pyproject_python()

    if status == PyprojectPythonStatus.FILE_MISSING:
        return True, "note: pyproject.toml not found; version cross-check skipped"
    if status == PyprojectPythonStatus.PROJECT_MISSING:
        return True, "note: pyproject.toml has no [project] table; version cross-check skipped"
    if status == PyprojectPythonStatus.REQUIRES_PYTHON_MISSING:
        return True, "note: [project].requires-python not set; version cross-check skipped"
    if status == PyprojectPythonStatus.INVALID:
        if strict:
            return False, "invalid requires-python value in pyproject.toml"
        return True, "note: invalid requires-python value; version cross-check skipped"

    if pyproject_version is None:
        return True, "note: [project].requires-python not set; version cross-check skipped"

    spec = pyproject_version.strip()

    # Simple spec: no operators => treat as equality
    if not any(ch in spec for ch in "<>,="):
        if spec == cfg_python:
            return True, f"pyproject requires_python matches intent ({spec})"
        return False, f"Version mismatch (simple spec): intent={cfg_python} vs pyproject={spec}"

    # Range-ish spec: best-effort compatibility check
    result = check_requires_python_range(cfg_python, spec)
    if result is False:
        return False, f"Version mismatch (range): intent {cfg_python} does not satisfy {spec}"
    if result is None:
        if strict:
            return False, f"Unsupported requires_python spec (strict): {spec}"
        return True, f"note: Unsupported requires_python spec (skipping): {spec}"

    # Compatible. Now detect "precision drift": pyproject broader than intent.
    intent_parsed = parse_version(cfg_python)
    if intent_parsed is None:
        return True, f"note: could not parse intent python.version ({cfg_python})"

    constraints = [c.strip() for c in spec.split(",") if c.strip()]
    lower = max_lower_bound(constraints)

    if lower is not None and lower < intent_parsed:
        msg = (
            f"pyproject requires_python ({spec}) is broader than intent ({cfg_python}); "
            "consider tightening pyproject to match intent"
        )
        if strict:
            return False, msg
        return True, f"note: {msg}"

    return True, f"Version ok (range): intent {cfg_python} satisfies {spec}"


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
        typer.echo("Error: --write and --dry-run cannot be used together", err=True)
        raise typer.Exit(code=2)

    path = Path(intent_path)

    try:
        cfg = load_intent(path)
    except FileNotFoundError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=2)
    except IntentConfigError as e:
        typer.echo(f"Config error: {e}", err=True)
        raise typer.Exit(code=2)

    typer.echo(f"Intent python version: {cfg.python_version}")
    typer.echo("Intent commands:")
    for name, cmd in cfg.commands.items():
        typer.echo(f"  {name} -> {cmd}")

    cfg = load_intent(path)
    ok_versions, msg_versions = _check_versions(cfg.python_version, strict=False)
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
            typer.echo(str(e), err=True)
            raise typer.Exit(code=1)

        typer.echo(f"Wrote {ci_path}" if ci_changed else f"No changes to {ci_path}")
        typer.echo(f"Wrote {just_path}" if just_changed else f"No changes to {just_path}")


@app.command()
def check(intent_path: str = "intent.toml", strict: bool = False) -> None:
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
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=2)
    except IntentConfigError as e:
        typer.echo(f"Config error: {e}", err=True)
        raise typer.Exit(code=2)

    drift = False

    ok_versions, msg_versions = _check_versions(cfg.python_version, strict=strict)
    if not ok_versions:
        drift = True
        typer.echo(f"✗ {msg_versions}", err=True)
    else:
        if msg_versions.startswith("note:"):
            typer.echo(msg_versions)
        else:
            typer.echo(f"✓ {msg_versions}")

    ci_path = Path(".github/workflows/ci.yml")
    just_path = Path("justfile")

    ci_ok, ci_msg = _generated_drift_status(ci_path, render_ci(cfg))
    just_ok, just_msg = _generated_drift_status(just_path, render_just(cfg))

    if ci_ok:
        typer.echo(f"✓ {ci_msg}")
    else:
        drift = True
        typer.echo(f"✗ {ci_msg}", err=True)

    if just_ok:
        typer.echo(f"✓ {just_msg}")
    else:
        drift = True
        typer.echo(f"✗ {just_msg}", err=True)

    if drift:
        typer.echo("\nHint: run `intent sync --write` to update generated files.", err=True)
        raise typer.Exit(code=1)

    raise typer.Exit(code=0)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
