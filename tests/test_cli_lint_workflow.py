from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from intent.cli import app

runner = CliRunner()


def write_intent(tmp_path: Path, content: str) -> None:
    (tmp_path / "intent.toml").write_text(content, encoding="utf-8")


def test_lint_workflow_warns_for_custom_job_without_checkout(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    write_intent(
        tmp_path,
        """
        [python]
        version = "3.12"

        [commands]
        test = "pytest -q"

        [[ci.jobs]]
        name = "test"
        steps = [{ command = "test" }]
        """,
    )
    result = runner.invoke(app, ["lint-workflow"])
    assert result.exit_code == 0
    assert "[INTENT501] Warning:" in result.output
    assert "has no checkout step" in result.output


def test_lint_workflow_strict_fails_when_warnings_found(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    write_intent(
        tmp_path,
        """
        [python]
        version = "3.12"

        [commands]
        test = "pytest -q"

        [[ci.jobs]]
        name = "test"
        steps = [{ command = "test" }]
        """,
    )
    result = runner.invoke(app, ["lint-workflow", "--strict"])
    assert result.exit_code == 1
    assert "[INTENT501] Warning:" in result.output


def test_lint_workflow_passes_when_no_warnings(tmp_path: Path, monkeypatch) -> None:
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
    result = runner.invoke(app, ["lint-workflow"])
    assert result.exit_code == 0
    assert "No workflow lint warnings." in result.output
