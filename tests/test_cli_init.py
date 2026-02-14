from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from intent.cli import app

runner = CliRunner()


def write_pyproject(tmp_path: Path, content: str) -> None:
    (tmp_path / "pyproject.toml").write_text(content, encoding="utf-8")


def test_init_creates_default_intent_file(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0

    content = (tmp_path / "intent.toml").read_text(encoding="utf-8")
    assert '[python]' in content
    assert 'version = "3.12"' in content
    assert '[commands]' in content


def test_init_from_existing_infers_python_from_pyproject_lower_bound(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    write_pyproject(
        tmp_path,
        """
        [project]
        name = "x"
        version = "0.0.0"
        requires-python = ">=3.11,<3.13"
        """,
    )

    result = runner.invoke(app, ["init", "--from-existing"])
    assert result.exit_code == 0

    content = (tmp_path / "intent.toml").read_text(encoding="utf-8")
    assert 'version = "3.11"' in content
    assert "(pyproject)" in result.output


def test_init_refuses_overwrite_without_force(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "intent.toml").write_text("[python]\nversion='3.10'\n", encoding="utf-8")

    result = runner.invoke(app, ["init"])
    assert result.exit_code == 2
    assert "[INTENT005]" in result.output


def test_init_force_overwrites_existing_file(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "intent.toml").write_text("[python]\nversion='3.10'\n", encoding="utf-8")

    result = runner.invoke(app, ["init", "--force"])
    assert result.exit_code == 0

    content = (tmp_path / "intent.toml").read_text(encoding="utf-8")
    assert 'version = "3.12"' in content
