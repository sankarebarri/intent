from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from intent.cli import app

runner = CliRunner()


def write_intent(tmp_path: Path, content: str) -> None:
    (tmp_path / "intent.toml").write_text(content, encoding="utf-8")


def write_pyproject(tmp_path: Path, content: str) -> None:
    (tmp_path / "pyproject.toml").write_text(content, encoding="utf-8")


def test_check_warns_when_pyproject_requires_python_is_broader(tmp_path: Path, monkeypatch) -> None:
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
    write_pyproject(
        tmp_path,
        """
        [project]
        name = "x"
        version = "0.0.0"
        requires-python = ">=2"
        """,
    )

    # Generate tool-owned files so `check` doesn't fail for "missing generated files".
    res_sync = runner.invoke(app, ["sync", "--write"])
    assert res_sync.exit_code == 0

    result = runner.invoke(app, ["check"])
    assert result.exit_code == 0
    assert "broader than intent" in result.output
    assert "note:" in result.output


def test_check_strict_fails_when_pyproject_requires_python_is_broader(
    tmp_path: Path, monkeypatch
) -> None:
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
    write_pyproject(
        tmp_path,
        """
        [project]
        name = "x"
        version = "0.0.0"
        requires-python = ">=2"
        """,
    )

    # Generate tool-owned files first (same reason as above).
    res_sync = runner.invoke(app, ["sync", "--write"])
    assert res_sync.exit_code == 0

    result = runner.invoke(app, ["check", "--strict"])
    assert result.exit_code == 1
    assert "broader than intent" in result.output
