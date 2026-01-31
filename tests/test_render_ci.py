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
