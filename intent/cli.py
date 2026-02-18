# intent/cli.py
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Literal

import typer

from . import __version__
from .config import CheckAssertion, CiSummaryMetric, IntentConfigError, load_intent
from .fs import GENERATED_MARKER, OwnershipError, write_generated_file
from .pyproject_reader import PyprojectPythonStatus, read_pyproject_python
from .render_ci import render_ci
from .render_just import render_just
from .versioning import (
    check_requires_python_range,
    max_lower_bound,
    parse_version,
    parse_pep440_version,
)

app = typer.Typer(help="Intent CLI", invoke_without_command=True)

ERR_USAGE_CONFLICT = "INTENT001"
ERR_CONFIG_NOT_FOUND = "INTENT002"
ERR_CONFIG_INVALID = "INTENT003"
ERR_OWNERSHIP = "INTENT004"
ERR_INIT_EXISTS = "INTENT005"
ERR_VERSION = "INTENT101"
ERR_FILE_MISSING = "INTENT201"
ERR_FILE_UNOWNED = "INTENT202"
ERR_FILE_OUTDATED = "INTENT203"
ERR_PLUGIN = "INTENT301"
ERR_CHECK = "INTENT401"


@app.callback()
def _root(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", help="Show version and exit", is_eager=True),
) -> None:
    if version:
        typer.echo(__version__)
        raise typer.Exit(code=0)

    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit(code=0)


def _preview_status(path: Path, new_content: str) -> str:
    if not path.exists():
        return f"Would write {path}"

    existing = path.read_text(encoding="utf-8")
    if GENERATED_MARKER not in existing:
        return f"Cannot update {path}: exists but is not tool-owned (missing marker)"
    if existing == new_content:
        return f"No changes to {path}"
    return f"Would update {path}"


def _generated_drift_status(path: Path, new_content: str) -> tuple[bool, str, str | None]:
    if not path.exists():
        return False, f"{path} is missing", ERR_FILE_MISSING

    existing = path.read_text(encoding="utf-8")
    if GENERATED_MARKER not in existing:
        return False, f"{path} exists but is not tool-owned (missing marker)", ERR_FILE_UNOWNED
    if existing != new_content:
        return False, f"{path} is out of date", ERR_FILE_OUTDATED
    return True, f"{path} is up to date", None


def _run_plugin_hooks(hooks: list[str] | None, stage: str) -> list[dict]:
    results: list[dict] = []
    for command in hooks or []:
        proc = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
        )
        results.append(
            {
                "stage": stage,
                "command": command,
                "ok": proc.returncode == 0,
                "exit_code": proc.returncode,
                "stdout": proc.stdout.strip(),
                "stderr": proc.stderr.strip(),
                "code": None if proc.returncode == 0 else ERR_PLUGIN,
            }
        )
    return results


def _run_json_commands(commands: dict[str, str], command_names: set[str]) -> dict[str, dict]:
    results: dict[str, dict] = {}
    for command_name in sorted(command_names):
        command = commands[command_name]
        proc = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
        )
        stdout = proc.stdout.strip()
        stderr = proc.stderr.strip()
        if proc.returncode != 0:
            results[command_name] = {
                "ok": False,
                "error": f"command failed with exit code {proc.returncode}",
                "stdout": stdout,
                "stderr": stderr,
            }
            continue

        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError as e:
            results[command_name] = {
                "ok": False,
                "error": f"stdout is not valid JSON: {e.msg}",
                "stdout": stdout,
                "stderr": stderr,
            }
            continue

        results[command_name] = {
            "ok": True,
            "payload": payload,
            "stdout": stdout,
            "stderr": stderr,
        }
    return results


def _json_path_tokens(path: str) -> list[str | int]:
    tokens: list[str | int] = []
    if not path or not path.strip():
        raise ValueError("path cannot be empty")

    for part in path.split("."):
        if not part:
            raise ValueError(f"invalid path segment in {path!r}")
        pos = 0
        key_match = re.match(r"[A-Za-z0-9_-]+", part[pos:])
        if not key_match:
            raise ValueError(f"invalid key segment in {path!r}")
        key = key_match.group(0)
        tokens.append(key)
        pos += len(key)

        while pos < len(part):
            index_match = re.match(r"\[(\d+)\]", part[pos:])
            if not index_match:
                raise ValueError(f"invalid index segment in {path!r}")
            tokens.append(int(index_match.group(1)))
            pos += len(index_match.group(0))
    return tokens


def _resolve_json_path(payload: object, path: str) -> tuple[bool, object | None, str | None]:
    try:
        tokens = _json_path_tokens(path)
    except ValueError as e:
        return False, None, str(e)

    cur: object = payload
    for token in tokens:
        if isinstance(token, str):
            if not isinstance(cur, dict):
                return False, None, f"path segment {token!r} expects object, got {type(cur).__name__}"
            if token not in cur:
                return False, None, f"path segment {token!r} missing"
            cur = cur[token]
        else:
            if not isinstance(cur, list):
                return False, None, f"path index [{token}] expects array, got {type(cur).__name__}"
            if token >= len(cur):
                return False, None, f"path index [{token}] out of range"
            cur = cur[token]
    return True, cur, None


def _compare_assertion(actual: object, op: str, expected: object) -> tuple[bool, str | None]:
    if op == "eq":
        return actual == expected, None
    if op == "ne":
        return actual != expected, None

    if op == "in":
        if not isinstance(expected, list):
            return False, "expected array for 'in' operator"
        return actual in expected, None
    if op == "not_in":
        if not isinstance(expected, list):
            return False, "expected array for 'not_in' operator"
        return actual not in expected, None

    try:
        if op == "gt":
            return actual > expected, None
        if op == "gte":
            return actual >= expected, None
        if op == "lt":
            return actual < expected, None
        if op == "lte":
            return actual <= expected, None
    except TypeError:
        return False, f"incompatible types for operator {op!r}"

    return False, f"unsupported operator {op!r}"


def _run_check_assertions(
    assertions: list[CheckAssertion] | None,
    command_results: dict[str, dict],
) -> list[dict]:
    if not assertions:
        return []

    results: list[dict] = []
    for assertion in assertions:
        command_result = command_results[assertion.command]
        base = {
            "command": assertion.command,
            "path": assertion.path,
            "op": assertion.op,
            "expected": assertion.value,
            "message": assertion.message,
            "code": None,
        }
        if not command_result["ok"]:
            results.append(
                {
                    **base,
                    "ok": False,
                    "actual": None,
                    "reason": command_result["error"],
                    "code": ERR_CHECK,
                }
            )
            continue

        found, actual, path_error = _resolve_json_path(command_result["payload"], assertion.path)
        if not found:
            results.append(
                {
                    **base,
                    "ok": False,
                    "actual": None,
                    "reason": path_error,
                    "code": ERR_CHECK,
                }
            )
            continue

        ok, compare_error = _compare_assertion(actual, assertion.op, assertion.value)
        results.append(
            {
                **base,
                "ok": ok,
                "actual": actual,
                "reason": compare_error if compare_error else None,
                "code": None if ok else ERR_CHECK,
            }
        )
    return results


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _apply_precision(value: object, precision: int | None) -> object:
    if precision is None or not _is_number(value):
        return value
    return round(float(value), precision)


def _evaluate_summary_metrics(
    metrics: list[CiSummaryMetric] | None,
    command_results: dict[str, dict],
) -> list[dict]:
    if not metrics:
        return []
    results: list[dict] = []
    for metric in metrics:
        command_result = command_results[metric.command]
        base = {
            "label": metric.label,
            "command": metric.command,
            "path": metric.path,
            "baseline_path": metric.baseline_path,
            "precision": metric.precision,
            "code": None,
        }
        if not command_result["ok"]:
            results.append(
                {
                    **base,
                    "ok": False,
                    "value": None,
                    "baseline": None,
                    "delta": None,
                    "reason": command_result["error"],
                    "code": ERR_CHECK,
                }
            )
            continue

        payload = command_result["payload"]
        found_value, value, value_error = _resolve_json_path(payload, metric.path)
        if not found_value:
            results.append(
                {
                    **base,
                    "ok": False,
                    "value": None,
                    "baseline": None,
                    "delta": None,
                    "reason": value_error,
                    "code": ERR_CHECK,
                }
            )
            continue

        baseline = None
        delta = None
        reason: str | None = None
        if metric.baseline_path:
            found_baseline, baseline_value, baseline_error = _resolve_json_path(
                payload, metric.baseline_path
            )
            if not found_baseline:
                results.append(
                    {
                        **base,
                        "ok": False,
                        "value": _apply_precision(value, metric.precision),
                        "baseline": None,
                        "delta": None,
                        "reason": baseline_error,
                        "code": ERR_CHECK,
                    }
                )
                continue
            baseline = baseline_value
            if _is_number(value) and _is_number(baseline):
                delta = float(value) - float(baseline)
            else:
                reason = "delta requires numeric value and baseline"

        results.append(
            {
                **base,
                "ok": True,
                "value": _apply_precision(value, metric.precision),
                "baseline": _apply_precision(baseline, metric.precision),
                "delta": _apply_precision(delta, metric.precision),
                "reason": reason,
            }
        )
    return results


def _render_summary_markdown(
    title: str,
    include_assertions: bool,
    assertions: list[dict],
    metrics: list[dict],
) -> str:
    lines = [f"## {title}", ""]
    if include_assertions:
        total = len(assertions)
        passed = sum(1 for item in assertions if item["ok"])
        failed = total - passed
        lines.append("### Assertions")
        lines.append("")
        lines.append(f"- Passed: {passed}")
        lines.append(f"- Failed: {failed}")
        lines.append("")
    if metrics:
        lines.append("### Metrics")
        lines.append("")
        lines.append("| Metric | Value | Baseline | Delta |")
        lines.append("| --- | ---: | ---: | ---: |")
        for metric in metrics:
            value = metric["value"] if metric["value"] is not None else "-"
            baseline = metric["baseline"] if metric["baseline"] is not None else "-"
            delta = metric["delta"] if metric["delta"] is not None else "-"
            lines.append(f"| {metric['label']} | {value} | {baseline} | {delta} |")
        lines.append("")
    return "\n".join(lines).rstrip()


def _resolved_payload(path: Path, cfg: object) -> dict:
    pyproject_status, pyproject_requires_python = read_pyproject_python()
    return {
        "ok": True,
        "intent_path": str(path),
        "schema_version": cfg.schema_version,
        "python_version": cfg.python_version,
        "policy_pack": cfg.policy_pack,
        "policy_strict": cfg.policy_strict,
        "ci_install": cfg.ci_install,
        "commands": cfg.commands,
        "ci_jobs": [
            {
                "name": job.name,
                "runs_on": job.runs_on,
                "needs": job.needs,
                "if": job.if_condition,
                "timeout_minutes": job.timeout_minutes,
                "continue_on_error": job.continue_on_error,
                "matrix": job.matrix,
                "steps": [
                    {
                        "name": step.name,
                        "run": step.run,
                        "command": step.command,
                        "uses": step.uses,
                        "with": step.with_args,
                        "if": step.if_condition,
                        "continue_on_error": step.continue_on_error,
                        "working_directory": step.working_directory,
                        "env": step.env,
                    }
                    for step in (job.steps or [])
                ],
            }
            for job in (cfg.ci_jobs or [])
        ],
        "ci_artifacts": [
            {
                "name": artifact.name,
                "path": artifact.path,
                "retention_days": artifact.retention_days,
                "when": artifact.when,
            }
            for artifact in (cfg.ci_artifacts or [])
        ],
        "ci_summary": (
            {
                "enabled": cfg.ci_summary.enabled,
                "title": cfg.ci_summary.title,
                "include_assertions": cfg.ci_summary.include_assertions,
                "metrics": [
                    {
                        "label": metric.label,
                        "command": metric.command,
                        "path": metric.path,
                        "baseline_path": metric.baseline_path,
                        "precision": metric.precision,
                    }
                    for metric in (cfg.ci_summary.metrics or [])
                ],
            }
            if cfg.ci_summary
            else None
        ),
        "checks": [
            {
                "command": assertion.command,
                "path": assertion.path,
                "op": assertion.op,
                "value": assertion.value,
                "message": assertion.message,
            }
            for assertion in (cfg.checks_assertions or [])
        ],
        "pyproject": {
            "status": pyproject_status.value,
            "requires_python": pyproject_requires_python,
        },
    }


def _sync_explain_payload(cfg: object) -> dict:
    workflow_steps = ["checkout", "setup-python", "install-deps"]
    if cfg.ci_jobs:
        workflow_steps = ["custom-jobs"]

    return {
        "generated_files": [
            {
                "path": ".github/workflows/ci.yml",
                "renderer": "render_ci",
                "inputs": [
                    "[python].version",
                    "[commands]",
                    "[ci].install",
                    "[ci].cache",
                    "[ci].python_versions",
                    "[ci].triggers",
                    "[ci].jobs",
                    "[ci].artifacts",
                    "[ci].summary",
                ],
                "blocks": workflow_steps,
                "owned": True,
            },
            {
                "path": "justfile",
                "renderer": "render_just",
                "inputs": ["[commands]"],
                "blocks": ["recipes-from-commands"],
                "owned": True,
            },
        ]
    }


def _print_sync_explain_text(cfg: object) -> None:
    typer.echo("--- explain ---")
    typer.echo(".github/workflows/ci.yml")
    typer.echo("  renderer: render_ci")
    typer.echo(
        "  inputs: [python].version, [commands], [ci].install, [ci].cache, "
        "[ci].python_versions, [ci].triggers, [ci].jobs, [ci].artifacts, [ci].summary"
    )
    if cfg.ci_jobs:
        typer.echo("  blocks: custom-jobs")
    else:
        typer.echo("  blocks: checkout, setup-python, install-deps, command-steps")
    typer.echo("justfile")
    typer.echo("  renderer: render_just")
    typer.echo("  inputs: [commands]")
    typer.echo("  blocks: recipes-from-commands")


def _check_versions(cfg_python: str, strict: bool) -> tuple[bool, str, str | None]:
    """
    Semantics:
    - If incompatible -> fail
    - If compatible but pyproject is broader than intent -> warn (or fail if strict)
    """
    status, pyproject_version = read_pyproject_python()

    if status == PyprojectPythonStatus.FILE_MISSING:
        return True, "note: pyproject.toml not found; version cross-check skipped", None
    if status == PyprojectPythonStatus.PROJECT_MISSING:
        return (
            True,
            "note: pyproject.toml has no [project] table; version cross-check skipped",
            None,
        )
    if status == PyprojectPythonStatus.REQUIRES_PYTHON_MISSING:
        return True, "note: [project].requires-python not set; version cross-check skipped", None
    if status == PyprojectPythonStatus.INVALID:
        if strict:
            return False, "invalid requires-python value in pyproject.toml", ERR_VERSION
        return True, "note: invalid requires-python value; version cross-check skipped", None

    if pyproject_version is None:
        return True, "note: [project].requires-python not set; version cross-check skipped", None

    spec = pyproject_version.strip()

    # Simple spec: no operators => treat as equality
    if not any(ch in spec for ch in "<>,="):
        spec_version = parse_pep440_version(spec)
        cfg_version = parse_pep440_version(cfg_python)
        if spec_version is None:
            if strict:
                return False, f"Unsupported requires_python spec (strict): {spec}", ERR_VERSION
            return True, f"note: Unsupported requires_python spec (skipping): {spec}", None
        if cfg_version is not None and spec_version == cfg_version:
            return True, f"pyproject requires_python matches intent ({spec})", None
        return (
            False,
            f"Version mismatch (simple spec): intent={cfg_python} vs pyproject={spec}",
            ERR_VERSION,
        )

    # Range-ish spec: best-effort compatibility check
    result = check_requires_python_range(cfg_python, spec)
    if result is False:
        return (
            False,
            f"Version mismatch (range): intent {cfg_python} does not satisfy {spec}",
            ERR_VERSION,
        )
    if result is None:
        if strict:
            return False, f"Unsupported requires_python spec (strict): {spec}", ERR_VERSION
        return True, f"note: Unsupported requires_python spec (skipping): {spec}", None

    # Compatible. Now detect "precision drift": pyproject broader than intent.
    intent_parsed = parse_pep440_version(cfg_python)
    if intent_parsed is None:
        return True, f"note: could not parse intent python.version ({cfg_python})", None
    lower = max_lower_bound(spec)

    if lower is not None and lower < intent_parsed:
        msg = (
            f"pyproject requires_python ({spec}) is broader than intent ({cfg_python}); "
            "consider tightening pyproject to match intent"
        )
        if strict:
            return False, msg, ERR_VERSION
        return True, f"note: {msg}", None

    return True, f"Version ok (range): intent {cfg_python} satisfies {spec}", None


def _render_intent_template(python_version: str) -> str:
    lines = [
        "[intent]",
        "schema_version = 1",
        "",
        "[python]",
        f'version = "{python_version}"',
        "",
        "[commands]",
        'test = "pytest -q"',
        'lint = "ruff check ."',
        "",
        "[ci]",
        'install = "-e .[dev]"',
        "",
        "[policy]",
        'pack = "default"',
        "strict = false",
        "",
    ]
    return "\n".join(lines)


def _python_env_tag(python_version: str) -> str:
    parsed = parse_version(python_version)
    if parsed is None or len(parsed) < 2:
        return "py312"
    return f"py{parsed[0]}{parsed[1]}"


def _render_tox_ini_template(python_version: str) -> str:
    env_tag = _python_env_tag(python_version)
    lines = [
        GENERATED_MARKER,
        "# DO NOT EDIT",
        "",
        "[tox]",
        f"envlist = {env_tag}",
        "",
        "[testenv]",
        "deps =",
        "    -e .[dev]",
        "commands =",
        "    pytest -q",
        "",
    ]
    return "\n".join(lines)


def _render_noxfile_template() -> str:
    lines = [
        GENERATED_MARKER,
        "# DO NOT EDIT",
        "",
        "import nox",
        "",
        "",
        "@nox.session",
        "def tests(session):",
        '    session.install("-e", ".[dev]")',
        '    session.run("pytest", "-q")',
        "",
    ]
    return "\n".join(lines)


def _infer_init_python_version(from_existing: bool) -> tuple[str, str]:
    default_version = "3.12"
    if not from_existing:
        return default_version, "default"

    status, raw = read_pyproject_python()
    if status != PyprojectPythonStatus.OK or raw is None:
        return default_version, "default"

    spec = raw.strip()
    if not spec:
        return default_version, "default"

    if not any(ch in spec for ch in "<>,="):
        parsed = parse_pep440_version(spec)
        if parsed is None:
            return default_version, "default"
        return f"{parsed.major}.{parsed.minor}", "pyproject"

    lower = max_lower_bound(spec)
    if lower is not None:
        return f"{lower.major}.{lower.minor}", "pyproject"

    if spec.startswith("==") and "," not in spec:
        parsed = parse_pep440_version(spec[2:].strip())
        if parsed is not None:
            return f"{parsed.major}.{parsed.minor}", "pyproject"

    return default_version, "default"


def _read_python_version_file(path: Path = Path(".python-version")) -> str | None:
    if not path.exists():
        return None
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return None
    return raw.splitlines()[0].strip() or None


def _read_tool_versions_python(path: Path = Path(".tool-versions")) -> str | None:
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = stripped.split()
        if len(parts) >= 2 and parts[0] == "python":
            return parts[1].strip() or None
    return None


def _same_major_minor(lhs: str, rhs: str) -> bool:
    left = parse_version(lhs)
    right = parse_version(rhs)
    if left is None or right is None or len(left) < 2 or len(right) < 2:
        return False
    return left[:2] == right[:2]


def _next_minor(version: str) -> str | None:
    parsed = parse_version(version)
    if parsed is None or len(parsed) < 2:
        return None
    major, minor = parsed[0], parsed[1]
    return f"{major}.{minor + 1}"


def _upsert_pyproject_requires_python(path: Path, new_spec: str) -> tuple[bool, str]:
    if not path.exists():
        content = (
            f'[project]\nname = "REPLACE_ME"\nversion = "0.0.0"\nrequires-python = "{new_spec}"\n'
        )
        path.write_text(content, encoding="utf-8")
        return True, "created"

    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    section_re = re.compile(r"^\s*\[([^\[\]]+)\]\s*$")

    project_start: int | None = None
    project_end = len(lines)
    for idx, line in enumerate(lines):
        match = section_re.match(line)
        if not match:
            continue
        section = match.group(1).strip()
        if section == "project":
            project_start = idx
            continue
        if project_start is not None:
            project_end = idx
            break

    changed = False
    new_line = f'requires-python = "{new_spec}"'

    if project_start is None:
        if lines and lines[-1].strip():
            lines.append("")
        lines.extend(["[project]", new_line])
        changed = True
    else:
        requires_idx: int | None = None
        for idx in range(project_start + 1, project_end):
            stripped = lines[idx].strip()
            if stripped.startswith("requires-python") and "=" in stripped:
                requires_idx = idx
                break
        if requires_idx is None:
            lines.insert(project_start + 1, new_line)
            changed = True
        elif lines[requires_idx].strip() != new_line:
            lines[requires_idx] = new_line
            changed = True

    if changed:
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return True, "updated" if path.exists() else "created"
    return False, "unchanged"


def _write_python_version(path: Path, version: str) -> tuple[bool, str]:
    new_text = f"{version}\n"
    if not path.exists():
        path.write_text(new_text, encoding="utf-8")
        return True, "created"
    existing = path.read_text(encoding="utf-8")
    if existing == new_text:
        return False, "unchanged"
    path.write_text(new_text, encoding="utf-8")
    return True, "updated"


def _upsert_tool_versions_python(path: Path, version: str) -> tuple[bool, str]:
    new_line = f"python {version}"
    if not path.exists():
        path.write_text(new_line + "\n", encoding="utf-8")
        return True, "created"

    lines = path.read_text(encoding="utf-8").splitlines()
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = stripped.split()
        if len(parts) >= 2 and parts[0] == "python":
            if stripped == new_line:
                return False, "unchanged"
            lines[idx] = new_line
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            return True, "updated"

    if lines and lines[-1].strip():
        lines.append("")
    lines.append(new_line)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return True, "updated"


@app.command()
def init(
    intent_path: str = "intent.toml",
    from_existing: bool = False,
    force: bool = False,
    starter: list[str] = typer.Option(
        [],
        "--starter",
        help="Optional starter files to generate: tox, nox (repeatable)",
    ),
) -> None:
    """
    Create a starter intent.toml.

    --from-existing: infer python version from pyproject.toml when possible.
    --force:         overwrite an existing intent.toml.
    """
    starters = list(dict.fromkeys(starter))
    allowed_starters = {"tox", "nox"}
    invalid_starters = [item for item in starters if item not in allowed_starters]
    if invalid_starters:
        invalid = ", ".join(invalid_starters)
        typer.echo(
            f"[{ERR_USAGE_CONFLICT}] Error: invalid --starter value(s): {invalid} "
            "(expected: tox, nox)",
            err=True,
        )
        raise typer.Exit(code=2)

    path = Path(intent_path)
    wrote_intent = False
    python_version, source = _infer_init_python_version(from_existing)
    if path.exists() and not force:
        if not starters:
            typer.echo(
                f"[{ERR_INIT_EXISTS}] Refusing to overwrite existing file: {path} (use --force)",
                err=True,
            )
            raise typer.Exit(code=2)
        try:
            existing_cfg = load_intent(path)
            python_version = existing_cfg.python_version
            typer.echo(f"Using existing {path}")
        except FileNotFoundError as e:
            typer.echo(f"[{ERR_CONFIG_NOT_FOUND}] Error: {e}", err=True)
            raise typer.Exit(code=2)
        except IntentConfigError as e:
            typer.echo(f"[{ERR_CONFIG_INVALID}] Config error: {e}", err=True)
            raise typer.Exit(code=2)
    else:
        content = _render_intent_template(python_version)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        wrote_intent = True
        typer.echo(f"Wrote {path}")

    for item in starters:
        try:
            if item == "tox":
                changed = write_generated_file(
                    Path("tox.ini"), _render_tox_ini_template(python_version)
                )
                typer.echo("Wrote tox.ini" if changed else "No changes to tox.ini")
            elif item == "nox":
                changed = write_generated_file(Path("noxfile.py"), _render_noxfile_template())
                typer.echo("Wrote noxfile.py" if changed else "No changes to noxfile.py")
        except OwnershipError as e:
            typer.echo(f"[{ERR_OWNERSHIP}] {e}", err=True)
            raise typer.Exit(code=1)

    if from_existing and wrote_intent:
        typer.echo(f"python.version = {python_version} ({source})")


@app.command()
def show(
    intent_path: str = "intent.toml",
    output_format: Literal["text", "json"] = typer.Option("text", "--format"),
) -> None:
    """
    Show resolved Intent config and related inspection info.
    """
    path = Path(intent_path)
    try:
        cfg = load_intent(path)
    except FileNotFoundError as e:
        if output_format == "json":
            typer.echo(
                json.dumps(
                    {
                        "ok": False,
                        "error": {"kind": "config", "message": f"{e}"},
                        "code": ERR_CONFIG_NOT_FOUND,
                    }
                )
            )
            raise typer.Exit(code=2)
        typer.echo(f"[{ERR_CONFIG_NOT_FOUND}] Error: {e}", err=True)
        raise typer.Exit(code=2)
    except IntentConfigError as e:
        if output_format == "json":
            typer.echo(
                json.dumps(
                    {
                        "ok": False,
                        "error": {"kind": "config", "message": f"{e}"},
                        "code": ERR_CONFIG_INVALID,
                    }
                )
            )
            raise typer.Exit(code=2)
        typer.echo(f"[{ERR_CONFIG_INVALID}] Config error: {e}", err=True)
        raise typer.Exit(code=2)

    resolved = _resolved_payload(path, cfg)
    pyproject_status = PyprojectPythonStatus(resolved["pyproject"]["status"])
    pyproject_requires_python = resolved["pyproject"]["requires_python"]

    if output_format == "json":
        typer.echo(json.dumps(resolved))
        raise typer.Exit(code=0)

    typer.echo(f"Intent path: {path}")
    typer.echo(f"Schema version: {cfg.schema_version}")
    typer.echo(f"Python version: {cfg.python_version}")
    typer.echo(f"Policy pack: {cfg.policy_pack or 'none'}")
    typer.echo(f"Policy strict: {cfg.policy_strict}")
    typer.echo(f"CI install: {cfg.ci_install}")
    typer.echo("Commands:")
    for name, cmd in cfg.commands.items():
        typer.echo(f"  {name} -> {cmd}")
    if cfg.ci_jobs:
        typer.echo("CI jobs:")
        for job in cfg.ci_jobs:
            typer.echo(f"  {job.name} ({len(job.steps or [])} steps)")
    if cfg.ci_artifacts:
        typer.echo("CI artifacts:")
        for artifact in cfg.ci_artifacts:
            typer.echo(f"  {artifact.name}: {artifact.path} ({artifact.when})")
    if cfg.ci_summary:
        typer.echo(
            f"CI summary: enabled={cfg.ci_summary.enabled} "
            f"metrics={len(cfg.ci_summary.metrics or [])}"
        )
    if cfg.checks_assertions:
        typer.echo("Checks:")
        for assertion in cfg.checks_assertions:
            typer.echo(
                "  "
                f"{assertion.command}: {assertion.path} {assertion.op} "
                f"{assertion.value!r}"
            )
    typer.echo(f"Pyproject status: {pyproject_status.value}")
    if pyproject_requires_python is not None:
        typer.echo(f"Pyproject requires-python: {pyproject_requires_python}")


@app.command()
def sync(
    intent_path: str = "intent.toml",
    show_ci: bool = False,
    show_just: bool = False,
    show_json: bool = False,
    explain: bool = False,
    write: bool = False,
    dry_run: bool = False,
    adopt: bool = False,
    force: bool = False,
) -> None:
    """
    Show config + versions. Optionally preview generated files, or write them.

    --dry-run: show what would be written/updated (no writes)
    --write:   write tool-owned generated files
    """
    if write and dry_run:
        typer.echo(
            f"[{ERR_USAGE_CONFLICT}] Error: --write and --dry-run cannot be used together", err=True
        )
        raise typer.Exit(code=2)
    if adopt and force:
        typer.echo(
            f"[{ERR_USAGE_CONFLICT}] Error: --adopt and --force cannot be used together", err=True
        )
        raise typer.Exit(code=2)
    if (adopt or force) and not write:
        typer.echo(f"[{ERR_USAGE_CONFLICT}] Error: --adopt/--force require --write", err=True)
        raise typer.Exit(code=2)
    if (show_json or explain) and write:
        typer.echo(f"[{ERR_USAGE_CONFLICT}] Error: --show-json/--explain cannot be used with --write", err=True)
        raise typer.Exit(code=2)

    path = Path(intent_path)

    try:
        cfg = load_intent(path)
    except FileNotFoundError as e:
        typer.echo(f"[{ERR_CONFIG_NOT_FOUND}] Error: {e}", err=True)
        typer.echo("Fix: run `intent init` to create a starter config.", err=True)
        raise typer.Exit(code=2)
    except IntentConfigError as e:
        typer.echo(f"[{ERR_CONFIG_INVALID}] Config error: {e}", err=True)
        raise typer.Exit(code=2)

    ci_path = Path(".github/workflows/ci.yml")
    just_path = Path("justfile")
    ci_content = render_ci(cfg)
    just_content = render_just(cfg)

    if show_json:
        payload = _resolved_payload(path, cfg)
        payload["sync"] = {
            "show_json": True,
            "explain": explain,
            "generated": {
                "ci": str(ci_path),
                "justfile": str(just_path),
            },
            "explain_map": _sync_explain_payload(cfg) if explain else None,
        }
        typer.echo(json.dumps(payload))
        raise typer.Exit(code=0)

    if explain:
        _print_sync_explain_text(cfg)
        raise typer.Exit(code=0)

    if not write and not dry_run:
        typer.echo(f"Intent python version: {cfg.python_version}")
        typer.echo("Intent commands: " + ", ".join(cfg.commands.keys()))

    ok_versions, msg_versions, _ = _check_versions(cfg.python_version, strict=False)
    typer.echo(msg_versions)

    if show_ci:
        typer.echo("\n--- ci.yml (preview) ---\n")
        typer.echo(ci_content)

    if show_just:
        typer.echo("\n--- justfile (preview) ---\n")
        typer.echo(just_content)

    if dry_run:
        typer.echo("\n--- dry-run ---")
        typer.echo(_preview_status(ci_path, ci_content))
        typer.echo(_preview_status(just_path, just_content))
        raise typer.Exit(code=0)

    if write:
        mode = "strict"
        if adopt:
            mode = "adopt"
        elif force:
            mode = "force"
        try:
            ci_changed = write_generated_file(ci_path, ci_content, mode=mode)
            just_changed = write_generated_file(just_path, just_content, mode=mode)
        except OwnershipError as e:
            typer.echo(f"[{ERR_OWNERSHIP}] {e}", err=True)
            raise typer.Exit(code=1)

        typer.echo(f"Wrote {ci_path}" if ci_changed else f"No changes to {ci_path}")
        typer.echo(f"Wrote {just_path}" if just_changed else f"No changes to {just_path}")

        hook_results = _run_plugin_hooks(cfg.plugin_generate_hooks, stage="generate")
        for result in hook_results:
            if result["ok"]:
                typer.echo(f"✓ plugin generate: {result['command']}")
                continue
            typer.echo(
                f"✗ [{ERR_PLUGIN}] plugin generate failed ({result['exit_code']}): "
                f"{result['command']}",
                err=True,
            )
            if result["stderr"]:
                typer.echo(f"  stderr: {result['stderr']}", err=True)
            raise typer.Exit(code=1)


@app.command()
def check(
    intent_path: str = "intent.toml",
    strict: bool | None = typer.Option(None, "--strict/--no-strict"),
    output_format: Literal["text", "json"] = typer.Option("text", "--format"),
) -> None:
    """
    Check drift without writing.

    Exit codes:
      0 = OK
      1 = drift / mismatch found
      2 = config/usage error
    """
    path = Path(intent_path)

    try:
        cfg = load_intent(path)
    except FileNotFoundError as e:
        if output_format == "json":
            typer.echo(
                json.dumps(
                    {
                        "ok": False,
                        "error": {"kind": "config", "message": f"{e}"},
                        "code": ERR_CONFIG_NOT_FOUND,
                    }
                )
            )
            raise typer.Exit(code=2)
        typer.echo(f"[{ERR_CONFIG_NOT_FOUND}] Error: {e}", err=True)
        raise typer.Exit(code=2)
    except IntentConfigError as e:
        if output_format == "json":
            typer.echo(
                json.dumps(
                    {
                        "ok": False,
                        "error": {"kind": "config", "message": f"{e}"},
                        "code": ERR_CONFIG_INVALID,
                    }
                )
            )
            raise typer.Exit(code=2)
        typer.echo(f"[{ERR_CONFIG_INVALID}] Config error: {e}", err=True)
        raise typer.Exit(code=2)

    drift = False
    effective_strict = cfg.policy_strict if strict is None else strict

    ok_versions, msg_versions, versions_code = _check_versions(
        cfg.python_version,
        strict=effective_strict,
    )
    ci_path = Path(".github/workflows/ci.yml")
    just_path = Path("justfile")

    ci_ok, ci_msg, ci_code = _generated_drift_status(ci_path, render_ci(cfg))
    just_ok, just_msg, just_code = _generated_drift_status(just_path, render_just(cfg))
    plugin_results = _run_plugin_hooks(cfg.plugin_check_hooks, stage="check")
    commands_for_json: set[str] = {item.command for item in (cfg.checks_assertions or [])}
    if cfg.ci_summary and cfg.ci_summary.metrics:
        commands_for_json.update(metric.command for metric in cfg.ci_summary.metrics)
    command_results = _run_json_commands(cfg.commands, commands_for_json)
    assertion_results = _run_check_assertions(cfg.checks_assertions, command_results)
    summary_metrics = _evaluate_summary_metrics(
        cfg.ci_summary.metrics if cfg.ci_summary else None,
        command_results,
    )
    summary_markdown = None
    if cfg.ci_summary and cfg.ci_summary.enabled:
        summary_markdown = _render_summary_markdown(
            title=cfg.ci_summary.title,
            include_assertions=cfg.ci_summary.include_assertions,
            assertions=assertion_results,
            metrics=summary_metrics,
        )

    if output_format == "json":
        if not ok_versions:
            drift = True
        if not ci_ok:
            drift = True
        if not just_ok:
            drift = True
        if any(result["ok"] is False for result in plugin_results):
            drift = True
        if any(result["ok"] is False for result in assertion_results):
            drift = True
        if any(metric["ok"] is False for metric in summary_metrics):
            drift = True

        payload = {
            "ok": not drift,
            "strict": effective_strict,
            "intent_path": str(path),
            "versions": {
                "ok": ok_versions,
                "message": msg_versions,
                "code": versions_code,
            },
            "files": [
                {
                    "path": str(ci_path),
                    "ok": ci_ok,
                    "message": ci_msg,
                    "code": ci_code,
                },
                {
                    "path": str(just_path),
                    "ok": just_ok,
                    "message": just_msg,
                    "code": just_code,
                },
            ],
            "plugins": plugin_results,
            "checks": assertion_results,
            "report": {
                "summary_enabled": bool(cfg.ci_summary and cfg.ci_summary.enabled),
                "summary_markdown": summary_markdown,
                "metrics": summary_metrics,
            },
        }
        typer.echo(json.dumps(payload))
        raise typer.Exit(code=1 if drift else 0)

    if not ok_versions:
        drift = True
        typer.echo(f"✗ [{versions_code}] {msg_versions}", err=True)
    else:
        if msg_versions.startswith("note:"):
            typer.echo(msg_versions)
        else:
            typer.echo(f"✓ {msg_versions}")

    if ci_ok:
        typer.echo(f"✓ {ci_msg}")
    else:
        drift = True
        typer.echo(f"✗ [{ci_code}] {ci_msg}", err=True)

    if just_ok:
        typer.echo(f"✓ {just_msg}")
    else:
        drift = True
        typer.echo(f"✗ [{just_code}] {just_msg}", err=True)

    for result in plugin_results:
        if result["ok"]:
            typer.echo(f"✓ plugin check: {result['command']}")
        else:
            drift = True
            typer.echo(
                f"✗ [{ERR_PLUGIN}] plugin check failed ({result['exit_code']}): "
                f"{result['command']}",
                err=True,
            )
            if result["stderr"]:
                typer.echo(f"  stderr: {result['stderr']}", err=True)

    for result in assertion_results:
        description = (
            f"check assertion ({result['command']}): "
            f"{result['path']} {result['op']} {result['expected']!r}"
        )
        if result["ok"]:
            typer.echo(f"✓ {description} (actual={result['actual']!r})")
            continue
        drift = True
        typer.echo(f"✗ [{ERR_CHECK}] {description}", err=True)
        if result.get("message"):
            typer.echo(f"  note: {result['message']}", err=True)
        if result.get("reason"):
            typer.echo(f"  reason: {result['reason']}", err=True)
        if result.get("actual") is not None:
            typer.echo(f"  actual: {result['actual']!r}", err=True)

    for metric in summary_metrics:
        metric_desc = f"summary metric ({metric['command']}): {metric['label']} @ {metric['path']}"
        if metric["ok"]:
            if metric["delta"] is not None:
                typer.echo(
                    f"✓ {metric_desc} value={metric['value']!r} "
                    f"baseline={metric['baseline']!r} delta={metric['delta']!r}"
                )
            else:
                typer.echo(f"✓ {metric_desc} value={metric['value']!r}")
            continue
        drift = True
        typer.echo(f"✗ [{ERR_CHECK}] {metric_desc}", err=True)
        if metric.get("reason"):
            typer.echo(f"  reason: {metric['reason']}", err=True)

    if drift:
        typer.echo("\nHint: run `intent sync --write` to update generated files.", err=True)
        raise typer.Exit(code=1)

    raise typer.Exit(code=0)


@app.command()
def doctor(
    intent_path: str = "intent.toml",
    strict: bool | None = typer.Option(None, "--strict/--no-strict"),
) -> None:
    """
    Diagnose common Intent issues and suggest concrete fixes.

    Exit codes:
      0 = no issues
      1 = issues found
      2 = config/usage error
    """
    path = Path(intent_path)
    try:
        cfg = load_intent(path)
    except FileNotFoundError as e:
        typer.echo(f"[{ERR_CONFIG_NOT_FOUND}] Error: {e}", err=True)
        typer.echo("Fix: run `intent init` to create a starter config.", err=True)
        raise typer.Exit(code=2)
    except IntentConfigError as e:
        typer.echo(f"[{ERR_CONFIG_INVALID}] Config error: {e}", err=True)
        typer.echo("Fix: open intent.toml and correct the invalid field/type.", err=True)
        raise typer.Exit(code=2)

    issues = False
    effective_strict = cfg.policy_strict if strict is None else strict

    typer.echo("--- doctor ---")
    typer.echo(f"Intent path: {path}")

    ok_versions, msg_versions, versions_code = _check_versions(
        cfg.python_version,
        strict=effective_strict,
    )
    if ok_versions:
        typer.echo(f"✓ versions: {msg_versions}")
    else:
        issues = True
        typer.echo(f"✗ [{versions_code}] versions: {msg_versions}", err=True)
        typer.echo("  Fix: align [python].version with pyproject requires-python.", err=True)

    file_checks = [
        (Path(".github/workflows/ci.yml"), render_ci(cfg)),
        (Path("justfile"), render_just(cfg)),
    ]
    for file_path, content in file_checks:
        ok, message, code = _generated_drift_status(file_path, content)
        if ok:
            typer.echo(f"✓ {message}")
            continue
        issues = True
        typer.echo(f"✗ [{code}] {message}", err=True)
        if code in (ERR_FILE_MISSING, ERR_FILE_OUTDATED):
            typer.echo("  Fix: run `intent sync --write`.", err=True)
        elif code == ERR_FILE_UNOWNED:
            typer.echo(
                "  Fix: keep it user-owned or replace it explicitly with generated output.",
                err=True,
            )

    if issues:
        raise typer.Exit(code=1)

    typer.echo("No issues found.")
    raise typer.Exit(code=0)


@app.command()
def reconcile(
    intent_path: str = "intent.toml",
    plan: bool = typer.Option(False, "--plan", help="Show planned Python-version reconciliation"),
    apply: bool = typer.Option(False, "--apply", help="Apply Python-version reconciliation"),
    allow_existing: bool = typer.Option(
        False,
        "--allow-existing",
        help="Allow editing existing pyproject/.python-version/.tool-versions files",
    ),
) -> None:
    """
    Plan Python-version reconciliation across supported project files.
    """
    if plan == apply:
        typer.echo(
            f"[{ERR_USAGE_CONFLICT}] Error: choose exactly one of --plan or --apply",
            err=True,
        )
        raise typer.Exit(code=2)

    path = Path(intent_path)
    try:
        cfg = load_intent(path)
    except FileNotFoundError as e:
        typer.echo(f"[{ERR_CONFIG_NOT_FOUND}] Error: {e}", err=True)
        raise typer.Exit(code=2)
    except IntentConfigError as e:
        typer.echo(f"[{ERR_CONFIG_INVALID}] Config error: {e}", err=True)
        raise typer.Exit(code=2)

    target = cfg.python_version
    next_minor = _next_minor(target)
    recommended_pyproject = f">={target},<{next_minor}" if next_minor else f">={target}"
    pyproject_path = Path("pyproject.toml")
    pyproject_status, pyproject_spec = read_pyproject_python(pyproject_path)
    python_version_current = _read_python_version_file()
    tool_versions_current = _read_tool_versions_python()

    mode = "apply" if apply else "plan"
    typer.echo(f"--- reconcile {mode} ---")
    typer.echo(f"Target python version (from intent): {target}")
    typer.echo("")

    unresolved = False

    if pyproject_status == PyprojectPythonStatus.FILE_MISSING:
        if apply:
            _, action = _upsert_pyproject_requires_python(pyproject_path, recommended_pyproject)
            typer.echo(
                f"- {pyproject_path}: {action} ([project].requires-python={recommended_pyproject})"
            )
        else:
            typer.echo(f"- {pyproject_path}: missing")
            typer.echo(
                f"  action: create/update [project].requires-python = {recommended_pyproject}"
            )
    elif pyproject_status == PyprojectPythonStatus.PROJECT_MISSING:
        if apply and allow_existing:
            _, action = _upsert_pyproject_requires_python(pyproject_path, recommended_pyproject)
            typer.echo(
                f"- {pyproject_path}: {action} ([project].requires-python={recommended_pyproject})"
            )
        elif apply:
            unresolved = True
            typer.echo(f"- {pyproject_path}: skipped ([project] missing, use --allow-existing)")
        else:
            typer.echo(f"- {pyproject_path}: [project] missing")
            typer.echo(f"  action: add [project].requires-python = {recommended_pyproject}")
    elif pyproject_status == PyprojectPythonStatus.REQUIRES_PYTHON_MISSING:
        if apply and allow_existing:
            _, action = _upsert_pyproject_requires_python(pyproject_path, recommended_pyproject)
            typer.echo(
                f"- {pyproject_path}: {action} ([project].requires-python={recommended_pyproject})"
            )
        elif apply:
            unresolved = True
            typer.echo(
                f"- {pyproject_path}: skipped (requires-python missing, use --allow-existing)"
            )
        else:
            typer.echo(f"- {pyproject_path}: requires-python missing")
            typer.echo(f"  action: add requires-python = {recommended_pyproject}")
    elif pyproject_status == PyprojectPythonStatus.INVALID:
        typer.echo(f"- {pyproject_path}: invalid/unreadable")
        if apply:
            unresolved = True
            typer.echo("  action: manual fix required before reconcile --apply")
        else:
            typer.echo("  action: manual fix required before auto-reconcile")
    else:
        assert pyproject_spec is not None
        in_range = check_requires_python_range(target, pyproject_spec)
        lower = max_lower_bound(pyproject_spec)
        exact_lower_match = lower is not None and _same_major_minor(str(lower), target)
        if in_range is True and exact_lower_match:
            typer.echo(f"- {pyproject_path}: aligned (requires-python={pyproject_spec})")
        else:
            if apply and allow_existing:
                _, action = _upsert_pyproject_requires_python(pyproject_path, recommended_pyproject)
                typer.echo(
                    f"- {pyproject_path}: {action} (requires-python={recommended_pyproject})"
                )
            elif apply:
                unresolved = True
                typer.echo(
                    f"- {pyproject_path}: skipped (drift={pyproject_spec}, use --allow-existing)"
                )
            else:
                typer.echo(f"- {pyproject_path}: drift (requires-python={pyproject_spec})")
                typer.echo(f"  action: set requires-python = {recommended_pyproject}")

    python_version_path = Path(".python-version")
    if python_version_current is None:
        if apply:
            _, action = _write_python_version(python_version_path, target)
            typer.echo(f"- {python_version_path}: {action} ({target})")
        else:
            typer.echo(f"- {python_version_path}: missing")
            typer.echo(f"  action: write {target}")
    elif _same_major_minor(python_version_current, target):
        typer.echo(f"- {python_version_path}: aligned ({python_version_current})")
    else:
        if apply and allow_existing:
            _, action = _write_python_version(python_version_path, target)
            typer.echo(f"- {python_version_path}: {action} ({target})")
        elif apply:
            unresolved = True
            typer.echo(
                f"- {python_version_path}: skipped "
                f"(drift={python_version_current}, use --allow-existing)"
            )
        else:
            typer.echo(f"- {python_version_path}: drift ({python_version_current})")
            typer.echo(f"  action: replace with {target}")

    tool_versions_path = Path(".tool-versions")
    if tool_versions_current is None:
        if not tool_versions_path.exists() and apply:
            _, action = _upsert_tool_versions_python(tool_versions_path, target)
            typer.echo(f"- {tool_versions_path}: {action} (python {target})")
        elif apply and allow_existing:
            _, action = _upsert_tool_versions_python(tool_versions_path, target)
            typer.echo(f"- {tool_versions_path}: {action} (python {target})")
        elif apply:
            unresolved = True
            typer.echo(f"- {tool_versions_path}: skipped (no python entry, use --allow-existing)")
        else:
            typer.echo(f"- {tool_versions_path}: missing or no python entry")
            typer.echo(f"  action: add `python {target}`")
    elif _same_major_minor(tool_versions_current, target):
        typer.echo(f"- {tool_versions_path}: aligned (python {tool_versions_current})")
    else:
        if apply and allow_existing:
            _, action = _upsert_tool_versions_python(tool_versions_path, target)
            typer.echo(f"- {tool_versions_path}: {action} (python {target})")
        elif apply:
            unresolved = True
            typer.echo(
                f"- {tool_versions_path}: skipped "
                f"(drift={tool_versions_current}, use --allow-existing)"
            )
        else:
            typer.echo(f"- {tool_versions_path}: drift (python {tool_versions_current})")
            typer.echo(f"  action: set `python {target}`")

    typer.echo("")
    if apply:
        if unresolved:
            typer.echo(
                "Reconcile apply completed with skips. Re-run with `--allow-existing` where needed."
            )
            raise typer.Exit(code=1)
        typer.echo("Reconcile apply completed.")
        raise typer.Exit(code=0)
    typer.echo("No files were modified. Use `intent reconcile --apply` to apply changes.")
    raise typer.Exit(code=0)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
