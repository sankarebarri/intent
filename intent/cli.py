from __future__ import annotations

from pathlib import Path

import typer

from .config import IntentConfigError, load_intent
from .pyproject_reader import read_pyproject_python

app = typer.Typer(help="Intent CLI")

@app.callback()
def callback():
    """Intent CLI"""
    pass


@app.command()
def sync(intent_path: str = "intent.toml") -> None:
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


if __name__ == "__main__":
    app()
