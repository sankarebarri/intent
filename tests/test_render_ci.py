# test_render_ci.py
from pathlib import (
    Path,
)

from intent.config import (
    CiArtifact,
    CiJob,
    CiSummary,
    CiStep,
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


def test_render_ci_commands_use_block_scalars() -> None:
    cfg = IntentConfig(
        python_version="3.12",
        commands={"test": "pytest -q\npytest --maxfail=1"},
        ci_install="-e .[dev]",
    )
    out = render_ci(cfg)

    assert "- name: test" in out
    assert "run: |\n          pytest -q\n          pytest --maxfail=1" in out


def test_render_ci_with_python_matrix() -> None:
    cfg = IntentConfig(
        python_version="3.12",
        commands={"test": "pytest -q"},
        ci_install="-e .[dev]",
        ci_python_versions=["3.11", "3.12"],
    )
    out = render_ci(cfg)

    assert "strategy:" in out
    assert "matrix:" in out
    assert 'python-version: ["3.11", "3.12"]' in out
    assert "python-version: ${{ matrix.python-version }}" in out


def test_render_ci_with_custom_triggers() -> None:
    cfg = IntentConfig(
        python_version="3.12",
        commands={"test": "pytest -q"},
        ci_triggers=["push", "pull_request"],
    )
    out = render_ci(cfg)
    assert "on: [push, pull_request]" in out


def test_render_ci_with_pip_cache() -> None:
    cfg = IntentConfig(
        python_version="3.12",
        commands={"test": "pytest -q"},
        ci_cache="pip",
    )
    out = render_ci(cfg)
    assert "cache: pip" in out


def test_render_ci_with_custom_jobs_and_step_metadata() -> None:
    cfg = IntentConfig(
        python_version="3.12",
        commands={"test": "pytest -q", "lint": "ruff check ."},
        ci_jobs=[
            CiJob(
                name="lint",
                steps=[
                    CiStep(uses="actions/checkout@v4"),
                    CiStep(command="lint", if_condition="${{ github.event_name == 'push' }}"),
                ],
            ),
            CiJob(
                name="test",
                needs=["lint"],
                timeout_minutes=15,
                continue_on_error=True,
                matrix={"python-version": ["3.11", "3.12"]},
                steps=[
                    CiStep(
                        uses="actions/setup-python@v5",
                        with_args={"python-version": "${{ matrix.python-version }}"},
                    ),
                    CiStep(
                        command="test",
                        working_directory=".",
                        env={"PYTHONUNBUFFERED": "1"},
                        continue_on_error=True,
                    ),
                ],
            ),
        ],
    )
    out = render_ci(cfg)

    assert "  lint:" in out
    assert "  test:" in out
    assert "    needs: [lint]" in out
    assert "    timeout-minutes: 15" in out
    assert "    continue-on-error: true" in out
    assert '        python-version: ["3.11", "3.12"]' in out
    assert "        with:" in out
    assert '          python-version: "${{ matrix.python-version }}"' in out
    assert "        working-directory: ." in out
    assert "        continue-on-error: true" in out
    assert '          PYTHONUNBUFFERED: "1"' in out


def test_render_ci_with_artifacts_baseline_job() -> None:
    cfg = IntentConfig(
        python_version="3.12",
        commands={"test": "pytest -q"},
        ci_artifacts=[
            CiArtifact(name="junit", path="reports/junit.xml", retention_days=7, when="on-failure"),
            CiArtifact(name="coverage", path="coverage.xml", when="always"),
        ],
    )
    out = render_ci(cfg)
    assert "Upload artifact: junit" in out
    assert "uses: actions/upload-artifact@v4" in out
    assert 'name: "junit"' in out
    assert 'path: "reports/junit.xml"' in out
    assert "retention-days: 7" in out
    assert "if: ${{ failure() }}" in out
    assert "if: ${{ always() }}" in out


def test_render_ci_with_artifacts_custom_jobs() -> None:
    cfg = IntentConfig(
        python_version="3.12",
        commands={"test": "pytest -q"},
        ci_jobs=[CiJob(name="test", steps=[CiStep(command="test")])],
        ci_artifacts=[CiArtifact(name="logs", path="logs/**", when="on-success")],
    )
    out = render_ci(cfg)
    assert "  test:" in out
    assert "Upload artifact: logs" in out
    assert "if: ${{ success() }}" in out


def test_render_ci_with_summary_step_baseline() -> None:
    cfg = IntentConfig(
        python_version="3.12",
        commands={"test": "pytest -q"},
    )
    cfg.ci_summary = CiSummary(enabled=True)
    out = render_ci(cfg)
    assert "name: Write intent summary" in out
    assert "intent check --format json > intent-check.json || true" in out
    assert "summary_path = os.environ.get('GITHUB_STEP_SUMMARY')" in out
    assert "Path(summary_path).write_text(summary + '\\n', encoding='utf-8')" in out


def test_render_ci_with_summary_job_for_custom_jobs() -> None:
    cfg = IntentConfig(
        python_version="3.12",
        commands={"test": "pytest -q"},
        ci_jobs=[CiJob(name="test", steps=[CiStep(command="test")])],
    )
    cfg.ci_summary = CiSummary(enabled=True)
    out = render_ci(cfg)
    assert "  intent_summary:" in out
    assert "needs: [test]" in out
    assert "name: Write intent summary" in out
