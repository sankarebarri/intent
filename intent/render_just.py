# intent/render_just.py
from __future__ import annotations

from .config import IntentConfig
from .fs import GENERATED_MARKER


def render_just(cfg: IntentConfig) -> str:
    """
    Render a minimal justfile as a string.
    """
    lines: list[str] = []

    lines.append(GENERATED_MARKER)
    lines.append("# DO NOT EDIT")
    lines.append("")

    lines.append("default:")
    lines.append("    @just --list")
    lines.append("")

    for name, cmd in cfg.commands.items():
        lines.append(f"{name}:")
        lines.append(f"    {cmd}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
