from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from intent.cli import app

runner = CliRunner()


def write_intent(tmp_path: Path, content: str) -> None:
    (tmp_path / "intent.toml").write_text(content, encoding="utf-8")


def test_show_text_outputs_resolved_config(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    write_intent(
        tmp_path,
        """
        [intent]
        schema_version = 1

        [python]
        version = "3.12"

        [commands]
        test = "pytest -q"

        [policy]
        pack = "strict"
        strict = true
        """,
    )

    result = runner.invoke(app, ["show"])
    assert result.exit_code == 0
    assert "Schema version: 1" in result.output
    assert "Python version: 3.12" in result.output
    assert "Policy pack: strict" in result.output
    assert "Policy strict: True" in result.output
    assert "Commands:" in result.output


def test_show_json_outputs_machine_readable_payload(tmp_path: Path, monkeypatch) -> None:
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

    result = runner.invoke(app, ["show", "--format", "json"])
    assert result.exit_code == 0

    data = json.loads(result.output)
    assert data["ok"] is True
    assert data["schema_version"] == 1
    assert data["python_version"] == "3.12"
    assert data["policy_pack"] is None
    assert data["policy_strict"] is False
    assert data["commands"]["test"] == "pytest -q"
    assert "status" in data["pyproject"]


def test_show_json_missing_intent_returns_error_code(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["show", "--format", "json"])
    assert result.exit_code == 2

    data = json.loads(result.output)
    assert data["ok"] is False
    assert data["code"] == "INTENT002"
