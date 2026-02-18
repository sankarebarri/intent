# test_cli_dry_run_and_check.py
from __future__ import annotations

import json
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


def write_synced_generated_files(tmp_path: Path, intent_path: Path) -> None:
    cfg = load_intent(intent_path)
    (tmp_path / ".github/workflows").mkdir(parents=True)
    (tmp_path / ".github/workflows/ci.yml").write_text(render_ci(cfg), encoding="utf-8")
    (tmp_path / "justfile").write_text(render_just(cfg), encoding="utf-8")


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
    assert "Intent commands:" not in result.output

    assert not (tmp_path / ".github").exists()
    assert not (tmp_path / "justfile").exists()


def test_sync_missing_intent_shows_init_fix_hint(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["sync"])
    assert result.exit_code == 2
    assert "[INTENT002]" in result.output
    assert "Fix: run `intent init` to create a starter config." in result.output


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

    write_synced_generated_files(tmp_path, intent_path)

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


def test_sync_dry_run_reports_unowned_existing_file(tmp_path: Path, monkeypatch) -> None:
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

    (tmp_path / "justfile").write_text("default:\n\t@echo user-owned\n", encoding="utf-8")

    result = runner.invoke(app, ["sync", "--dry-run"])
    assert result.exit_code == 0
    assert "Cannot update justfile: exists but is not tool-owned (missing marker)" in result.output


def test_check_handles_invalid_pyproject_toml_non_strict(tmp_path: Path, monkeypatch) -> None:
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

    (tmp_path / "pyproject.toml").write_text("[project\n", encoding="utf-8")
    write_synced_generated_files(tmp_path, intent_path)

    result = runner.invoke(app, ["check"])
    assert result.exit_code == 0
    assert "note: invalid requires-python value; version cross-check skipped" in result.output


def test_check_handles_invalid_pyproject_toml_strict(tmp_path: Path, monkeypatch) -> None:
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

    (tmp_path / "pyproject.toml").write_text("[project\n", encoding="utf-8")
    write_synced_generated_files(tmp_path, intent_path)

    result = runner.invoke(app, ["check", "--strict"])
    assert result.exit_code == 1
    assert "[INTENT101]" in result.output
    assert "invalid requires-python value in pyproject.toml" in result.output


def test_check_json_output_success(tmp_path: Path, monkeypatch) -> None:
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

    write_synced_generated_files(tmp_path, intent_path)

    result = runner.invoke(app, ["check", "--format", "json"])
    assert result.exit_code == 0

    data = json.loads(result.output)
    assert data["ok"] is True
    assert data["versions"]["ok"] is True
    assert len(data["files"]) == 2
    assert all(entry["ok"] for entry in data["files"])


def test_check_json_output_drift(tmp_path: Path, monkeypatch) -> None:
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

    result = runner.invoke(app, ["check", "--format", "json"])
    assert result.exit_code == 1

    data = json.loads(result.output)
    assert data["ok"] is False
    assert any(entry["ok"] is False for entry in data["files"])


def test_check_json_output_config_error(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["check", "--format", "json"])
    assert result.exit_code == 2

    data = json.loads(result.output)
    assert data["ok"] is False
    assert data["code"] == "INTENT002"
    assert data["error"]["kind"] == "config"


def test_check_json_output_includes_stable_codes(tmp_path: Path, monkeypatch) -> None:
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

    result = runner.invoke(app, ["check", "--strict", "--format", "json"])
    assert result.exit_code == 1

    data = json.loads(result.output)
    assert data["ok"] is False
    assert data["versions"]["code"] is None
    assert data["files"][0]["code"] == "INTENT201"
    assert data["files"][1]["code"] == "INTENT201"


def test_sync_rejects_conflicting_write_and_dry_run_with_code(tmp_path: Path, monkeypatch) -> None:
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

    result = runner.invoke(app, ["sync", "--write", "--dry-run"])
    assert result.exit_code == 2
    assert "[INTENT001]" in result.output


def test_sync_rejects_conflicting_adopt_and_force(tmp_path: Path, monkeypatch) -> None:
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

    result = runner.invoke(app, ["sync", "--write", "--adopt", "--force"])
    assert result.exit_code == 2
    assert "[INTENT001]" in result.output


def test_sync_rejects_adopt_without_write(tmp_path: Path, monkeypatch) -> None:
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

    result = runner.invoke(app, ["sync", "--adopt"])
    assert result.exit_code == 2
    assert "[INTENT001]" in result.output


def test_sync_show_json_outputs_resolved_payload(tmp_path: Path, monkeypatch) -> None:
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
    result = runner.invoke(app, ["sync", "--show-json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["ok"] is True
    assert data["python_version"] == "3.12"
    assert data["sync"]["show_json"] is True
    assert data["sync"]["generated"]["ci"] == ".github/workflows/ci.yml"


def test_sync_show_json_with_explain_includes_mapping(tmp_path: Path, monkeypatch) -> None:
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
    result = runner.invoke(app, ["sync", "--show-json", "--explain"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    explain = data["sync"]["explain_map"]
    assert explain is not None
    assert explain["generated_files"][0]["path"] == ".github/workflows/ci.yml"


def test_sync_explain_outputs_text_mapping(tmp_path: Path, monkeypatch) -> None:
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
    result = runner.invoke(app, ["sync", "--explain"])
    assert result.exit_code == 0
    assert "--- explain ---" in result.output
    assert "renderer: render_ci" in result.output
    assert "renderer: render_just" in result.output


def test_sync_rejects_show_json_with_write(tmp_path: Path, monkeypatch) -> None:
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
    result = runner.invoke(app, ["sync", "--show-json", "--write"])
    assert result.exit_code == 2
    assert "[INTENT001]" in result.output


def test_check_with_assertions_passes(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "metrics.json").write_text(
        '{"metrics":{"score":0.95},"status":"ok"}',
        encoding="utf-8",
    )
    intent_path = write_intent(
        tmp_path,
        """
        [python]
        version = "3.12"

        [commands]
        eval = "cat metrics.json"

        [checks]
        assertions = [
          { command = "eval", path = "metrics.score", op = "gte", value = 0.9 },
          { command = "eval", path = "status", op = "in", value = ["ok", "warn"] }
        ]
        """,
    )
    write_synced_generated_files(tmp_path, intent_path)

    result = runner.invoke(app, ["check"])
    assert result.exit_code == 0
    assert "check assertion (eval): metrics.score gte 0.9" in result.output
    assert "check assertion (eval): status in ['ok', 'warn']" in result.output


def test_check_with_assertions_fails_when_threshold_misses(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "metrics.json").write_text('{"metrics":{"score":0.80}}', encoding="utf-8")
    intent_path = write_intent(
        tmp_path,
        """
        [python]
        version = "3.12"

        [commands]
        eval = "cat metrics.json"

        [[checks.assertions]]
        command = "eval"
        path = "metrics.score"
        op = "gte"
        value = 0.9
        message = "score regression gate"
        """,
    )
    write_synced_generated_files(tmp_path, intent_path)

    result = runner.invoke(app, ["check"])
    assert result.exit_code == 1
    assert "[INTENT401]" in result.output
    assert "score regression gate" in result.output


def test_check_json_output_includes_assertion_failures(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "metrics.json").write_text('{"metrics":{"score":0.80}}', encoding="utf-8")
    intent_path = write_intent(
        tmp_path,
        """
        [python]
        version = "3.12"

        [commands]
        eval = "cat metrics.json"

        [checks]
        assertions = [
          { command = "eval", path = "metrics.score", op = "gte", value = 0.9 }
        ]
        """,
    )
    write_synced_generated_files(tmp_path, intent_path)

    result = runner.invoke(app, ["check", "--format", "json"])
    assert result.exit_code == 1
    data = json.loads(result.output)
    assert data["ok"] is False
    assert data["checks"][0]["ok"] is False
    assert data["checks"][0]["code"] == "INTENT401"


def test_check_json_output_includes_summary_metrics_delta(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "metrics.json").write_text(
        '{"metrics":{"score":0.91,"baseline_score":0.89}}',
        encoding="utf-8",
    )
    intent_path = write_intent(
        tmp_path,
        """
        [python]
        version = "3.12"

        [commands]
        eval = "cat metrics.json"

        [ci.summary]
        enabled = true
        title = "Quality"

        [[ci.summary.metrics]]
        label = "score"
        command = "eval"
        path = "metrics.score"
        baseline_path = "metrics.baseline_score"
        precision = 3
        """,
    )
    write_synced_generated_files(tmp_path, intent_path)

    result = runner.invoke(app, ["check", "--format", "json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["report"]["summary_enabled"] is True
    assert data["report"]["summary_markdown"] is not None
    assert data["report"]["metrics"][0]["label"] == "score"
    assert data["report"]["metrics"][0]["delta"] == 0.02


def test_check_json_output_fails_on_invalid_summary_metric_path(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "metrics.json").write_text('{"metrics":{"score":0.91}}', encoding="utf-8")
    intent_path = write_intent(
        tmp_path,
        """
        [python]
        version = "3.12"

        [commands]
        eval = "cat metrics.json"

        [ci.summary]
        enabled = true
        metrics = [
          { label = "score", command = "eval", path = "metrics.missing" }
        ]
        """,
    )
    write_synced_generated_files(tmp_path, intent_path)

    result = runner.invoke(app, ["check", "--format", "json"])
    assert result.exit_code == 1
    data = json.loads(result.output)
    assert data["ok"] is False
    assert data["report"]["metrics"][0]["ok"] is False


def test_check_json_summary_metric_uses_file_baseline(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "metrics.json").write_text('{"metrics":{"score":0.93}}', encoding="utf-8")
    (tmp_path / "baseline.json").write_text('{"metrics":{"score":0.90}}', encoding="utf-8")
    intent_path = write_intent(
        tmp_path,
        """
        [python]
        version = "3.12"

        [commands]
        eval = "cat metrics.json"

        [ci.summary]
        [[ci.summary.metrics]]
        label = "score"
        command = "eval"
        path = "metrics.score"
        baseline_path = "metrics.score"
        precision = 3

        [ci.summary.baseline]
        source = "file"
        file = "baseline.json"
        on_missing = "fail"
        """,
    )
    write_synced_generated_files(tmp_path, intent_path)
    result = runner.invoke(app, ["check", "--format", "json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["report"]["metrics"][0]["delta"] == 0.03


def test_check_json_summary_metric_missing_file_baseline_fails(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "metrics.json").write_text('{"metrics":{"score":0.93}}', encoding="utf-8")
    intent_path = write_intent(
        tmp_path,
        """
        [python]
        version = "3.12"

        [commands]
        eval = "cat metrics.json"

        [ci.summary]
        [[ci.summary.metrics]]
        label = "score"
        command = "eval"
        path = "metrics.score"
        baseline_path = "metrics.score"
        precision = 3

        [ci.summary.baseline]
        source = "file"
        file = "missing-baseline.json"
        on_missing = "fail"
        """,
    )
    write_synced_generated_files(tmp_path, intent_path)
    result = runner.invoke(app, ["check", "--format", "json"])
    assert result.exit_code == 1
    data = json.loads(result.output)
    assert data["report"]["metrics"][0]["ok"] is False
    assert "baseline source unavailable" in data["report"]["metrics"][0]["reason"]


def test_check_json_summary_metric_missing_file_baseline_skip_mode(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "metrics.json").write_text('{"metrics":{"score":0.93}}', encoding="utf-8")
    intent_path = write_intent(
        tmp_path,
        """
        [python]
        version = "3.12"

        [commands]
        eval = "cat metrics.json"

        [ci.summary]
        [[ci.summary.metrics]]
        label = "score"
        command = "eval"
        path = "metrics.score"
        baseline_path = "metrics.score"
        precision = 3

        [ci.summary.baseline]
        source = "file"
        file = "missing-baseline.json"
        on_missing = "skip"
        """,
    )
    write_synced_generated_files(tmp_path, intent_path)
    result = runner.invoke(app, ["check", "--format", "json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["report"]["metrics"][0]["ok"] is True
    assert data["report"]["metrics"][0]["delta"] is None
    assert "baseline source unavailable" in data["report"]["metrics"][0]["reason"]


def test_check_groups_repeated_command_failures_for_assertions(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    intent_path = write_intent(
        tmp_path,
        """
        [python]
        version = "3.12"

        [commands]
        eval = "sh -c 'exit 2'"

        [checks]
        assertions = [
          { command = "eval", path = "metrics.score", op = "gte", value = 0.9 },
          { command = "eval", path = "status", op = "eq", value = "ok" }
        ]
        """,
    )
    write_synced_generated_files(tmp_path, intent_path)

    result = runner.invoke(app, ["check"])
    assert result.exit_code == 1
    assert "failed before evaluation" in result.output
    assert "affected assertions: 2" in result.output


def test_check_json_keeps_full_results_when_command_failures_are_grouped_in_text(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    intent_path = write_intent(
        tmp_path,
        """
        [python]
        version = "3.12"

        [commands]
        eval = "sh -c 'exit 2'"

        [checks]
        assertions = [
          { command = "eval", path = "metrics.score", op = "gte", value = 0.9 },
          { command = "eval", path = "status", op = "eq", value = "ok" }
        ]

        [ci.summary]
        enabled = true
        metrics = [
          { label = "score", command = "eval", path = "metrics.score" },
          { label = "status_ok", command = "eval", path = "status.ok" }
        ]
        """,
    )
    write_synced_generated_files(tmp_path, intent_path)

    result = runner.invoke(app, ["check", "--format", "json"])
    assert result.exit_code == 1
    data = json.loads(result.output)
    assert len(data["checks"]) == 2
    assert all(item["ok"] is False for item in data["checks"])
    assert len(data["report"]["metrics"]) == 2
    assert all(item["ok"] is False for item in data["report"]["metrics"])


def test_check_with_gates_passes_and_fails_as_expected(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "audit.json").write_text(
        '{"migrations":{"pending":0},"checks":{"warnings":2},"status":"ok"}',
        encoding="utf-8",
    )
    intent_path = write_intent(
        tmp_path,
        """
        [python]
        version = "3.12"

        [commands]
        audit = "cat audit.json"

        [[checks.gates]]
        name = "migrations"
        kind = "threshold"
        command = "audit"
        path = "migrations.pending"
        max = 0

        [[checks.gates]]
        name = "warnings"
        kind = "threshold"
        command = "audit"
        path = "checks.warnings"
        max = 5

        [[checks.gates]]
        name = "status"
        kind = "equals"
        command = "audit"
        path = "status"
        value = "ok"
        """,
    )
    write_synced_generated_files(tmp_path, intent_path)
    result = runner.invoke(app, ["check"])
    assert result.exit_code == 0

    (tmp_path / "audit.json").write_text(
        '{"migrations":{"pending":1},"checks":{"warnings":9},"status":"bad"}',
        encoding="utf-8",
    )
    result = runner.invoke(app, ["check"])
    assert result.exit_code == 1
    assert "[INTENT401]" in result.output


def test_check_uses_policy_strict_by_default(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    intent_path = write_intent(
        tmp_path,
        """
        [python]
        version = "3.12"

        [commands]
        test = "pytest -q"

        [policy]
        strict = true
        """,
    )

    (tmp_path / "pyproject.toml").write_text("[project\n", encoding="utf-8")
    cfg = load_intent(intent_path)
    (tmp_path / ".github/workflows").mkdir(parents=True)
    (tmp_path / ".github/workflows/ci.yml").write_text(render_ci(cfg), encoding="utf-8")
    (tmp_path / "justfile").write_text(render_just(cfg), encoding="utf-8")

    result = runner.invoke(app, ["check"])
    assert result.exit_code == 1
    assert "[INTENT101]" in result.output


def test_check_can_override_policy_strict_with_no_strict(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    intent_path = write_intent(
        tmp_path,
        """
        [python]
        version = "3.12"

        [commands]
        test = "pytest -q"

        [policy]
        strict = true
        """,
    )

    (tmp_path / "pyproject.toml").write_text("[project\n", encoding="utf-8")
    cfg = load_intent(intent_path)
    (tmp_path / ".github/workflows").mkdir(parents=True)
    (tmp_path / ".github/workflows/ci.yml").write_text(render_ci(cfg), encoding="utf-8")
    (tmp_path / "justfile").write_text(render_just(cfg), encoding="utf-8")

    result = runner.invoke(app, ["check", "--no-strict"])
    assert result.exit_code == 0
    assert "note: invalid requires-python value; version cross-check skipped" in result.output


def test_check_uses_policy_pack_strict_by_default(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    intent_path = write_intent(
        tmp_path,
        """
        [python]
        version = "3.12"

        [commands]
        test = "pytest -q"

        [policy]
        pack = "strict"
        """,
    )

    (tmp_path / "pyproject.toml").write_text("[project\n", encoding="utf-8")
    cfg = load_intent(intent_path)
    (tmp_path / ".github/workflows").mkdir(parents=True)
    (tmp_path / ".github/workflows/ci.yml").write_text(render_ci(cfg), encoding="utf-8")
    (tmp_path / "justfile").write_text(render_just(cfg), encoding="utf-8")

    result = runner.invoke(app, ["check"])
    assert result.exit_code == 1
    assert "[INTENT101]" in result.output


def test_sync_write_with_adopt_rejects_unowned_different_file(tmp_path: Path, monkeypatch) -> None:
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
    (tmp_path / "justfile").write_text("default:\n\t@echo user-owned\n", encoding="utf-8")

    result = runner.invoke(app, ["sync", "--write", "--adopt"])
    assert result.exit_code == 1
    assert "[INTENT004]" in result.output
    assert "Refusing to adopt" in result.output


def test_sync_write_with_force_overwrites_unowned_file(tmp_path: Path, monkeypatch) -> None:
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
    (tmp_path / "justfile").write_text("default:\n\t@echo user-owned\n", encoding="utf-8")

    result = runner.invoke(app, ["sync", "--write", "--force"])
    assert result.exit_code == 0
    assert "Intent commands:" not in result.output
    cfg = load_intent(intent_path)
    assert (tmp_path / "justfile").read_text(encoding="utf-8") == render_just(cfg)


def test_check_runs_plugin_check_hooks_and_fails_on_error(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    intent_path = write_intent(
        tmp_path,
        """
        [python]
        version = "3.12"

        [commands]
        test = "pytest -q"

        [plugins]
        check = ["echo plugin-ok", "echo plugin-bad 1>&2; exit 7"]
        """,
    )

    cfg = load_intent(intent_path)
    (tmp_path / ".github/workflows").mkdir(parents=True)
    (tmp_path / ".github/workflows/ci.yml").write_text(render_ci(cfg), encoding="utf-8")
    (tmp_path / "justfile").write_text(render_just(cfg), encoding="utf-8")

    result = runner.invoke(app, ["check"])
    assert result.exit_code == 1
    assert "✓ plugin check: echo plugin-ok" in result.output
    assert "[INTENT301]" in result.output
    assert "plugin check failed (7)" in result.output
    assert "stderr: plugin-bad" in result.output


def test_check_json_includes_plugin_results(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    intent_path = write_intent(
        tmp_path,
        """
        [python]
        version = "3.12"

        [commands]
        test = "pytest -q"

        [plugins]
        check = ["echo plugin-ok", "echo plugin-bad 1>&2; exit 5"]
        """,
    )

    cfg = load_intent(intent_path)
    (tmp_path / ".github/workflows").mkdir(parents=True)
    (tmp_path / ".github/workflows/ci.yml").write_text(render_ci(cfg), encoding="utf-8")
    (tmp_path / "justfile").write_text(render_just(cfg), encoding="utf-8")

    result = runner.invoke(app, ["check", "--format", "json"])
    assert result.exit_code == 1

    data = json.loads(result.output)
    assert data["ok"] is False
    assert len(data["plugins"]) == 2
    assert data["plugins"][0]["ok"] is True
    assert data["plugins"][1]["ok"] is False
    assert data["plugins"][1]["code"] == "INTENT301"
    assert data["plugins"][1]["stderr"] == "plugin-bad"


def test_sync_write_runs_plugin_generate_hooks_and_fails_on_error(
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

        [plugins]
        generate = ["echo gen-ok", "echo gen-bad 1>&2; exit 9"]
        """,
    )

    result = runner.invoke(app, ["sync", "--write"])
    assert result.exit_code == 1
    assert "✓ plugin generate: echo gen-ok" in result.output
    assert "[INTENT301]" in result.output
    assert "plugin generate failed (9)" in result.output
    assert "stderr: gen-bad" in result.output
