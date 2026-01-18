from __future__ import annotations

from pathlib import Path
import tomllib

def read_pyproject_python(path: Path = Path("pyproject.toml")) -> str | None:
    """
    Return the [project].requires-python string from pyproject.toml if present, otherwise None.
    """
    if not path.exists():
        return None
    
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    project = data.get("project")
    if not isinstance(project, dict):
        return None
    
    requires_python = project.get("requires-python")
    if isinstance(requires_python, str):
        return requires_python
    
    return None