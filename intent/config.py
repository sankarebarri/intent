# intent/config.py
from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from .versioning import validate_python_version

DEFAULT_CI_INSTALL = "-e .[dev]"
DEFAULT_CI_CACHE = "none"
DEFAULT_SCHEMA_VERSION = 1
DEFAULT_POLICY_STRICT = False


class IntentConfigError(Exception):
    """Config error in intent.toml"""


def _type_name(value: object) -> str:
    if value is None:
        return "null"
    return type(value).__name__


def _field_type_error(path: Path, field: str, expected: str, value: object) -> IntentConfigError:
    return IntentConfigError(
        f"{path}: invalid {field} (expected {expected}, got {_type_name(value)})"
    )


@dataclass
class IntentConfig:
    python_version: str
    commands: dict[str, str]
    ci_install: str = DEFAULT_CI_INSTALL
    ci_cache: str = DEFAULT_CI_CACHE
    ci_python_versions: list[str] | None = None
    ci_triggers: list[str] | None = None
    plugin_check_hooks: list[str] | None = None
    plugin_generate_hooks: list[str] | None = None
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
        raise _field_type_error(path, "[python]", "table/object", python_section)

    version = python_section.get("version")
    if not isinstance(version, str):
        raise _field_type_error(path, "[python].version", "string", version)

    commands_section = data.get("commands")
    if not isinstance(commands_section, dict):
        raise _field_type_error(path, "[commands]", "table/object", commands_section)

    if not commands_section:
        raise IntentConfigError("[commands] must define at least one command")

    for name, value in commands_section.items():
        if not isinstance(value, str):
            raise _field_type_error(path, f"[commands].{name}", "string shell command", value)
        if not value.strip():
            raise IntentConfigError(f"[commands].{name} cannot be empty")

    intent_section = data.get("intent")
    if intent_section is not None:
        if not isinstance(intent_section, dict):
            raise _field_type_error(path, "[intent]", "table/object", intent_section)
        raw_schema = intent_section.get("schema_version")
        if raw_schema is None:
            raise IntentConfigError("[intent].schema_version is required when [intent] is present")
        if not isinstance(raw_schema, int):
            raise _field_type_error(path, "[intent].schema_version", "integer", raw_schema)
        if raw_schema != DEFAULT_SCHEMA_VERSION:
            raise IntentConfigError(
                f"Unsupported [intent].schema_version={raw_schema} "
                f"(expected {DEFAULT_SCHEMA_VERSION})"
            )

    policy_section = data.get("policy")
    if policy_section is not None:
        if not isinstance(policy_section, dict):
            raise _field_type_error(path, "[policy]", "table/object", policy_section)
        raw_strict = policy_section.get("strict")
        if raw_strict is not None and not isinstance(raw_strict, bool):
            raise _field_type_error(path, "[policy].strict", "boolean", raw_strict)

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
    ci_cache = DEFAULT_CI_CACHE
    ci_python_versions: list[str] | None = None
    ci_triggers: list[str] | None = None
    plugin_check_hooks: list[str] | None = None
    plugin_generate_hooks: list[str] | None = None
    ci_section = data.get("ci")
    if ci_section is not None:
        if not isinstance(ci_section, dict):
            raise _field_type_error(path, "[ci]", "table/object", ci_section)
        raw_install = ci_section.get("install")
        if raw_install is not None:
            if not isinstance(raw_install, str) or not raw_install.strip():
                raise _field_type_error(path, "[ci].install", "non-empty string", raw_install)
            ci_install = raw_install.strip()
        raw_cache = ci_section.get("cache")
        if raw_cache is not None:
            if not isinstance(raw_cache, str):
                raise _field_type_error(path, "[ci].cache", "string ('none'|'pip')", raw_cache)
            cache = raw_cache.strip().lower()
            if cache not in ("none", "pip"):
                raise IntentConfigError(
                    f"{path}: invalid [ci].cache (expected one of 'none', 'pip', got {raw_cache!r})"
                )
            ci_cache = cache
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

    plugins_section = data.get("plugins")
    if plugins_section is not None:
        if not isinstance(plugins_section, dict):
            raise _field_type_error(path, "[plugins]", "table/object", plugins_section)
        raw_check_hooks = plugins_section.get("check")
        if raw_check_hooks is not None:
            if not isinstance(raw_check_hooks, list):
                raise _field_type_error(path, "[plugins].check", "array of strings", raw_check_hooks)
            parsed_check_hooks: list[str] = []
            for idx, raw in enumerate(raw_check_hooks):
                if not isinstance(raw, str) or not raw.strip():
                    raise IntentConfigError(
                        f"{path}: invalid [plugins].check[{idx}] "
                        "(expected non-empty string command)"
                    )
                parsed_check_hooks.append(raw.strip())
            plugin_check_hooks = parsed_check_hooks or None
        raw_generate_hooks = plugins_section.get("generate")
        if raw_generate_hooks is not None:
            if not isinstance(raw_generate_hooks, list):
                raise _field_type_error(
                    path, "[plugins].generate", "array of strings", raw_generate_hooks
                )
            parsed_generate_hooks: list[str] = []
            for idx, raw in enumerate(raw_generate_hooks):
                if not isinstance(raw, str) or not raw.strip():
                    raise IntentConfigError(
                        f"{path}: invalid [plugins].generate[{idx}] "
                        "(expected non-empty string command)"
                    )
                parsed_generate_hooks.append(raw.strip())
            plugin_generate_hooks = parsed_generate_hooks or None
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
        ci_cache=ci_cache,
        ci_python_versions=ci_python_versions,
        ci_triggers=ci_triggers,
        plugin_check_hooks=plugin_check_hooks,
        plugin_generate_hooks=plugin_generate_hooks,
        policy_strict=policy_strict,
    )
