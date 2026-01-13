"""Strict JSON parsing with enhanced error reporting."""

import json
from pathlib import Path
from typing import Any


class JSONReadError(Exception):
    """Raised when JSON cannot be parsed, with location information."""

    def __init__(
        self,
        message: str,
        path: Path | str,
        line: int | None = None,
        column: int | None = None,
        position: int | None = None,
        original_error: Exception | None = None,
    ):
        super().__init__(message)
        self.path = Path(path) if path else None
        self.line = line
        self.column = column
        self.position = position
        self.original_error = original_error

    def __str__(self) -> str:
        parts = [f"JSON parse error in {self.path}"]
        if self.line is not None:
            parts.append(f"line {self.line}")
        if self.column is not None:
            parts.append(f"column {self.column}")
        if self.position is not None:
            parts.append(f"position {self.position}")
        parts.append(f": {super().__str__()}")
        return " ".join(parts)


def _detect_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Detect duplicate keys in JSON object pairs."""
    seen = {}
    duplicates = []
    for key, value in pairs:
        if key in seen:
            duplicates.append(key)
        seen[key] = value
    if duplicates:
        raise ValueError(f"Duplicate keys found: {', '.join(duplicates)}")
    return seen


def read_json_strict(path: Path | str) -> tuple[dict[str, Any] | list[Any], dict[str, Any]]:
    """
    Read and parse JSON file with strict validation.

    Detects duplicate keys and provides detailed error information.

    Args:
        path: Path to JSON file

    Returns:
        Tuple of (parsed_data, metadata) where metadata contains:
        - "has_duplicate_keys": bool
        - "error": JSONReadError if parsing failed

    Raises:
        JSONReadError: If JSON cannot be parsed or contains duplicate keys
    """
    path = Path(path)
    metadata: dict[str, Any] = {
        "has_duplicate_keys": False,
        "error": None,
    }

    if not path.exists():
        raise JSONReadError(f"File does not exist: {path}", path)

    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as e:
        raise JSONReadError(
            f"File encoding error: {e}",
            path,
            original_error=e,
        )

    # Try parsing with duplicate key detection
    try:
        data = json.loads(content, object_pairs_hook=_detect_duplicate_keys)
        return data, metadata
    except ValueError as e:
        # Check if it's our duplicate key error
        if "Duplicate keys found" in str(e):
            metadata["has_duplicate_keys"] = True
            raise JSONReadError(
                str(e),
                path,
                original_error=e,
            )
        # Otherwise, try to get location from JSONDecodeError
        try:
            json.loads(content)  # This will raise JSONDecodeError with location
        except json.JSONDecodeError as json_err:
            raise JSONReadError(
                f"Invalid JSON: {json_err.msg}",
                path,
                line=json_err.lineno,
                column=json_err.colno,
                position=json_err.pos,
                original_error=json_err,
            )
        # Fallback
        raise JSONReadError(
            f"Invalid JSON: {e}",
            path,
            original_error=e,
        )
    except json.JSONDecodeError as e:
        raise JSONReadError(
            f"Invalid JSON: {e.msg}",
            path,
            line=e.lineno,
            column=e.colno,
            position=e.pos,
            original_error=e,
        )
