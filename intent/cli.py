from __future__ import annotations

from pathlib import Path

import typer

from .config import IntentConfigError, load_intent
from .pyproject_reader import read_pyproject_python

app = typer.Typer(help="Intent CLI")

from .render_ci import render_ci

def _parse_version(version: str) -> tuple[int, ...] | None:
    """
    Parse a version string like '3.12 into a tuple (3, 12).
    """
    parts: list[int] = []
    for part in version.split("."):
        part = part.strip()
        if not part:
            break
        if not part.isdigit():
            return None
        parts.append(int(part))
    if not parts:
        return None
    return tuple(parts)


def _check_requires_python_range(intent_version: str, spec: str) -> bool | None:
    """
    Basic, best-effort checker for common patterns:
    '>=3.10,<3.13'
    '>=3.11'
    '<3.13'

    Returns:
      True -> intent_version appears to satisfy the spec
      False -> intent_version does NOT satisfy the spec
      None -> spec use patterns we don't hanlde yet
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
            bound = c[2:].strip()
            bound_parsed = _parse_version(bound)
            if bound_parsed is None:
                supported = False
                continue
            if intent_parsed < bound_parsed:
                ok = False
        elif c.startswith("<"):
            bound = c[1:].strip()
            bound_parsed = _parse_version(bound)
            if bound_parsed is None:
                supported = False
                continue
            if not intent_parsed < bound_parsed:
                ok = False
        else:
            # we don't handle this kind of constraint yet (e.g. ~=, ==, <=)
            supported = False
    if not supported:
        return None
    return ok


@app.callback()
def callback():
    """Intent CLI"""
    pass


@app.command()
def sync(intent_path: str = "intent.toml", show_ci: bool = False) -> None:
    """
    Main command for now: show config + Python versions.
    Later: will generate CI + justfile.
    """
    path = Path(intent_path)

    try:
        cfg = load_intent(path)
    except FileNotFoundError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)
    except IntentConfigError as e:
        typer.echo(f"Config error: {e}", err=True)
        raise typer.Exit(code=1)

    # From intent.toml
    typer.echo(f"Intent python version: {cfg.python_version}")
    typer.echo("Intent commands:")
    for name, cmd in cfg.commands.items():
        typer.echo(f"  {name} -> {cmd}")

    # From pyproject.toml (if any)
    pyproject_version = read_pyproject_python()
    if pyproject_version is None:
        typer.echo("pyproject: requires_python not found")
    else:
        typer.echo(f"pyproject requires_python: {pyproject_version}")

        # Consistency checks
        spec = pyproject_version.strip()

        # Case 1: simple spec (no range operators) → strict equality
        if not any(ch in spec for ch in "<>,="):
            if spec != cfg.python_version:
                typer.echo(
                    "Version mismatch (simple spec):\n"
                    f"  intent.toml python.version = {cfg.python_version}\n"
                    f"  pyproject.toml requires_python = {spec}",
                    err=True,
                )
                raise typer.Exit(code=1)
            # no return here: allow show_ci to run

        # Case 2: range-like spec → try a basic best-effort check
        else:
            result = _check_requires_python_range(cfg.python_version, spec)
            if result is True:
                typer.echo(
                    f"Version check (range): {cfg.python_version} appears to satisfy "
                    f"requires_python = {spec} (basic check)"
                )
            elif result is False:
                typer.echo(
                    "Version mismatch (range):\n"
                    f"  intent.toml python.version = {cfg.python_version}\n"
                    f"  pyproject.toml requires_python = {spec}",
                    err=True,
                )
                raise typer.Exit(code=1)
            else:
                typer.echo(
                    "note: requires_python uses a complex or unsupported pattern; "
                    "skipping detailed compatibility check for now"
                )

    # CI preview (optional)
    if show_ci:
        typer.echo("\n--- ci.yml (preview) ---\n")
        typer.echo(render_ci(cfg))


if __name__ == "__main__":
    app()
