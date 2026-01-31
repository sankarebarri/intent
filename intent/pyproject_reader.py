from __future__ import annotations

import tomllib
from enum import Enum
from pathlib import Path


class PyprojectPythonStatus(Enum):
    OK = "ok"
    FILE_MISSING = "file_missing"
    PROJECT_MISSING = "project_missing"
    REQUIRES_PYTHON_MISSING = "requires_python_missing"
    INVALID = "invalid"


def read_pyproject_python(
    path: Path = Path("pyproject.toml"),
) -> tuple[PyprojectPythonStatus, str | None]:
    """
    Read the [project].requires-python string from pyproject.toml.

    Returns:
        (status, value)
    """
    if not path.exists():
        return PyprojectPythonStatus.FILE_MISSING, None

    data = tomllib.loads(path.read_text(encoding="utf-8"))
    project = data.get("project")
    if not isinstance(project, dict):
        return PyprojectPythonStatus.PROJECT_MISSING, None

    requires_python = project.get("requires-python")
    if requires_python is None:
        return PyprojectPythonStatus.REQUIRES_PYTHON_MISSING, None

    if not isinstance(requires_python, str):
        return PyprojectPythonStatus.INVALID, None

    return PyprojectPythonStatus.OK, requires_python
