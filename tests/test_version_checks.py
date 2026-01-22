from intent.cli import _check_requires_python_range, _parse_version


def test_parse_version_ok() -> None:
    assert _parse_version("3.12") == (3, 12)
    assert _parse_version("3.12.1") == (3, 12, 1)

def test_parse_version_bad() -> None:
    assert _parse_version("") is None
    assert _parse_version("3.x") is None
    assert _parse_version("hello") is None


def test_check_requires_python_range_supported_true() -> None:
    assert _check_requires_python_range("3.12", ">=3.10,<3.13") is True
    assert _check_requires_python_range("3.12", ">=3.12") is True
    assert _check_requires_python_range("3.12", "<3.13") is True


def test_check_requires_python_range_supported_false() -> None:
    assert _check_requires_python_range("3.9", ">=3.10,<3.13") is False
    assert _check_requires_python_range("3.13", "<3.13") is False


def test_check_requires_python_range_unsupported() -> None:
    # We intentionally don't support these patterns yet
    assert _check_requires_python_range("3.12", "~=3.11") is None
    assert _check_requires_python_range("3.12", "==3.12") is None
    assert _check_requires_python_range("3.12", "<=3.12") is None
