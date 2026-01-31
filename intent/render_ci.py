# intent/render_ci.py
from __future__ import annotations

from .config import IntentConfig
from .fs import GENERATED_MARKER


def render_ci(cfg: IntentConfig) -> str:
    """
    Render a minimal GitHub Actions workflow as a string.
    """
    lines: list[str] = []

    lines.append(GENERATED_MARKER)
    lines.append("# DO NOT EDIT")
    lines.append("")

    lines.append("name: CI")
    lines.append("on: [push]")
    lines.append("")
    lines.append("jobs:")
    lines.append("  ci:")
    lines.append("    runs-on: ubuntu-latest")
    lines.append("    steps:")
    lines.append("      - uses: actions/checkout@v4")
    lines.append("      - uses: actions/setup-python@v5")
    lines.append("        with:")
    lines.append(f'          python-version: "{cfg.python_version}"')
    lines.append("")
    lines.append("      - name: Install dependencies")
    lines.append("        run: |")
    lines.append("          python -m pip install -U pip")
    lines.append(f"          python -m pip install {cfg.ci_install}")
    lines.append("")

    for name, cmd in cfg.commands.items():
        lines.append(f"      - name: {name}")
        lines.append(f"        run: {cmd}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
