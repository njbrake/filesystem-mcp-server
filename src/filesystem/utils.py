"""Utility functions for path validation."""

from pathlib import Path

ALLOWED_ROOT: Path | None = None


def validate_path(relative_path: str) -> Path:
    """Validate and resolve a path against the allowed root directory.

    Args:
        relative_path: Path relative to the allowed root

    Returns:
        Resolved absolute path

    Raises:
        ValueError: If path is outside allowed root or ALLOWED_ROOT not set
    """
    if ALLOWED_ROOT is None:
        raise ValueError("Server not properly initialized: ALLOWED_ROOT not set")

    full_path = ALLOWED_ROOT / relative_path
    resolved = full_path.resolve()
    allowed = ALLOWED_ROOT.resolve()

    if not str(resolved).startswith(str(allowed)):
        raise ValueError(f"Path '{relative_path}' is outside allowed root directory")

    return resolved
