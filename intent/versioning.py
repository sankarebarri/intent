# intent/versioning.py
from __future__ import annotations


def parse_version(version: str) -> tuple[int, ...] | None:
    """
    Parse a version string like:
      "3" -> (3,)
      "3.12" -> (3, 12)
      "3.12.1" -> (3, 12, 1)

    Rejects:
      "3.5l", "py312", "", ">=3.12"
    """
    version = version.strip()
    if not version:
        return None

    parts: list[int] = []
    for part in version.split("."):
        part = part.strip()
        if not part:
            break
        if not part.isdigit():
            return None
        parts.append(int(part))

    return tuple(parts) if parts else None


def validate_python_version(raw: str) -> None:
    """
    Raises ValueError if invalid.
    """
    if parse_version(raw) is None:
        raise ValueError(f"Invalid python version {raw!r} (expected like '3.12')")


def max_lower_bound(constraints: list[str]) -> tuple[int, ...] | None:
    """
    Return the *largest* >= bound found in constraints, e.g.
    [">=3.10", ">=3.12", "<3.13"] -> (3, 12)
    """
    best: tuple[int, ...] | None = None
    for c in constraints:
        c = c.strip()
        if c.startswith(">="):
            bound = parse_version(c[2:].strip())
            if bound is None:
                continue
            if best is None or bound > best:
                best = bound
    return best


def check_requires_python_range(intent_version: str, spec: str) -> bool | None:
    """
    Best-effort checker for patterns like:
      '>=3.10,<3.13'
      '>=3.11'
      '<3.13'

    Returns:
      True  -> intent_version appears to satisfy the spec
      False -> intent_version does NOT satisfy the spec
      None  -> unsupported/unknown spec pattern
    """
    intent_parsed = parse_version(intent_version)
    if intent_parsed is None:
        return None

    constraints = [c.strip() for c in spec.split(",") if c.strip()]
    if not constraints:
        return None

    supported = True
    ok = True

    for c in constraints:
        if c.startswith(">="):
            bound_parsed = parse_version(c[2:].strip())
            if bound_parsed is None:
                supported = False
                continue
            if intent_parsed < bound_parsed:
                ok = False
        elif c.startswith("<"):
            bound_parsed = parse_version(c[1:].strip())
            if bound_parsed is None:
                supported = False
                continue
            if not (intent_parsed < bound_parsed):
                ok = False
        else:
            supported = False

    return ok if supported else None
