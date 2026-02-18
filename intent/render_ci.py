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
    triggers = cfg.ci_triggers or ["push"]
    trigger_values = ", ".join(triggers)
    lines.append(f"on: [{trigger_values}]")
    lines.append("")
    lines.append("jobs:")
    lines.append("  ci:")
    lines.append("    runs-on: ubuntu-latest")
    if cfg.ci_python_versions:
        lines.append("    strategy:")
        lines.append("      fail-fast: false")
        lines.append("      matrix:")
        versions = ", ".join(f'"{v}"' for v in cfg.ci_python_versions)
        lines.append(f"        python-version: [{versions}]")
    lines.append("    steps:")
    lines.append("      - uses: actions/checkout@v4")
    lines.append("      - uses: actions/setup-python@v5")
    lines.append("        with:")
    if cfg.ci_python_versions:
        lines.append("          python-version: ${{ matrix.python-version }}")
    else:
        lines.append(f'          python-version: "{cfg.python_version}"')
    if cfg.ci_cache == "pip":
        lines.append("          cache: pip")
    lines.append("")
    lines.append("      - name: Install dependencies")
    lines.append("        run: |")
    lines.append("          python -m pip install -U pip")
    lines.append(f"          python -m pip install {cfg.ci_install}")
    lines.append("")

    for name, cmd in cfg.commands.items():
        lines.append(f"      - name: {name}")
        lines.append("        run: |")
        for cmd_line in cmd.splitlines():
            lines.append(f"          {cmd_line}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
