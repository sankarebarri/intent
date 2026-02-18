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


def test_doctor_reports_missing_config_with_fix(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 2
    assert "[INTENT002]" in result.output
    assert "Fix: run `intent init`" in result.output


def test_doctor_reports_generated_file_drift_with_actionable_fix(tmp_path: Path, monkeypatch) -> None:
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

    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 1
    assert "[INTENT201]" in result.output
    assert "Fix: run `intent sync --write`." in result.output


def test_doctor_passes_when_generated_files_are_in_sync(tmp_path: Path, monkeypatch) -> None:
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
    (tmp_path / ".github/workflows").mkdir(parents=True)
    (tmp_path / ".github/workflows/ci.yml").write_text(render_ci(cfg), encoding="utf-8")
    (tmp_path / "justfile").write_text(render_just(cfg), encoding="utf-8")

    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "No issues found." in result.output
