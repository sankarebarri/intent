from __future__ import (
    annotations,
)

from pathlib import (
    Path,
)
import tomllib

from dataclasses import (
    dataclass,
)
from typing import (
    Dict,
)

DEFAULT_CI_INSTALL = "-e .[dev]"


class IntentConfigError(Exception):
    """Config error in intent.toml"""

    pass


@dataclass
class IntentConfig:
    python_version: str
    commands: Dict[
        str,
        str,
    ]
    ci_install: str = DEFAULT_CI_INSTALL


def load_raw_intent(
    path: Path,
) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"{path} does not exist")

    text = path.read_text(encoding="utf-8")
    data = tomllib.loads(text)

    python_section = data.get("python")
    if not isinstance(
        python_section,
        dict,
    ):
        raise IntentConfigError("Missing [python] table in intent.toml")

    version = python_section.get("version")
    if not isinstance(
        version,
        str,
    ):
        raise IntentConfigError("Missing or invalid python.version (expected a string)")

    commands_section = data.get("commands")
    if not isinstance(
        commands_section,
        dict,
    ):
        raise IntentConfigError("Missing [commands] table in intent.toml")

    if not commands_section:
        raise IntentConfigError("[commands] must define at least one command")

    for (
        name,
        value,
    ) in commands_section.items():
        if not isinstance(
            value,
            str,
        ):
            raise IntentConfigError(f"[commands].{name} must be a string shell command")
        if not value.strip():
            raise IntentConfigError(f"[commands].{name} cannot be empty")

    return data


def load_intent(
    path: Path,
) -> IntentConfig:
    """
    Load intent.toml and return a structured IntentConfig.

    Assumes load_raw_intent has already done basic validation.
    """
    data = load_raw_intent(path)

    python_section = data["python"]
    commands_section = data["commands"]

    python_version = python_section["version"]
    commands = dict(commands_section)

    ci_install = DEFAULT_CI_INSTALL
    ci_section = data.get("ci")
    if ci_section is not None:
        if not isinstance(
            ci_section,
            dict,
        ):
            raise IntentConfigError("Invalid [ci] table: must be a table/object")
        raw_install = ci_section.get("install")
        if raw_install is not None:
            if (
                not isinstance(
                    raw_install,
                    str,
                )
                or not raw_install.strip()
            ):
                raise IntentConfigError("[ci].install must be a non-empty string")
            ci_install = raw_install.strip()

    return IntentConfig(
        python_version=python_version,
        commands=commands,
        ci_install=ci_install,
    )
