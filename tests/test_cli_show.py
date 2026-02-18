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


def test_show_json_includes_ci_jobs_when_configured(tmp_path: Path, monkeypatch) -> None:
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

    result = runner.invoke(app, ["show", "--format", "json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert len(data["ci_jobs"]) == 1
    assert data["ci_jobs"][0]["name"] == "test"


def test_show_json_includes_ci_artifacts_when_configured(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    write_intent(
        tmp_path,
        """
        [python]
        version = "3.12"

        [commands]
        test = "pytest -q"

        [ci]
        artifacts = [{ name = "logs", path = "logs/**", when = "on-success" }]
        """,
    )

    result = runner.invoke(app, ["show", "--format", "json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert len(data["ci_artifacts"]) == 1
    assert data["ci_artifacts"][0]["name"] == "logs"


def test_show_json_includes_ci_summary_when_configured(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    write_intent(
        tmp_path,
        """
        [python]
        version = "3.12"

        [commands]
        eval = "cat metrics.json"

        [ci.summary]
        enabled = true
        title = "Quality"
        metrics = [{ label = "score", command = "eval", path = "metrics.score" }]
        """,
    )

    result = runner.invoke(app, ["show", "--format", "json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["ci_summary"]["enabled"] is True
    assert data["ci_summary"]["title"] == "Quality"


def test_show_json_includes_ci_summary_baseline_when_configured(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    write_intent(
        tmp_path,
        """
        [python]
        version = "3.12"

        [commands]
        eval = "cat metrics.json"

        [ci.summary]
        metrics = [{ label = "score", command = "eval", path = "metrics.score", baseline_path = "metrics.score" }]

        [ci.summary.baseline]
        source = "file"
        file = "baseline.json"
        on_missing = "skip"
        """,
    )
    result = runner.invoke(app, ["show", "--format", "json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["ci_summary"]["baseline"]["source"] == "file"
    assert data["ci_summary"]["baseline"]["file"] == "baseline.json"
    assert data["ci_summary"]["baseline"]["on_missing"] == "skip"


def test_show_json_includes_gates_when_configured(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    write_intent(
        tmp_path,
        """
        [python]
        version = "3.12"

        [commands]
        audit = "cat audit.json"

        [checks]
        gates = [{ kind = "threshold", command = "audit", path = "migrations.pending", max = 0 }]
        """,
    )

    result = runner.invoke(app, ["show", "--format", "json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert len(data["gates"]) == 1
    assert data["gates"][0]["kind"] == "threshold"
