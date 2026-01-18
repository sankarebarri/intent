from __future__ import annotations

from pathlib import Path
import typer

from .config import IntentConfigError, load_intent

app = typer.Typer(help="Intent tool CLI (MVP stub)")

@app.command()
def main(intent_path: str = "intent.toml") -> None:
    """For now: load intent.toml and print the raw data."""
    path = Path(intent_path)
    try:
        cfg = load_intent(path)
    except FileNotFoundError as e:
        typer.echo(f"Error: {e}", err=True)
        raise type.Exit(code=1)
    except IntentConfigError as e:
        typer.echo(f"Config error: {e}", err=True)
        raise typer.Exit(code=1)
    
    typer.echo(f"Python version: {cfg.python_version}")
    typer.echo(f"Commands:")
    for name, cmd in cfg.commands.items():
        typer.echo(f"   {name} -> {cmd}")

# def run() -> None:
#     app()

if __name__ == "__main__":
    type.run(main)
