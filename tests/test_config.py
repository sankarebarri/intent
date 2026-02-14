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

    # our config.py raises: "Missing [python] table in content.toml"
    assert "Missing [python]" in str(excinfo.value)


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
