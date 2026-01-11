"""
Data Models for Task Context
=============================

Core data structures for representing file matches and task context.
"""

from dataclasses import dataclass, field


@dataclass
class FileMatch:
    """A file that matched the search criteria."""

    path: str
    service: str
    reason: str
    relevance_score: float = 0.0
    matching_lines: list[tuple[int, str]] = field(default_factory=list)


@dataclass
class TaskContext:
    """Complete context for a task."""

    task_description: str
    scoped_services: list[str]
    files_to_modify: list[dict]
    files_to_reference: list[dict]
    patterns_discovered: dict[str, str]
    service_contexts: dict[str, dict]
    graph_hints: list[dict] = field(
        default_factory=list
    )  # Historical hints from Graphiti
    # Enhanced analysis data (optional)
    codebase_graph_summary: dict | None = None  # Summary of codebase graph (key files, dependency counts)
    architecture_patterns: list[dict] | None = None  # Detected architecture patterns
    service_boundaries: list[dict] | None = None  # Identified service boundaries
    file_dependencies: dict[str, list[str]] | None = None  # Dependencies for files mentioned in spec
