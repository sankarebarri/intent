from pathlib import Path
from intent.pyproject_reader import read_pyproject_python

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

    assert read_pyproject_python(path) == ">=3.10,<3.13"


def test_read_pyproject_python_missing_file(tmp_path: Path) -> None:
    path = tmp_path / "pyproject.toml"
    assert read_pyproject_python(path) is None


def test_read_pyproject_python_missing_project(tmp_path: Path) -> None:
    path = write_project(
        tmp_path,
        """
        [tool.black]
        line-length = 88
        """,
    )

    assert read_pyproject_python(path) is None


def test_read_pyproject_python_requires_python_not_string(tmp_path: Path) -> None:
    path = write_project(
        tmp_path,
        """
        [project]
        requires-python = 3.12
        """,
    )

    result = read_pyproject_python(path)
    assert result is None
