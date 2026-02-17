from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from intent.cli import app

runner = CliRunner()


def write_intent(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "intent.toml"
    path.write_text(content, encoding="utf-8")
    return path


def test_reconcile_requires_plan_flag(tmp_path: Path, monkeypatch) -> None:
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

    result = runner.invoke(app, ["reconcile"])
    assert result.exit_code == 2
    assert "choose exactly one of --plan or --apply" in result.output


def test_reconcile_rejects_plan_and_apply_together(tmp_path: Path, monkeypatch) -> None:
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

    result = runner.invoke(app, ["reconcile", "--plan", "--apply"])
    assert result.exit_code == 2
    assert "choose exactly one of --plan or --apply" in result.output


def test_reconcile_plan_reports_aligned_files(tmp_path: Path, monkeypatch) -> None:
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
    (tmp_path / "pyproject.toml").write_text(
        """
        [project]
        name = "demo"
        version = "0.1.0"
        requires-python = ">=3.12,<3.13"
        """,
        encoding="utf-8",
    )
    (tmp_path / ".python-version").write_text("3.12.6\n", encoding="utf-8")
    (tmp_path / ".tool-versions").write_text("python 3.12.4\n", encoding="utf-8")

    result = runner.invoke(app, ["reconcile", "--plan"])
    assert result.exit_code == 0
    assert "Target python version (from intent): 3.12" in result.output
    assert "pyproject.toml: aligned" in result.output
    assert ".python-version: aligned" in result.output
    assert ".tool-versions: aligned" in result.output
    assert "No files were modified" in result.output


def test_reconcile_plan_reports_actions_for_drift_and_missing(tmp_path: Path, monkeypatch) -> None:
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
    (tmp_path / "pyproject.toml").write_text(
        """
        [project]
        name = "demo"
        version = "0.1.0"
        requires-python = ">=3.11,<3.13"
        """,
        encoding="utf-8",
    )
    (tmp_path / ".python-version").write_text("3.11.9\n", encoding="utf-8")

    result = runner.invoke(app, ["reconcile", "--plan"])
    assert result.exit_code == 0
    assert "pyproject.toml: drift" in result.output
    assert "set requires-python = >=3.12,<3.13" in result.output
    assert ".python-version: drift (3.11.9)" in result.output
    assert "replace with 3.12" in result.output
    assert ".tool-versions: missing or no python entry" in result.output
    assert "add `python 3.12`" in result.output


def test_reconcile_apply_creates_missing_files(tmp_path: Path, monkeypatch) -> None:
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

    result = runner.invoke(app, ["reconcile", "--apply"])
    assert result.exit_code == 0
    assert "Reconcile apply completed." in result.output
    assert (tmp_path / ".python-version").read_text(encoding="utf-8") == "3.12\n"
    assert (tmp_path / ".tool-versions").read_text(encoding="utf-8") == "python 3.12\n"
    pyproject = (tmp_path / "pyproject.toml").read_text(encoding="utf-8")
    assert 'requires-python = ">=3.12,<3.13"' in pyproject


def test_reconcile_apply_skips_existing_without_allow_existing(tmp_path: Path, monkeypatch) -> None:
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
    (tmp_path / "pyproject.toml").write_text(
        """
        [project]
        name = "demo"
        version = "0.1.0"
        requires-python = ">=3.11,<3.13"
        """,
        encoding="utf-8",
    )
    (tmp_path / ".python-version").write_text("3.11.8\n", encoding="utf-8")
    (tmp_path / ".tool-versions").write_text("python 3.11.9\n", encoding="utf-8")

    result = runner.invoke(app, ["reconcile", "--apply"])
    assert result.exit_code == 1
    assert "use --allow-existing" in result.output
    assert "Reconcile apply completed with skips" in result.output
    assert (tmp_path / ".python-version").read_text(encoding="utf-8") == "3.11.8\n"
    assert (tmp_path / ".tool-versions").read_text(encoding="utf-8") == "python 3.11.9\n"
    pyproject = (tmp_path / "pyproject.toml").read_text(encoding="utf-8")
    assert 'requires-python = ">=3.11,<3.13"' in pyproject


def test_reconcile_apply_updates_existing_with_allow_existing(tmp_path: Path, monkeypatch) -> None:
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
    (tmp_path / "pyproject.toml").write_text(
        """
        [project]
        name = "demo"
        version = "0.1.0"
        requires-python = ">=3.11,<3.13"
        """,
        encoding="utf-8",
    )
    (tmp_path / ".python-version").write_text("3.11.8\n", encoding="utf-8")
    (tmp_path / ".tool-versions").write_text("python 3.11.9\n", encoding="utf-8")

    result = runner.invoke(app, ["reconcile", "--apply", "--allow-existing"])
    assert result.exit_code == 0
    assert "Reconcile apply completed." in result.output
    assert (tmp_path / ".python-version").read_text(encoding="utf-8") == "3.12\n"
    assert (tmp_path / ".tool-versions").read_text(encoding="utf-8") == "python 3.12\n"
    pyproject = (tmp_path / "pyproject.toml").read_text(encoding="utf-8")
    assert 'requires-python = ">=3.12,<3.13"' in pyproject
