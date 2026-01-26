from pathlib import (
    Path,
)
import pytest
from intent.fs import (
    GENERATED_MARKER,
    OwnershipError,
    write_generated_file,
)


def test_write_generated_file_creates_file(
    tmp_path: Path,
) -> None:
    path = tmp_path / "demo.txt"
    content = f"{GENERATED_MARKER}\n# DO NOT EDIT\n\nhello\n"

    changed = write_generated_file(
        path,
        content,
    )

    assert changed is True
    assert path.exists()
    assert path.read_text(encoding="utf-8") == content


def test_write_generated_file_is_idempotent(
    tmp_path: Path,
) -> None:
    p = tmp_path / "demo.txt"
    content = f"{GENERATED_MARKER}\n# DO NOT EDIT\n\nhello\n"

    assert (
        write_generated_file(
            p,
            content,
        )
        is True
    )
    assert (
        write_generated_file(
            p,
            content,
        )
        is False
    )  # no changes


def test_write_generated_file_refuses_user_owned_file(
    tmp_path: Path,
) -> None:
    path = tmp_path / "demo.txt"
    path.write_text(
        "user content\n",
        encoding="utf-8",
    )

    content = f"{GENERATED_MARKER}\n# DO NOT EDIT\n\nhello\n"

    with pytest.raises(OwnershipError) as excinfo:
        write_generated_file(
            path,
            content,
        )

    msg = str(excinfo.value)
    assert "Refusing to overwrite" in msg
    assert str(path) in msg


def test_write_generated_file_refuses_missing_marker_in_new_content(
    tmp_path: Path,
) -> None:
    p = tmp_path / "demo.txt"
    bad_content = "# DO NOT EDIT\n\nhello\n"

    with pytest.raises(ValueError) as excinfo:
        write_generated_file(
            p,
            bad_content,
        )

    assert "missing marker" in str(excinfo.value).lower()
