"""Data models for status report issues and fix plans."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Issue:
    """Represents a detected issue in a spec or roadmap."""

    severity: str  # "error", "warning", "info"
    code: str  # Issue type code (e.g., "invalid_json", "missing_file")
    message: str  # Human-readable message
    paths: list[str] = field(default_factory=list)  # Affected file paths
    suggested_fix: str | None = None  # Optional fix suggestion
    details: dict[str, Any] = field(default_factory=dict)  # Additional context

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "paths": self.paths,
            "suggestedFix": self.suggested_fix,
            "details": self.details,
        }


@dataclass
class PatchChange:
    """Represents a single file change in a fix plan."""

    path: str  # Relative path from project root
    action: str  # "create", "update", "delete"
    content: str | None = None  # File content (for create/update)
    encoding: str = "utf-8"  # File encoding

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "path": self.path,
            "action": self.action,
        }
        if self.content is not None:
            result["content"] = self.content
        if self.encoding != "utf-8":
            result["encoding"] = self.encoding
        return result


@dataclass
class FixPlan:
    """Represents a plan to fix one or more issues."""

    issue_codes: list[str]  # Codes of issues this plan addresses
    changes: list[PatchChange]  # Files to create/update/delete
    description: str  # Human-readable description of the fix
    dry_run: bool = True  # Whether this is a preview (dry-run)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "issueCodes": self.issue_codes,
            "changes": [c.to_dict() for c in self.changes],
            "description": self.description,
            "dryRun": self.dry_run,
        }
