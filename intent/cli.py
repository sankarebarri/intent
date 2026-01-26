from __future__ import annotations

from pathlib import Path

import typer

from . import __version__
from .config import IntentConfigError, load_intent
from .fs import GENERATED_MARKER, OwnershipError, write_generated_file
from .pyproject_reader import read_pyproject_python
from .render_ci import render_ci
from .render_just import render_just

app = typer.Typer(help="Intent CLI")


@app.callback()
def _root(
    version: bool = typer.Option(False, "--version", help="Show version and exit", is_eager=True),
) -> None:
    if version:
        typer.echo(__version__)
        raise typer.Exit(code=0)


def _parse_version(version: str) -> tuple[int, ...] | None:
    parts: list[int] = []
    for part in version.split("."):
        part = part.strip()
        if not part:
            break
        if not part.isdigit():
            return None
        parts.append(int(part))
    return tuple(parts) if parts else None


def _check_requires_python_range(intent_version: str, spec: str) -> bool | None:
    """
    Basic, best-effort checker for patterns like:
      '>=3.10,<3.13'
      '>=3.11'
      '<3.13'

    Returns:
      True  -> intent_version appears to satisfy the spec
      False -> intent_version does NOT satisfy the spec
      None  -> unsupported/unknown spec pattern
    """
    intent_parsed = _parse_version(intent_version)
    if intent_parsed is None:
        return None

    constraints = [c.strip() for c in spec.split(",") if c.strip()]
    if not constraints:
        return None

    supported = True
    ok = True

    for c in constraints:
        if c.startswith(">="):
            bound_parsed = _parse_version(c[2:].strip())
            if bound_parsed is None:
                supported = False
                continue
            if intent_parsed < bound_parsed:
                ok = False
        elif c.startswith("<"):
            bound_parsed = _parse_version(c[1:].strip())
            if bound_parsed is None:
                supported = False
                continue
            if not (intent_parsed < bound_parsed):
                ok = False
        else:
            supported = False

    return ok if supported else None


def _preview_status(path: Path, new_content: str) -> str:
    """
    Used by --dry-run and check.
    """
    if not path.exists():
        return f"Would write {path}"

    existing = path.read_text(encoding="utf-8")
    if existing == new_content:
        return f"No changes to {path}"
    return f"Would update {path}"


def _generated_drift_status(path: Path, new_content: str) -> tuple[bool, str]:
    """
    Used by `intent check`.

    Returns: (is_ok, message)
    """
    if not path.exists():
        return (False, f"{path} is missing")

    existing = path.read_text(encoding="utf-8")
    if GENERATED_MARKER not in existing:
        return False, f"{path} exists but is not tool-owned (missing marker)"
    if existing != new_content:
        return (False, f"{path} is out of date")
    return (True, f"{path} is up to date")


def _check_versions(cfg_python: str, strict: bool) -> tuple[bool, str]:
    """
    Compare intent.toml python.version with pyproject.toml requires_python.

    Returns: (ok, message)
    """
    pyproject_version = read_pyproject_python()
    if pyproject_version is None:
        return (True, "pyproject: requires_python not found (skipping)")

    spec = pyproject_version.strip()

    # Simple spec: no operators => treat as equality
    if not any(ch in spec for ch in "<>,="):
        if spec == cfg_python:
            return True, f"pyproject requires_python matches intent ({spec})"
        return False, f"Version mismatch (simple spec): intent={cfg_python} vs pyproject={spec}"

    # Range-ish spec: best-effort check
    result = _check_requires_python_range(cfg_python, spec)
    if result is True:
        return True, f"Version ok (range): intent {cfg_python} satisfies {spec}"
    if result is False:
        return False, f"Version mismatch (range): intent {cfg_python} does not satisfy {spec}"

    # Unsupported pattern
    if strict:
        return False, f"Unsupported requires_python spec (strict): {spec}"
    return True, f"Unsupported requires_python spec (skipping): {spec}"


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

    # From intent.toml
    typer.echo(f"Intent python version: {cfg.python_version}")
    typer.echo("Intent commands:")
    for name, cmd in cfg.commands.items():
        typer.echo(f"  {name} -> {cmd}")

    (
        ok_versions,
        msg_versions,
    ) = _check_versions(
        cfg.python_version,
        strict=False,
    )
    if "Unsupported" in msg_versions:
        typer.echo(f"note: {msg_versions}")
    else:
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
        typer.echo(
            _preview_status(
                ci_path,
                ci_content,
            )
        )
        typer.echo(
            _preview_status(
                just_path,
                just_content,
            )
        )
        raise typer.Exit(code=0)

    if write:
        try:
            ci_changed = write_generated_file(
                ci_path,
                ci_content,
            )
            just_changed = write_generated_file(
                just_path,
                just_content,
            )
        except OwnershipError as e:
            typer.echo(
                str(e),
                err=True,
            )
            raise typer.Exit(code=1)

        typer.echo(f"Wrote {ci_path}" if ci_changed else f"No changes to {ci_path}")
        typer.echo(f"Wrote {just_path}" if just_changed else f"No changes to {just_path}")


@app.command()
def check(
    intent_path: str = "intent.toml",
    strict: bool = False,
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
        typer.echo(
            f"Error: {e}",
            err=True,
        )
        raise typer.Exit(code=2)
    except IntentConfigError as e:
        typer.echo(
            f"Config error: {e}",
            err=True,
        )
        raise typer.Exit(code=2)

    drift = False

    (
        ok_versions,
        msg_versions,
    ) = _check_versions(
        cfg.python_version,
        strict=strict,
    )
    if not ok_versions:
        drift = True
        typer.echo(
            f"✗ {msg_versions}",
            err=True,
        )
    else:
        # show as note if unsupported but not strict
        if msg_versions.startswith("Unsupported"):
            typer.echo(f"note: {msg_versions}")
        else:
            typer.echo(f"✓ {msg_versions}")

    ci_path = Path(".github/workflows/ci.yml")
    just_path = Path("justfile")

    (
        ci_ok,
        ci_msg,
    ) = _generated_drift_status(
        ci_path,
        render_ci(cfg),
    )
    (
        just_ok,
        just_msg,
    ) = _generated_drift_status(
        just_path,
        render_just(cfg),
    )

    if ci_ok:
        typer.echo(f"✓ {ci_msg}")
    else:
        drift = True
        typer.echo(
            f"✗ {ci_msg}",
            err=True,
        )

    if just_ok:
        typer.echo(f"✓ {just_msg}")
    else:
        drift = True
        typer.echo(
            f"✗ {just_msg}",
            err=True,
        )

    if drift:
        typer.echo(
            "\nHint: run `intent sync --write` to update generated files.",
            err=True,
        )
        raise typer.Exit(code=1)

    raise typer.Exit(code=0)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
