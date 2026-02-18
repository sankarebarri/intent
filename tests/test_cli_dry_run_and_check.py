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
    cfg = load_intent(intent_path)
    (tmp_path / ".github/workflows").mkdir(parents=True)
    (tmp_path / ".github/workflows/ci.yml").write_text(render_ci(cfg), encoding="utf-8")
    (tmp_path / "justfile").write_text(render_just(cfg), encoding="utf-8")

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
    cfg = load_intent(intent_path)
    (tmp_path / ".github/workflows").mkdir(parents=True)
    (tmp_path / ".github/workflows/ci.yml").write_text(render_ci(cfg), encoding="utf-8")
    (tmp_path / "justfile").write_text(render_just(cfg), encoding="utf-8")

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

    cfg = load_intent(intent_path)
    (tmp_path / ".github/workflows").mkdir(parents=True)
    (tmp_path / ".github/workflows/ci.yml").write_text(render_ci(cfg), encoding="utf-8")
    (tmp_path / "justfile").write_text(render_just(cfg), encoding="utf-8")

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
