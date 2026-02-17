# intent/config.py
from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from .versioning import validate_python_version

DEFAULT_CI_INSTALL = "-e .[dev]"
DEFAULT_SCHEMA_VERSION = 1
DEFAULT_POLICY_STRICT = False


class IntentConfigError(Exception):
    """Config error in intent.toml"""


@dataclass
class IntentConfig:
    python_version: str
    commands: dict[str, str]
    ci_install: str = DEFAULT_CI_INSTALL
    ci_python_versions: list[str] | None = None
    ci_triggers: list[str] | None = None
    policy_strict: bool = DEFAULT_POLICY_STRICT
    schema_version: int = DEFAULT_SCHEMA_VERSION


def load_raw_intent(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"{path} does not exist")

    text = path.read_text(encoding="utf-8")
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        raise IntentConfigError(f"Invalid TOML in {path}: {e}") from e

    python_section = data.get("python")
    if not isinstance(python_section, dict):
        raise IntentConfigError("Missing [python] table in intent.toml")

    version = python_section.get("version")
    if not isinstance(version, str):
        raise IntentConfigError("Missing or invalid python.version (expected a string)")

    commands_section = data.get("commands")
    if not isinstance(commands_section, dict):
        raise IntentConfigError("Missing [commands] table in intent.toml")

    if not commands_section:
        raise IntentConfigError("[commands] must define at least one command")

    for name, value in commands_section.items():
        if not isinstance(value, str):
            raise IntentConfigError(f"[commands].{name} must be a string shell command")
        if not value.strip():
            raise IntentConfigError(f"[commands].{name} cannot be empty")

    intent_section = data.get("intent")
    if intent_section is not None:
        if not isinstance(intent_section, dict):
            raise IntentConfigError("Invalid [intent] table: must be a table/object")
        raw_schema = intent_section.get("schema_version")
        if raw_schema is None:
            raise IntentConfigError("[intent].schema_version is required when [intent] is present")
        if not isinstance(raw_schema, int):
            raise IntentConfigError("[intent].schema_version must be an integer")
        if raw_schema != DEFAULT_SCHEMA_VERSION:
            raise IntentConfigError(
                f"Unsupported [intent].schema_version={raw_schema} "
                f"(expected {DEFAULT_SCHEMA_VERSION})"
            )

    policy_section = data.get("policy")
    if policy_section is not None:
        if not isinstance(policy_section, dict):
            raise IntentConfigError("Invalid [policy] table: must be a table/object")
        raw_strict = policy_section.get("strict")
        if raw_strict is not None and not isinstance(raw_strict, bool):
            raise IntentConfigError("[policy].strict must be a boolean")

    return data


def load_intent(path: Path) -> IntentConfig:
    """
    Load intent.toml and return a structured IntentConfig.
    """
    data = load_raw_intent(path)

    python_section = data["python"]
    commands_section = data["commands"]

    python_version = python_section["version"].strip()
    try:
        validate_python_version(python_version)
    except ValueError as e:
        raise IntentConfigError(str(e)) from e

    commands = {k: v.strip() for k, v in dict(commands_section).items()}

    ci_install = DEFAULT_CI_INSTALL
    ci_python_versions: list[str] | None = None
    ci_triggers: list[str] | None = None
    ci_section = data.get("ci")
    if ci_section is not None:
        if not isinstance(ci_section, dict):
            raise IntentConfigError("Invalid [ci] table: must be a table/object")
        raw_install = ci_section.get("install")
        if raw_install is not None:
            if not isinstance(raw_install, str) or not raw_install.strip():
                raise IntentConfigError("[ci].install must be a non-empty string")
            ci_install = raw_install.strip()
        raw_versions = ci_section.get("python_versions")
        if raw_versions is not None:
            if not isinstance(raw_versions, list) or not raw_versions:
                raise IntentConfigError("[ci].python_versions must be a non-empty array of strings")
            parsed_versions: list[str] = []
            for idx, raw in enumerate(raw_versions):
                if not isinstance(raw, str) or not raw.strip():
                    raise IntentConfigError(
                        f"[ci].python_versions[{idx}] must be a non-empty version string"
                    )
                version = raw.strip()
                try:
                    validate_python_version(version)
                except ValueError as e:
                    raise IntentConfigError(str(e)) from e
                parsed_versions.append(version)
            ci_python_versions = parsed_versions
        raw_triggers = ci_section.get("triggers")
        if raw_triggers is not None:
            if not isinstance(raw_triggers, list) or not raw_triggers:
                raise IntentConfigError("[ci].triggers must be a non-empty array of strings")
            parsed_triggers: list[str] = []
            for idx, raw in enumerate(raw_triggers):
                if not isinstance(raw, str) or not raw.strip():
                    raise IntentConfigError(
                        f"[ci].triggers[{idx}] must be a non-empty trigger string"
                    )
                parsed_triggers.append(raw.strip())
            ci_triggers = parsed_triggers
    schema_version = DEFAULT_SCHEMA_VERSION
    intent_section = data.get("intent")
    if isinstance(intent_section, dict):
        schema_version = intent_section["schema_version"]

    policy_strict = DEFAULT_POLICY_STRICT
    policy_section = data.get("policy")
    if isinstance(policy_section, dict):
        raw_strict = policy_section.get("strict")
        if raw_strict is not None:
            policy_strict = raw_strict

    return IntentConfig(
        schema_version=schema_version,
        python_version=python_version,
        commands=commands,
        ci_install=ci_install,
        ci_python_versions=ci_python_versions,
        ci_triggers=ci_triggers,
        policy_strict=policy_strict,
    )
