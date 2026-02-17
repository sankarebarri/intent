# test_render_ci.py
from pathlib import (
    Path,
)

from intent.config import (
    IntentConfig,
)
from intent.render_ci import (
    render_ci,
)


def test_render_ci_includes_install_step(
    tmp_path: Path,
) -> None:
    cfg = IntentConfig(
        python_version="3.12",
        commands={"test": "pytest -q"},
        ci_install="-e .[dev]",
    )
    out = render_ci(cfg)

    assert "name: Install dependencies" in out
    assert "python -m pip install -U pip" in out
    assert "python -m pip install -e .[dev]" in out


def test_render_ci_commands_use_block_scalars() -> None:
    cfg = IntentConfig(
        python_version="3.12",
        commands={"test": "pytest -q\npytest --maxfail=1"},
        ci_install="-e .[dev]",
    )
    out = render_ci(cfg)

    assert "- name: test" in out
    assert "run: |\n          pytest -q\n          pytest --maxfail=1" in out


def test_render_ci_with_python_matrix() -> None:
    cfg = IntentConfig(
        python_version="3.12",
        commands={"test": "pytest -q"},
        ci_install="-e .[dev]",
        ci_python_versions=["3.11", "3.12"],
    )
    out = render_ci(cfg)

    assert "strategy:" in out
    assert "matrix:" in out
    assert 'python-version: ["3.11", "3.12"]' in out
    assert "python-version: ${{ matrix.python-version }}" in out


def test_render_ci_with_custom_triggers() -> None:
    cfg = IntentConfig(
        python_version="3.12",
        commands={"test": "pytest -q"},
        ci_triggers=["push", "pull_request"],
    )
    out = render_ci(cfg)
    assert "on: [push, pull_request]" in out
