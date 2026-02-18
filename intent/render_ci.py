# intent/render_ci.py
from __future__ import annotations

from .config import CiArtifact, CiJob, CiStep, IntentConfig
from .fs import GENERATED_MARKER


def _yaml_scalar(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return f'"{value}"'


def _append_step(lines: list[str], step: CiStep, commands: dict[str, str], indent: str = "      ") -> None:
    lines.append(f"{indent}-")
    if step.name:
        lines.append(f"{indent}  name: {step.name}")
    if step.if_condition:
        lines.append(f"{indent}  if: {step.if_condition}")
    if step.continue_on_error:
        lines.append(f"{indent}  continue-on-error: true")
    if step.working_directory:
        lines.append(f"{indent}  working-directory: {step.working_directory}")
    if step.env:
        lines.append(f"{indent}  env:")
        for key in sorted(step.env):
            lines.append(f"{indent}    {key}: {_yaml_scalar(step.env[key])}")
    if step.uses:
        lines.append(f"{indent}  uses: {step.uses}")
        if step.with_args:
            lines.append(f"{indent}  with:")
            for key in sorted(step.with_args):
                lines.append(f"{indent}    {key}: {_yaml_scalar(step.with_args[key])}")
        return

    command_text = step.run if step.run is not None else commands[step.command or ""]
    lines.append(f"{indent}  run: |")
    for cmd_line in command_text.splitlines():
        lines.append(f"{indent}    {cmd_line}")


def _append_custom_job(lines: list[str], job: CiJob, commands: dict[str, str]) -> None:
    lines.append(f"  {job.name}:")
    lines.append(f"    runs-on: {job.runs_on}")
    if job.if_condition:
        lines.append(f"    if: {job.if_condition}")
    if job.continue_on_error:
        lines.append("    continue-on-error: true")
    if job.timeout_minutes is not None:
        lines.append(f"    timeout-minutes: {job.timeout_minutes}")
    if job.needs:
        sorted_needs = sorted(job.needs)
        needs_text = ", ".join(sorted_needs)
        lines.append(f"    needs: [{needs_text}]")
    if job.matrix:
        lines.append("    strategy:")
        lines.append("      fail-fast: false")
        lines.append("      matrix:")
        for key in sorted(job.matrix):
            values = ", ".join(_yaml_scalar(v) for v in job.matrix[key])
            lines.append(f"        {key}: [{values}]")
    lines.append("    steps:")
    for step in job.steps or []:
        _append_step(lines, step, commands)
    lines.append("")


def _append_artifact_steps(lines: list[str], artifacts: list[CiArtifact] | None, indent: str = "      ") -> None:
    if not artifacts:
        return
    when_to_if = {
        "always": "${{ always() }}",
        "on-failure": "${{ failure() }}",
        "on-success": "${{ success() }}",
    }
    for artifact in artifacts:
        lines.append(f"{indent}-")
        lines.append(f"{indent}  name: Upload artifact: {artifact.name}")
        lines.append(f"{indent}  if: {when_to_if[artifact.when]}")
        lines.append(f"{indent}  uses: actions/upload-artifact@v4")
        lines.append(f"{indent}  with:")
        lines.append(f"{indent}    name: {_yaml_scalar(artifact.name)}")
        lines.append(f"{indent}    path: {_yaml_scalar(artifact.path)}")
        if artifact.retention_days is not None:
            lines.append(f"{indent}    retention-days: {artifact.retention_days}")


def _summary_step() -> CiStep:
    run = "\n".join(
        [
            "intent check --format json > intent-check.json || true",
            "python - <<'PY'",
            "import json",
            "from pathlib import Path",
            "payload = json.loads(Path('intent-check.json').read_text(encoding='utf-8'))",
            "report = payload.get('report') or {}",
            "summary = report.get('summary_markdown')",
            "if summary:",
            "    github_summary = Path('${GITHUB_STEP_SUMMARY}')",
            "    github_summary.write_text(summary + '\\n', encoding='utf-8')",
            "PY",
        ]
    )
    return CiStep(name="Write intent summary", if_condition="${{ always() }}", run=run)


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
    if cfg.ci_jobs:
        for job in cfg.ci_jobs:
            copied_job = CiJob(
                name=job.name,
                runs_on=job.runs_on,
                needs=job.needs,
                if_condition=job.if_condition,
                timeout_minutes=job.timeout_minutes,
                continue_on_error=job.continue_on_error,
                matrix=job.matrix,
                steps=[*(job.steps or [])],
            )
            copied_job.steps.extend(
                [
                    CiStep(
                        name=f"Upload artifact: {artifact.name}",
                        uses="actions/upload-artifact@v4",
                        with_args={
                            "name": artifact.name,
                            "path": artifact.path,
                            **(
                                {"retention-days": str(artifact.retention_days)}
                                if artifact.retention_days is not None
                                else {}
                            ),
                        },
                        if_condition={
                            "always": "${{ always() }}",
                            "on-failure": "${{ failure() }}",
                            "on-success": "${{ success() }}",
                        }[artifact.when],
                    )
                    for artifact in (cfg.ci_artifacts or [])
                ]
            )
            _append_custom_job(lines, copied_job, cfg.commands)
        if cfg.ci_summary and cfg.ci_summary.enabled:
            summary_job = CiJob(
                name="intent_summary",
                needs=sorted([job.name for job in cfg.ci_jobs]),
                steps=[
                    CiStep(uses="actions/checkout@v4"),
                    CiStep(uses="actions/setup-python@v5", with_args={"python-version": cfg.python_version}),
                    CiStep(run="python -m pip install -U pip\npython -m pip install -e .[dev]"),
                    _summary_step(),
                ],
            )
            _append_custom_job(lines, summary_job, cfg.commands)
        return "\n".join(lines).rstrip() + "\n"

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

    _append_artifact_steps(lines, cfg.ci_artifacts)
    if cfg.ci_summary and cfg.ci_summary.enabled:
        _append_step(lines, _summary_step(), cfg.commands)

    return "\n".join(lines).rstrip() + "\n"
