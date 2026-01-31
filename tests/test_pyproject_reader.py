# test_pyproject_reader.py
from pathlib import Path

from intent.pyproject_reader import PyprojectPythonStatus, read_pyproject_python


def write_project(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "pyproject.toml"
    path.write_text(content, encoding="utf-8")
    return path


def test_read_pyproject_python_valid(tmp_path: Path) -> None:
    path = write_project(
        tmp_path,
        """
        [project]
        name = "demo"
        requires-python = ">=3.10,<3.13"
        """,
    )

    status, value = read_pyproject_python(path)
    assert status is PyprojectPythonStatus.OK
    assert value == ">=3.10,<3.13"


def test_read_pyproject_python_missing_file(tmp_path: Path) -> None:
    path = tmp_path / "pyproject.toml"
    status, value = read_pyproject_python(path)
    assert status is PyprojectPythonStatus.FILE_MISSING
    assert value is None


def test_read_pyproject_python_missing_project(tmp_path: Path) -> None:
    path = write_project(
        tmp_path,
        """
        [tool.black]
        line-length = 88
        """,
    )

    status, value = read_pyproject_python(path)
    assert status is PyprojectPythonStatus.PROJECT_MISSING
    assert value is None


def test_read_pyproject_python_requires_python_not_string(tmp_path: Path) -> None:
    path = write_project(
        tmp_path,
        """
        [project]
        requires-python = 3.12
        """,
    )

    status, value = read_pyproject_python(path)
    assert status is PyprojectPythonStatus.INVALID
    assert value is None
