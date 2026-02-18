# intent/config.py
from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .versioning import validate_python_version

DEFAULT_CI_INSTALL = "-e .[dev]"
DEFAULT_CI_CACHE = "none"
DEFAULT_SCHEMA_VERSION = 1
DEFAULT_POLICY_STRICT = False
CHECK_ASSERTION_OPERATORS = {
    "eq",
    "ne",
    "gt",
    "gte",
    "lt",
    "lte",
    "in",
    "not_in",
}
CI_ARTIFACT_WHEN = {"always", "on-failure", "on-success"}
POLICY_PACK_DEFAULT = "default"
POLICY_PACK_STRICT = "strict"
POLICY_PACKS: dict[str, dict[str, bool]] = {
    POLICY_PACK_DEFAULT: {"strict": False},
    POLICY_PACK_STRICT: {"strict": True},
}


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
class CheckAssertion:
    command: str
    path: str
    op: str
    value: Any
    message: str | None = None


@dataclass
class CiStep:
    name: str | None = None
    run: str | None = None
    command: str | None = None
    uses: str | None = None
    with_args: dict[str, str] | None = None
    if_condition: str | None = None
    continue_on_error: bool = False
    working_directory: str | None = None
    env: dict[str, str] | None = None


@dataclass
class CiJob:
    name: str
    runs_on: str = "ubuntu-latest"
    needs: list[str] | None = None
    if_condition: str | None = None
    timeout_minutes: int | None = None
    continue_on_error: bool = False
    matrix: dict[str, list[Any]] | None = None
    steps: list[CiStep] | None = None


@dataclass
class CiArtifact:
    name: str
    path: str
    retention_days: int | None = None
    when: str = "always"


@dataclass
class CiSummaryMetric:
    label: str
    command: str
    path: str
    baseline_path: str | None = None
    precision: int | None = None


@dataclass
class CiSummary:
    enabled: bool = True
    title: str = "Intent CI Summary"
    include_assertions: bool = True
    metrics: list[CiSummaryMetric] | None = None


@dataclass
class IntentConfig:
    python_version: str
    commands: dict[str, str]
    ci_install: str = DEFAULT_CI_INSTALL
    ci_cache: str = DEFAULT_CI_CACHE
    ci_python_versions: list[str] | None = None
    ci_triggers: list[str] | None = None
    ci_jobs: list[CiJob] | None = None
    ci_artifacts: list[CiArtifact] | None = None
    ci_summary: CiSummary | None = None
    plugin_check_hooks: list[str] | None = None
    plugin_generate_hooks: list[str] | None = None
    checks_assertions: list[CheckAssertion] | None = None
    policy_pack: str | None = None
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
        raw_pack = policy_section.get("pack")
        if raw_pack is not None:
            if not isinstance(raw_pack, str) or not raw_pack.strip():
                raise _field_type_error(path, "[policy].pack", "non-empty string", raw_pack)
            policy_pack = raw_pack.strip()
            if policy_pack not in POLICY_PACKS:
                allowed = ", ".join(sorted(POLICY_PACKS))
                raise IntentConfigError(
                    f"{path}: invalid [policy].pack "
                    f"(expected one of {allowed}, got {policy_pack!r})"
                )
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
    ci_jobs: list[CiJob] | None = None
    ci_artifacts: list[CiArtifact] | None = None
    ci_summary: CiSummary | None = None
    plugin_check_hooks: list[str] | None = None
    plugin_generate_hooks: list[str] | None = None
    checks_assertions: list[CheckAssertion] | None = None
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
        raw_jobs = ci_section.get("jobs")
        if raw_jobs is not None:
            if not isinstance(raw_jobs, list) or not raw_jobs:
                raise IntentConfigError("[ci].jobs must be a non-empty array of tables")
            parsed_jobs: list[CiJob] = []
            seen_job_names: set[str] = set()
            for job_idx, raw_job in enumerate(raw_jobs):
                if not isinstance(raw_job, dict):
                    raise IntentConfigError(
                        f"{path}: invalid [ci].jobs[{job_idx}] (expected table/object)"
                    )

                raw_name = raw_job.get("name")
                if not isinstance(raw_name, str) or not raw_name.strip():
                    raise IntentConfigError(
                        f"{path}: invalid [ci].jobs[{job_idx}].name (expected non-empty string)"
                    )
                job_name = raw_name.strip()
                if job_name in seen_job_names:
                    raise IntentConfigError(
                        f"{path}: duplicate [ci].jobs name {job_name!r} is not allowed"
                    )
                seen_job_names.add(job_name)

                runs_on = "ubuntu-latest"
                raw_runs_on = raw_job.get("runs_on")
                if raw_runs_on is not None:
                    if not isinstance(raw_runs_on, str) or not raw_runs_on.strip():
                        raise IntentConfigError(
                            f"{path}: invalid [ci].jobs[{job_idx}].runs_on "
                            "(expected non-empty string)"
                        )
                    runs_on = raw_runs_on.strip()

                needs: list[str] | None = None
                raw_needs = raw_job.get("needs")
                if raw_needs is not None:
                    if not isinstance(raw_needs, list) or not raw_needs:
                        raise IntentConfigError(
                            f"{path}: invalid [ci].jobs[{job_idx}].needs "
                            "(expected non-empty array of strings)"
                        )
                    parsed_needs: list[str] = []
                    for need_idx, raw_need in enumerate(raw_needs):
                        if not isinstance(raw_need, str) or not raw_need.strip():
                            raise IntentConfigError(
                                f"{path}: invalid [ci].jobs[{job_idx}].needs[{need_idx}] "
                                "(expected non-empty string)"
                            )
                        parsed_needs.append(raw_need.strip())
                    needs = parsed_needs

                if_condition: str | None = None
                raw_if = raw_job.get("if")
                if raw_if is not None:
                    if not isinstance(raw_if, str) or not raw_if.strip():
                        raise IntentConfigError(
                            f"{path}: invalid [ci].jobs[{job_idx}].if "
                            "(expected non-empty string)"
                        )
                    if_condition = raw_if.strip()

                timeout_minutes: int | None = None
                raw_timeout = raw_job.get("timeout_minutes")
                if raw_timeout is not None:
                    if not isinstance(raw_timeout, int) or raw_timeout <= 0:
                        raise IntentConfigError(
                            f"{path}: invalid [ci].jobs[{job_idx}].timeout_minutes "
                            "(expected positive integer)"
                        )
                    timeout_minutes = raw_timeout

                continue_on_error = False
                raw_continue_on_error = raw_job.get("continue_on_error")
                if raw_continue_on_error is not None:
                    if not isinstance(raw_continue_on_error, bool):
                        raise IntentConfigError(
                            f"{path}: invalid [ci].jobs[{job_idx}].continue_on_error "
                            "(expected boolean)"
                        )
                    continue_on_error = raw_continue_on_error

                matrix: dict[str, list[Any]] | None = None
                raw_matrix = raw_job.get("matrix")
                if raw_matrix is not None:
                    if not isinstance(raw_matrix, dict) or not raw_matrix:
                        raise IntentConfigError(
                            f"{path}: invalid [ci].jobs[{job_idx}].matrix "
                            "(expected non-empty table/object)"
                        )
                    parsed_matrix: dict[str, list[Any]] = {}
                    for matrix_key, matrix_values in raw_matrix.items():
                        if not isinstance(matrix_key, str) or not matrix_key.strip():
                            raise IntentConfigError(
                                f"{path}: invalid [ci].jobs[{job_idx}].matrix key "
                                "(expected non-empty string)"
                            )
                        if not isinstance(matrix_values, list) or not matrix_values:
                            raise IntentConfigError(
                                f"{path}: invalid [ci].jobs[{job_idx}].matrix.{matrix_key} "
                                "(expected non-empty array)"
                            )
                        parsed_values: list[Any] = []
                        for val_idx, value in enumerate(matrix_values):
                            if not isinstance(value, (str, int, float, bool)):
                                raise IntentConfigError(
                                    f"{path}: invalid [ci].jobs[{job_idx}].matrix."
                                    f"{matrix_key}[{val_idx}] (unsupported value type)"
                                )
                            parsed_values.append(value)
                        parsed_matrix[matrix_key.strip()] = parsed_values
                    matrix = parsed_matrix

                raw_steps = raw_job.get("steps")
                if not isinstance(raw_steps, list) or not raw_steps:
                    raise IntentConfigError(
                        f"{path}: invalid [ci].jobs[{job_idx}].steps "
                        "(expected non-empty array of tables)"
                    )
                parsed_steps: list[CiStep] = []
                for step_idx, raw_step in enumerate(raw_steps):
                    if not isinstance(raw_step, dict):
                        raise IntentConfigError(
                            f"{path}: invalid [ci].jobs[{job_idx}].steps[{step_idx}] "
                            "(expected table/object)"
                        )
                    raw_name = raw_step.get("name")
                    step_name: str | None = None
                    if raw_name is not None:
                        if not isinstance(raw_name, str) or not raw_name.strip():
                            raise IntentConfigError(
                                f"{path}: invalid [ci].jobs[{job_idx}].steps[{step_idx}].name "
                                "(expected non-empty string)"
                            )
                        step_name = raw_name.strip()

                    raw_run = raw_step.get("run")
                    run: str | None = None
                    if raw_run is not None:
                        if not isinstance(raw_run, str) or not raw_run.strip():
                            raise IntentConfigError(
                                f"{path}: invalid [ci].jobs[{job_idx}].steps[{step_idx}].run "
                                "(expected non-empty string)"
                            )
                        run = raw_run.strip()

                    raw_command = raw_step.get("command")
                    command: str | None = None
                    if raw_command is not None:
                        if not isinstance(raw_command, str) or not raw_command.strip():
                            raise IntentConfigError(
                                f"{path}: invalid [ci].jobs[{job_idx}].steps[{step_idx}].command "
                                "(expected non-empty string)"
                            )
                        command = raw_command.strip()
                        if command not in commands:
                            raise IntentConfigError(
                                f"{path}: invalid [ci].jobs[{job_idx}].steps[{step_idx}].command "
                                f"(unknown command {command!r})"
                            )

                    raw_uses = raw_step.get("uses")
                    uses: str | None = None
                    if raw_uses is not None:
                        if not isinstance(raw_uses, str) or not raw_uses.strip():
                            raise IntentConfigError(
                                f"{path}: invalid [ci].jobs[{job_idx}].steps[{step_idx}].uses "
                                "(expected non-empty string)"
                            )
                        uses = raw_uses.strip()

                    set_count = sum(item is not None for item in (run, command, uses))
                    if set_count != 1:
                        raise IntentConfigError(
                            f"{path}: invalid [ci].jobs[{job_idx}].steps[{step_idx}] "
                            "(set exactly one of run, command, uses)"
                        )

                    with_args: dict[str, str] | None = None
                    raw_with = raw_step.get("with")
                    if raw_with is not None:
                        if not isinstance(raw_with, dict):
                            raise IntentConfigError(
                                f"{path}: invalid [ci].jobs[{job_idx}].steps[{step_idx}].with "
                                "(expected table/object)"
                            )
                        parsed_with: dict[str, str] = {}
                        for key, val in raw_with.items():
                            if not isinstance(key, str) or not key.strip():
                                raise IntentConfigError(
                                    f"{path}: invalid [ci].jobs[{job_idx}].steps[{step_idx}].with key "
                                    "(expected non-empty string)"
                                )
                            if not isinstance(val, str) or not val.strip():
                                raise IntentConfigError(
                                    f"{path}: invalid [ci].jobs[{job_idx}].steps[{step_idx}].with."
                                    f"{key} (expected non-empty string)"
                                )
                            parsed_with[key.strip()] = val.strip()
                        with_args = parsed_with or None

                    step_if: str | None = None
                    raw_step_if = raw_step.get("if")
                    if raw_step_if is not None:
                        if not isinstance(raw_step_if, str) or not raw_step_if.strip():
                            raise IntentConfigError(
                                f"{path}: invalid [ci].jobs[{job_idx}].steps[{step_idx}].if "
                                "(expected non-empty string)"
                            )
                        step_if = raw_step_if.strip()

                    step_continue_on_error = False
                    raw_step_coe = raw_step.get("continue_on_error")
                    if raw_step_coe is not None:
                        if not isinstance(raw_step_coe, bool):
                            raise IntentConfigError(
                                f"{path}: invalid [ci].jobs[{job_idx}].steps[{step_idx}]."
                                "continue_on_error (expected boolean)"
                            )
                        step_continue_on_error = raw_step_coe

                    working_directory: str | None = None
                    raw_working_dir = raw_step.get("working_directory")
                    if raw_working_dir is not None:
                        if not isinstance(raw_working_dir, str) or not raw_working_dir.strip():
                            raise IntentConfigError(
                                f"{path}: invalid [ci].jobs[{job_idx}].steps[{step_idx}]."
                                "working_directory (expected non-empty string)"
                            )
                        working_directory = raw_working_dir.strip()

                    env: dict[str, str] | None = None
                    raw_env = raw_step.get("env")
                    if raw_env is not None:
                        if not isinstance(raw_env, dict):
                            raise IntentConfigError(
                                f"{path}: invalid [ci].jobs[{job_idx}].steps[{step_idx}].env "
                                "(expected table/object)"
                            )
                        parsed_env: dict[str, str] = {}
                        for key, val in raw_env.items():
                            if not isinstance(key, str) or not key.strip():
                                raise IntentConfigError(
                                    f"{path}: invalid [ci].jobs[{job_idx}].steps[{step_idx}].env key "
                                    "(expected non-empty string)"
                                )
                            if not isinstance(val, str):
                                raise IntentConfigError(
                                    f"{path}: invalid [ci].jobs[{job_idx}].steps[{step_idx}].env."
                                    f"{key} (expected string)"
                                )
                            parsed_env[key.strip()] = val
                        env = parsed_env or None

                    parsed_steps.append(
                        CiStep(
                            name=step_name,
                            run=run,
                            command=command,
                            uses=uses,
                            with_args=with_args,
                            if_condition=step_if,
                            continue_on_error=step_continue_on_error,
                            working_directory=working_directory,
                            env=env,
                        )
                    )

                parsed_jobs.append(
                    CiJob(
                        name=job_name,
                        runs_on=runs_on,
                        needs=needs,
                        if_condition=if_condition,
                        timeout_minutes=timeout_minutes,
                        continue_on_error=continue_on_error,
                        matrix=matrix,
                        steps=parsed_steps,
                    )
                )

            known_jobs = {job.name for job in parsed_jobs}
            for job in parsed_jobs:
                for need in job.needs or []:
                    if need not in known_jobs:
                        raise IntentConfigError(
                            f"{path}: invalid [ci].jobs[{job.name!r}].needs "
                            f"(unknown job {need!r})"
                        )
            ci_jobs = parsed_jobs
        raw_artifacts = ci_section.get("artifacts")
        if raw_artifacts is not None:
            if not isinstance(raw_artifacts, list) or not raw_artifacts:
                raise IntentConfigError("[ci].artifacts must be a non-empty array of tables")
            parsed_artifacts: list[CiArtifact] = []
            for artifact_idx, raw_artifact in enumerate(raw_artifacts):
                if not isinstance(raw_artifact, dict):
                    raise IntentConfigError(
                        f"{path}: invalid [ci].artifacts[{artifact_idx}] "
                        "(expected table/object)"
                    )
                raw_name = raw_artifact.get("name")
                if not isinstance(raw_name, str) or not raw_name.strip():
                    raise IntentConfigError(
                        f"{path}: invalid [ci].artifacts[{artifact_idx}].name "
                        "(expected non-empty string)"
                    )
                raw_path = raw_artifact.get("path")
                if not isinstance(raw_path, str) or not raw_path.strip():
                    raise IntentConfigError(
                        f"{path}: invalid [ci].artifacts[{artifact_idx}].path "
                        "(expected non-empty string)"
                    )

                retention_days: int | None = None
                raw_retention_days = raw_artifact.get("retention_days")
                if raw_retention_days is not None:
                    if not isinstance(raw_retention_days, int) or raw_retention_days <= 0:
                        raise IntentConfigError(
                            f"{path}: invalid [ci].artifacts[{artifact_idx}].retention_days "
                            "(expected positive integer)"
                        )
                    retention_days = raw_retention_days

                when = "always"
                raw_when = raw_artifact.get("when")
                if raw_when is not None:
                    if not isinstance(raw_when, str) or not raw_when.strip():
                        raise IntentConfigError(
                            f"{path}: invalid [ci].artifacts[{artifact_idx}].when "
                            "(expected non-empty string)"
                        )
                    when = raw_when.strip()
                    if when not in CI_ARTIFACT_WHEN:
                        allowed_when = ", ".join(sorted(CI_ARTIFACT_WHEN))
                        raise IntentConfigError(
                            f"{path}: invalid [ci].artifacts[{artifact_idx}].when "
                            f"(expected one of {allowed_when}, got {when!r})"
                        )
                parsed_artifacts.append(
                    CiArtifact(
                        name=raw_name.strip(),
                        path=raw_path.strip(),
                        retention_days=retention_days,
                        when=when,
                    )
                )
            ci_artifacts = parsed_artifacts
        raw_summary = ci_section.get("summary")
        if raw_summary is not None:
            if not isinstance(raw_summary, dict):
                raise _field_type_error(path, "[ci].summary", "table/object", raw_summary)
            enabled = True
            raw_enabled = raw_summary.get("enabled")
            if raw_enabled is not None:
                if not isinstance(raw_enabled, bool):
                    raise IntentConfigError(
                        f"{path}: invalid [ci].summary.enabled (expected boolean)"
                    )
                enabled = raw_enabled

            title = "Intent CI Summary"
            raw_title = raw_summary.get("title")
            if raw_title is not None:
                if not isinstance(raw_title, str) or not raw_title.strip():
                    raise IntentConfigError(
                        f"{path}: invalid [ci].summary.title (expected non-empty string)"
                    )
                title = raw_title.strip()

            include_assertions = True
            raw_include_assertions = raw_summary.get("include_assertions")
            if raw_include_assertions is not None:
                if not isinstance(raw_include_assertions, bool):
                    raise IntentConfigError(
                        f"{path}: invalid [ci].summary.include_assertions (expected boolean)"
                    )
                include_assertions = raw_include_assertions

            summary_metrics: list[CiSummaryMetric] | None = None
            raw_metrics = raw_summary.get("metrics")
            if raw_metrics is not None:
                if not isinstance(raw_metrics, list):
                    raise IntentConfigError(
                        f"{path}: invalid [ci].summary.metrics (expected array of tables)"
                    )
                parsed_metrics: list[CiSummaryMetric] = []
                for metric_idx, raw_metric in enumerate(raw_metrics):
                    if not isinstance(raw_metric, dict):
                        raise IntentConfigError(
                            f"{path}: invalid [ci].summary.metrics[{metric_idx}] "
                            "(expected table/object)"
                        )
                    raw_label = raw_metric.get("label")
                    if not isinstance(raw_label, str) or not raw_label.strip():
                        raise IntentConfigError(
                            f"{path}: invalid [ci].summary.metrics[{metric_idx}].label "
                            "(expected non-empty string)"
                        )
                    raw_command = raw_metric.get("command")
                    if not isinstance(raw_command, str) or not raw_command.strip():
                        raise IntentConfigError(
                            f"{path}: invalid [ci].summary.metrics[{metric_idx}].command "
                            "(expected non-empty string)"
                        )
                    command = raw_command.strip()
                    if command not in commands:
                        raise IntentConfigError(
                            f"{path}: invalid [ci].summary.metrics[{metric_idx}].command "
                            f"(unknown command {command!r})"
                        )
                    raw_metric_path = raw_metric.get("path")
                    if not isinstance(raw_metric_path, str) or not raw_metric_path.strip():
                        raise IntentConfigError(
                            f"{path}: invalid [ci].summary.metrics[{metric_idx}].path "
                            "(expected non-empty string)"
                        )
                    baseline_path: str | None = None
                    raw_baseline_path = raw_metric.get("baseline_path")
                    if raw_baseline_path is not None:
                        if not isinstance(raw_baseline_path, str) or not raw_baseline_path.strip():
                            raise IntentConfigError(
                                f"{path}: invalid [ci].summary.metrics[{metric_idx}].baseline_path "
                                "(expected non-empty string)"
                            )
                        baseline_path = raw_baseline_path.strip()

                    precision: int | None = None
                    raw_precision = raw_metric.get("precision")
                    if raw_precision is not None:
                        if not isinstance(raw_precision, int) or raw_precision < 0:
                            raise IntentConfigError(
                                f"{path}: invalid [ci].summary.metrics[{metric_idx}].precision "
                                "(expected integer >= 0)"
                            )
                        precision = raw_precision
                    parsed_metrics.append(
                        CiSummaryMetric(
                            label=raw_label.strip(),
                            command=command,
                            path=raw_metric_path.strip(),
                            baseline_path=baseline_path,
                            precision=precision,
                        )
                    )
                summary_metrics = parsed_metrics or None

            ci_summary = CiSummary(
                enabled=enabled,
                title=title,
                include_assertions=include_assertions,
                metrics=summary_metrics,
            )

    plugins_section = data.get("plugins")
    if plugins_section is not None:
        if not isinstance(plugins_section, dict):
            raise _field_type_error(path, "[plugins]", "table/object", plugins_section)
        raw_check_hooks = plugins_section.get("check")
        if raw_check_hooks is not None:
            if not isinstance(raw_check_hooks, list):
                raise _field_type_error(
                    path, "[plugins].check", "array of strings", raw_check_hooks
                )
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

    checks_section = data.get("checks")
    if checks_section is not None:
        if not isinstance(checks_section, dict):
            raise _field_type_error(path, "[checks]", "table/object", checks_section)
        raw_assertions = checks_section.get("assertions")
        if raw_assertions is not None:
            if not isinstance(raw_assertions, list):
                raise _field_type_error(
                    path, "[checks].assertions", "array of tables", raw_assertions
                )
            parsed_assertions: list[CheckAssertion] = []
            for idx, raw in enumerate(raw_assertions):
                if not isinstance(raw, dict):
                    raise IntentConfigError(
                        f"{path}: invalid [checks].assertions[{idx}] "
                        "(expected table/object)"
                    )
                command = raw.get("command")
                if not isinstance(command, str) or not command.strip():
                    raise IntentConfigError(
                        f"{path}: invalid [checks].assertions[{idx}].command "
                        "(expected non-empty string)"
                    )
                command = command.strip()
                if command not in commands:
                    raise IntentConfigError(
                        f"{path}: invalid [checks].assertions[{idx}].command "
                        f"(unknown command {command!r})"
                    )

                check_path = raw.get("path")
                if not isinstance(check_path, str) or not check_path.strip():
                    raise IntentConfigError(
                        f"{path}: invalid [checks].assertions[{idx}].path "
                        "(expected non-empty string)"
                    )
                check_path = check_path.strip()

                op = raw.get("op")
                if not isinstance(op, str) or not op.strip():
                    raise IntentConfigError(
                        f"{path}: invalid [checks].assertions[{idx}].op "
                        "(expected non-empty string)"
                    )
                op = op.strip()
                if op not in CHECK_ASSERTION_OPERATORS:
                    allowed_ops = ", ".join(sorted(CHECK_ASSERTION_OPERATORS))
                    raise IntentConfigError(
                        f"{path}: invalid [checks].assertions[{idx}].op "
                        f"(expected one of {allowed_ops}, got {op!r})"
                    )

                if "value" not in raw:
                    raise IntentConfigError(
                        f"{path}: invalid [checks].assertions[{idx}].value (field is required)"
                    )
                expected_value = raw["value"]
                if op in {"in", "not_in"} and not isinstance(expected_value, list):
                    raise IntentConfigError(
                        f"{path}: invalid [checks].assertions[{idx}].value "
                        f"(expected array for op={op!r})"
                    )

                message = raw.get("message")
                if message is not None and (not isinstance(message, str) or not message.strip()):
                    raise IntentConfigError(
                        f"{path}: invalid [checks].assertions[{idx}].message "
                        "(expected non-empty string)"
                    )
                parsed_assertions.append(
                    CheckAssertion(
                        command=command,
                        path=check_path,
                        op=op,
                        value=expected_value,
                        message=message.strip() if isinstance(message, str) else None,
                    )
                )
            checks_assertions = parsed_assertions or None
    schema_version = DEFAULT_SCHEMA_VERSION
    intent_section = data.get("intent")
    if isinstance(intent_section, dict):
        schema_version = intent_section["schema_version"]

    policy_pack: str | None = None
    policy_strict = DEFAULT_POLICY_STRICT
    policy_section = data.get("policy")
    if isinstance(policy_section, dict):
        raw_pack = policy_section.get("pack")
        if raw_pack is not None:
            policy_pack = raw_pack.strip()
            policy_strict = POLICY_PACKS[policy_pack]["strict"]
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
        ci_jobs=ci_jobs,
        ci_artifacts=ci_artifacts,
        ci_summary=ci_summary,
        plugin_check_hooks=plugin_check_hooks,
        plugin_generate_hooks=plugin_generate_hooks,
        checks_assertions=checks_assertions,
        policy_pack=policy_pack,
        policy_strict=policy_strict,
    )
