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
