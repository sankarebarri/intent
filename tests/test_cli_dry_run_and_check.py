# test_cli_dry_run_and_check.py
from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from intent.cli import app
from intent.config import load_intent
from intent.render_ci import render_ci
from intent.render_just import render_just

runner = CliRunner()


def write_intent(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "intent.toml"
    path.write_text(content, encoding="utf-8")
    return path


def test_sync_dry_run_does_not_write_files(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    write_intent(
        tmp_path,
        """
        [python]
        version = "3.12"

        [commands]
        test = "pytest -q"
        """,
    )

    result = runner.invoke(app, ["sync", "--dry-run"])
    assert result.exit_code == 0

    assert not (tmp_path / ".github").exists()
    assert not (tmp_path / "justfile").exists()


def test_check_fails_when_generated_files_missing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    write_intent(
        tmp_path,
        """
        [python]
        version = "3.12"

        [commands]
        test = "pytest -q"
        """,
    )

    result = runner.invoke(app, ["check"])
    assert result.exit_code == 1
    assert "is missing" in result.output


def test_check_passes_when_generated_files_in_sync(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    intent_path = write_intent(
        tmp_path,
        """
        [python]
        version = "3.12"

        [commands]
        test = "pytest -q"
        """,
    )

    cfg = load_intent(intent_path)

    # create tool-owned generated files matching our renderers’ marker rule
    (tmp_path / ".github/workflows").mkdir(parents=True)
    (tmp_path / ".github/workflows/ci.yml").write_text(render_ci(cfg), encoding="utf-8")
    (tmp_path / "justfile").write_text(render_just(cfg), encoding="utf-8")

    result = runner.invoke(app, ["check"])
    assert result.exit_code == 0


def test_check_fails_if_generated_file_exists_but_not_owned(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    write_intent(
        tmp_path,
        """
        [python]
        version = "3.12"

        [commands]
        test = "pytest -q"
        """,
    )

    (tmp_path / ".github/workflows").mkdir(parents=True)
    (tmp_path / ".github/workflows/ci.yml").write_text("name: CI\non: [push]\n", encoding="utf-8")

    result = runner.invoke(app, ["check"])
    assert result.exit_code == 1
    assert "not tool-owned" in result.output
