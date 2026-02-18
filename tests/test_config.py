# test_config.py
from pathlib import (
    Path,
)

import pytest

from intent.config import (
    IntentConfigError,
    load_intent,
)


def write_intent(
    tmp_path: Path,
    content: str,
) -> Path:
    """Helper: write intent.toml in a temp directory and return its path"""
    path = tmp_path / "intent.toml"
    path.write_text(
        content,
        encoding="utf-8",
    )
    return path


def test_load_intent_valid(
    tmp_path: Path,
) -> None:
    path = write_intent(
        tmp_path,
        """
        [python]
        version = "3.12"

        [commands]
        test = "pytest -q"
        lint = "ruff check ."
        """,
    )
    cfg = load_intent(path)

    assert cfg.python_version == "3.12"
    assert cfg.commands == {
        "test": "pytest -q",
        "lint": "ruff check .",
    }
    assert cfg.schema_version == 1
    assert cfg.policy_strict is False


def test_load_intent_missing_python(
    tmp_path: Path,
) -> None:
    path = write_intent(
        tmp_path,
        """
        [commands]
        test = "pytest -q"        
        """,
    )

    with pytest.raises(IntentConfigError) as excinfo:
        load_intent(path)

    msg = str(excinfo.value)
    assert "intent.toml" in msg
    assert "invalid [python]" in msg
    assert "expected table/object" in msg
    assert "got null" in msg


def test_load_intent_ci_install_default(
    tmp_path: Path,
) -> None:
    path = write_intent(
        tmp_path,
        """
        [python]
        version = "3.12"

        [commands]
        test = "pytest -q"
        """,
    )
    cfg = load_intent(path)
    assert cfg.ci_install == "-e .[dev]"


def test_load_intent_ci_install_custom(
    tmp_path: Path,
) -> None:
    path = write_intent(
        tmp_path,
        """
        [python]
        version = "3.12"

        [commands]
        test = "pytest -q"

        [ci]
        install = ".[dev]"
        """,
    )
    cfg = load_intent(path)
    assert cfg.ci_install == ".[dev]"


def test_load_intent_ci_cache_custom(tmp_path: Path) -> None:
    path = write_intent(
        tmp_path,
        """
        [python]
        version = "3.12"

        [commands]
        test = "pytest -q"

        [ci]
        cache = "pip"
        """,
    )
    cfg = load_intent(path)
    assert cfg.ci_cache == "pip"


def test_load_intent_ci_cache_rejects_invalid_value(tmp_path: Path) -> None:
    path = write_intent(
        tmp_path,
        """
        [python]
        version = "3.12"

        [commands]
        test = "pytest -q"

        [ci]
        cache = "poetry"
        """,
    )
    with pytest.raises(IntentConfigError) as excinfo:
        load_intent(path)
    assert "invalid [ci].cache" in str(excinfo.value)


def test_load_intent_ci_python_versions_custom(tmp_path: Path) -> None:
    path = write_intent(
        tmp_path,
        """
        [python]
        version = "3.12"

        [commands]
        test = "pytest -q"

        [ci]
        python_versions = ["3.11", "3.12"]
        """,
    )
    cfg = load_intent(path)
    assert cfg.ci_python_versions == ["3.11", "3.12"]


def test_load_intent_ci_python_versions_rejects_invalid_type(tmp_path: Path) -> None:
    path = write_intent(
        tmp_path,
        """
        [python]
        version = "3.12"

        [commands]
        test = "pytest -q"

        [ci]
        python_versions = "3.12"
        """,
    )
    with pytest.raises(IntentConfigError) as excinfo:
        load_intent(path)
    assert "[ci].python_versions must be a non-empty array of strings" in str(excinfo.value)


def test_load_intent_ci_triggers_custom(tmp_path: Path) -> None:
    path = write_intent(
        tmp_path,
        """
        [python]
        version = "3.12"

        [commands]
        test = "pytest -q"

        [ci]
        triggers = ["push", "pull_request"]
        """,
    )
    cfg = load_intent(path)
    assert cfg.ci_triggers == ["push", "pull_request"]


def test_load_intent_ci_triggers_rejects_invalid_type(tmp_path: Path) -> None:
    path = write_intent(
        tmp_path,
        """
        [python]
        version = "3.12"

        [commands]
        test = "pytest -q"

        [ci]
        triggers = "push"
        """,
    )
    with pytest.raises(IntentConfigError) as excinfo:
        load_intent(path)
    assert "[ci].triggers must be a non-empty array of strings" in str(excinfo.value)


def test_load_intent_checks_assertions_valid(tmp_path: Path) -> None:
    path = write_intent(
        tmp_path,
        """
        [python]
        version = "3.12"

        [commands]
        eval = "cat metrics.json"

        [checks]
        assertions = [
          { command = "eval", path = "metrics.score", op = "gte", value = 0.9, message = "score gate" }
        ]
        """,
    )
    cfg = load_intent(path)
    assert cfg.checks_assertions is not None
    assertion = cfg.checks_assertions[0]
    assert assertion.command == "eval"
    assert assertion.path == "metrics.score"
    assert assertion.op == "gte"
    assert assertion.value == 0.9
    assert assertion.message == "score gate"


def test_load_intent_checks_assertions_rejects_unknown_command(tmp_path: Path) -> None:
    path = write_intent(
        tmp_path,
        """
        [python]
        version = "3.12"

        [commands]
        test = "pytest -q"

        [checks]
        assertions = [{ command = "eval", path = "metrics.score", op = "gte", value = 0.9 }]
        """,
    )
    with pytest.raises(IntentConfigError) as excinfo:
        load_intent(path)
    assert "unknown command" in str(excinfo.value)


def test_load_intent_checks_assertions_rejects_invalid_operator(tmp_path: Path) -> None:
    path = write_intent(
        tmp_path,
        """
        [python]
        version = "3.12"

        [commands]
        eval = "cat metrics.json"

        [checks]
        assertions = [{ command = "eval", path = "metrics.score", op = "between", value = 0.9 }]
        """,
    )
    with pytest.raises(IntentConfigError) as excinfo:
        load_intent(path)
    assert "invalid [checks].assertions[0].op" in str(excinfo.value)


def test_load_intent_checks_gates_valid(tmp_path: Path) -> None:
    path = write_intent(
        tmp_path,
        """
        [python]
        version = "3.12"

        [commands]
        audit = "cat audit.json"

        [checks]
        gates = [
          { name = "pending migrations", kind = "threshold", command = "audit", path = "migrations.pending", max = 0 },
          { kind = "equals", command = "audit", path = "status", value = "ok" }
        ]
        """,
    )
    cfg = load_intent(path)
    assert cfg.checks_gates is not None
    assert len(cfg.checks_gates) == 2
    assert cfg.checks_gates[0].kind == "threshold"
    assert cfg.checks_gates[1].kind == "equals"


def test_load_intent_checks_gates_rejects_invalid_kind(tmp_path: Path) -> None:
    path = write_intent(
        tmp_path,
        """
        [python]
        version = "3.12"

        [commands]
        audit = "cat audit.json"

        [checks]
        gates = [{ kind = "range", command = "audit", path = "status", value = "ok" }]
        """,
    )
    with pytest.raises(IntentConfigError) as excinfo:
        load_intent(path)
    assert "invalid [checks].gates[0].kind" in str(excinfo.value)


def test_load_intent_schema_and_policy_values(
    tmp_path: Path,
) -> None:
    path = write_intent(
        tmp_path,
        """
        [intent]
        schema_version = 1

        [python]
        version = "3.12"

        [commands]
        test = "pytest -q"

        [policy]
        strict = true
        """,
    )
    cfg = load_intent(path)
    assert cfg.schema_version == 1
    assert cfg.policy_strict is True


def test_load_intent_rejects_invalid_schema_version(
    tmp_path: Path,
) -> None:
    path = write_intent(
        tmp_path,
        """
        [intent]
        schema_version = 2

        [python]
        version = "3.12"

        [commands]
        test = "pytest -q"
        """,
    )
    with pytest.raises(IntentConfigError) as excinfo:
        load_intent(path)
    assert "Unsupported [intent].schema_version" in str(excinfo.value)


def test_load_intent_rejects_non_boolean_policy_strict(
    tmp_path: Path,
) -> None:
    path = write_intent(
        tmp_path,
        """
        [python]
        version = "3.12"

        [commands]
        test = "pytest -q"

        [policy]
        strict = "yes"
        """,
    )
    with pytest.raises(IntentConfigError) as excinfo:
        load_intent(path)
    msg = str(excinfo.value)
    assert "invalid [policy].strict" in msg
    assert "expected boolean" in msg
    assert "got str" in msg


def test_load_intent_policy_pack_strict_sets_defaults(tmp_path: Path) -> None:
    path = write_intent(
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
    cfg = load_intent(path)
    assert cfg.policy_pack == "strict"
    assert cfg.policy_strict is True


def test_load_intent_policy_pack_allows_explicit_override(tmp_path: Path) -> None:
    path = write_intent(
        tmp_path,
        """
        [python]
        version = "3.12"

        [commands]
        test = "pytest -q"

        [policy]
        pack = "strict"
        strict = false
        """,
    )
    cfg = load_intent(path)
    assert cfg.policy_pack == "strict"
    assert cfg.policy_strict is False


def test_load_intent_rejects_unknown_policy_pack(tmp_path: Path) -> None:
    path = write_intent(
        tmp_path,
        """
        [python]
        version = "3.12"

        [commands]
        test = "pytest -q"

        [policy]
        pack = "team-alpha"
        """,
    )
    with pytest.raises(IntentConfigError) as excinfo:
        load_intent(path)
    assert "invalid [policy].pack" in str(excinfo.value)


def test_load_intent_invalid_toml(
    tmp_path: Path,
) -> None:
    path = write_intent(
        tmp_path,
        """
        [python
        version = "3.12"
        """,
    )

    with pytest.raises(IntentConfigError) as excinfo:
        load_intent(path)

    assert "Invalid TOML" in str(excinfo.value)


def test_load_intent_invalid_command_type_shows_expected_and_got(tmp_path: Path) -> None:
    path = write_intent(
        tmp_path,
        """
        [python]
        version = "3.12"

        [commands]
        test = 123
        """,
    )
    with pytest.raises(IntentConfigError) as excinfo:
        load_intent(path)
    msg = str(excinfo.value)
    assert "intent.toml" in msg
    assert "invalid [commands].test" in msg
    assert "expected string shell command" in msg
    assert "got int" in msg


def test_load_intent_plugins_hooks_custom(tmp_path: Path) -> None:
    path = write_intent(
        tmp_path,
        """
        [python]
        version = "3.12"

        [commands]
        test = "pytest -q"

        [plugins]
        check = ["echo check-1", "echo check-2"]
        generate = ["echo gen-1"]
        """,
    )
    cfg = load_intent(path)
    assert cfg.plugin_check_hooks == ["echo check-1", "echo check-2"]
    assert cfg.plugin_generate_hooks == ["echo gen-1"]


def test_load_intent_plugins_check_rejects_invalid_type(tmp_path: Path) -> None:
    path = write_intent(
        tmp_path,
        """
        [python]
        version = "3.12"

        [commands]
        test = "pytest -q"

        [plugins]
        check = "echo check"
        """,
    )
    with pytest.raises(IntentConfigError) as excinfo:
        load_intent(path)
    assert "invalid [plugins].check" in str(excinfo.value)


def test_load_intent_plugins_generate_rejects_empty_item(tmp_path: Path) -> None:
    path = write_intent(
        tmp_path,
        """
        [python]
        version = "3.12"

        [commands]
        test = "pytest -q"

        [plugins]
        generate = [" "]
        """,
    )
    with pytest.raises(IntentConfigError) as excinfo:
        load_intent(path)
    assert "invalid [plugins].generate[0]" in str(excinfo.value)


def test_load_intent_ci_jobs_valid(tmp_path: Path) -> None:
    path = write_intent(
        tmp_path,
        """
        [python]
        version = "3.12"

        [commands]
        test = "pytest -q"
        lint = "ruff check ."

        [[ci.jobs]]
        name = "lint"
        steps = [
          { uses = "actions/checkout@v4" },
          { command = "lint" }
        ]

        [[ci.jobs]]
        name = "test"
        needs = ["lint"]
        timeout_minutes = 20
        continue_on_error = true
        matrix = { python-version = ["3.11", "3.12"] }

        steps = [
          { uses = "actions/setup-python@v5", with = { python-version = "${{ matrix.python-version }}" } },
          { command = "test", if = "${{ always() }}", working_directory = ".", env = { PYTHONUNBUFFERED = "1" } }
        ]
        """,
    )
    cfg = load_intent(path)
    assert cfg.ci_jobs is not None
    assert len(cfg.ci_jobs) == 2
    assert cfg.ci_jobs[0].name == "lint"
    assert cfg.ci_jobs[1].needs == ["lint"]
    assert cfg.ci_jobs[1].matrix == {"python-version": ["3.11", "3.12"]}


def test_load_intent_ci_jobs_rejects_unknown_needs_job(tmp_path: Path) -> None:
    path = write_intent(
        tmp_path,
        """
        [python]
        version = "3.12"

        [commands]
        test = "pytest -q"

        [[ci.jobs]]
        name = "test"
        needs = ["lint"]
        steps = [{ command = "test" }]
        """,
    )
    with pytest.raises(IntentConfigError) as excinfo:
        load_intent(path)
    assert "unknown job 'lint'" in str(excinfo.value)


def test_load_intent_ci_jobs_rejects_step_with_multiple_actions(tmp_path: Path) -> None:
    path = write_intent(
        tmp_path,
        """
        [python]
        version = "3.12"

        [commands]
        test = "pytest -q"

        [[ci.jobs]]
        name = "test"
        steps = [{ command = "test", run = "pytest -q" }]
        """,
    )
    with pytest.raises(IntentConfigError) as excinfo:
        load_intent(path)
    assert "set exactly one of run, command, uses" in str(excinfo.value)


def test_load_intent_ci_artifacts_valid(tmp_path: Path) -> None:
    path = write_intent(
        tmp_path,
        """
        [python]
        version = "3.12"

        [commands]
        test = "pytest -q"

        [ci]
        artifacts = [
          { name = "junit", path = "reports/junit.xml", retention_days = 7, when = "on-failure" },
          { name = "coverage", path = "coverage.xml" }
        ]
        """,
    )
    cfg = load_intent(path)
    assert cfg.ci_artifacts is not None
    assert len(cfg.ci_artifacts) == 2
    assert cfg.ci_artifacts[0].when == "on-failure"
    assert cfg.ci_artifacts[1].when == "always"


def test_load_intent_ci_artifacts_rejects_invalid_when(tmp_path: Path) -> None:
    path = write_intent(
        tmp_path,
        """
        [python]
        version = "3.12"

        [commands]
        test = "pytest -q"

        [ci]
        artifacts = [{ name = "junit", path = "reports/junit.xml", when = "on-error" }]
        """,
    )
    with pytest.raises(IntentConfigError) as excinfo:
        load_intent(path)
    assert "invalid [ci].artifacts[0].when" in str(excinfo.value)


def test_load_intent_ci_summary_with_metrics_valid(tmp_path: Path) -> None:
    path = write_intent(
        tmp_path,
        """
        [python]
        version = "3.12"

        [commands]
        eval = "cat metrics.json"

        [ci.summary]
        enabled = true
        title = "Quality Report"
        include_assertions = true
        metrics = [
          { label = "score", command = "eval", path = "metrics.score", baseline_path = "metrics.prev_score", precision = 3 }
        ]
        """,
    )
    cfg = load_intent(path)
    assert cfg.ci_summary is not None
    assert cfg.ci_summary.title == "Quality Report"
    assert cfg.ci_summary.metrics is not None
    assert cfg.ci_summary.metrics[0].label == "score"


def test_load_intent_ci_summary_rejects_unknown_metric_command(tmp_path: Path) -> None:
    path = write_intent(
        tmp_path,
        """
        [python]
        version = "3.12"

        [commands]
        test = "pytest -q"

        [ci.summary]
        metrics = [{ label = "score", command = "eval", path = "metrics.score" }]
        """,
    )
    with pytest.raises(IntentConfigError) as excinfo:
        load_intent(path)
    assert "invalid [ci].summary.metrics[0].command" in str(excinfo.value)


def test_load_intent_ci_summary_baseline_file_requires_path(tmp_path: Path) -> None:
    path = write_intent(
        tmp_path,
        """
        [python]
        version = "3.12"

        [commands]
        eval = "cat metrics.json"

        [ci.summary]
        metrics = [{ label = "score", command = "eval", path = "metrics.score" }]

        [ci.summary.baseline]
        source = "file"
        """,
    )
    with pytest.raises(IntentConfigError) as excinfo:
        load_intent(path)
    assert "[ci].summary.baseline.file is required when source='file'" in str(excinfo.value)
