# intent/versioning.py
from __future__ import annotations

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version


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
            return None
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


def parse_pep440_version(raw: str) -> Version | None:
    raw = raw.strip()
    if not raw:
        return None
    try:
        return Version(raw)
    except InvalidVersion:
        return None


def max_lower_bound(spec: str) -> Version | None:
    """
    Return the largest lower bound found in a spec string.
    Examples:
      ">=3.10,>=3.12,<3.13" -> Version("3.12")
      ">3.11,<3.13" -> Version("3.11")
    """
    try:
        spec_set = SpecifierSet(spec)
    except InvalidSpecifier:
        return None

    best: Version | None = None
    for entry in spec_set:
        if entry.operator not in (">=", ">"):
            continue
        try:
            bound = Version(entry.version)
        except InvalidVersion:
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
    intent_parsed = parse_pep440_version(intent_version)
    if intent_parsed is None:
        return None

    if not spec.strip():
        return None

    try:
        spec_set = SpecifierSet(spec)
    except InvalidSpecifier:
        return None
    return intent_parsed in spec_set
