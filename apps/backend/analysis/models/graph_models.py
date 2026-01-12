"""
Data Models for Codebase Graph Analysis
========================================

Core data structures for representing codebase graphs including
file nodes, dependency edges, and complete codebase graphs.
"""

from dataclasses import asdict, dataclass, field
from enum import Enum


class DependencyType(Enum):
    """Types of dependencies between files."""

    IMPORT = "import"
    FUNCTION_CALL = "function_call"
    CLASS_INHERITANCE = "class_inheritance"
    TYPE_REFERENCE = "type_reference"
    INTERFACE_IMPLEMENTATION = "interface_implementation"
    ANNOTATION = "annotation"
    DYNAMIC_IMPORT = "dynamic_import"
    REQUIRE_CALL = "require_call"
    IMPORT_CALL = "import_call"


class ArchitecturePattern(Enum):
    """Detected architecture patterns in the codebase."""

    MVC = "mvc"
    MICROSERVICES = "microservices"
    MONOREPO = "monorepo"
    LAYERED = "layered"
    HEXAGONAL = "hexagonal"
    EVENT_DRIVEN = "event_driven"
    PLUGIN = "plugin"
    UNKNOWN = "unknown"


@dataclass
class FileNode:
    """Represents a single file in the codebase graph."""

    # File metadata
    file_path: str = ""
    file_type: str = ""
    language: str = ""
    relative_path: str = ""

    # Dependencies
    imports: list[str] = field(default_factory=list)
    exports: list[str] = field(default_factory=list)

    # File characteristics
    is_entry_point: bool = False
    is_test_file: bool = False
    is_config_file: bool = False

    # Code metrics
    line_count: int = 0
    function_count: int = 0
    class_count: int = 0
    complexity_score: float = 0.0

    # Additional metadata
    last_modified: str = ""
    hash: str = ""

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            "file_path": self.file_path,
            "file_type": self.file_type,
            "language": self.language,
            "relative_path": self.relative_path,
            "imports": self.imports,
            "exports": self.exports,
            "is_entry_point": self.is_entry_point,
            "is_test_file": self.is_test_file,
            "is_config_file": self.is_config_file,
            "line_count": self.line_count,
            "function_count": self.function_count,
            "class_count": self.class_count,
            "complexity_score": self.complexity_score,
            "last_modified": self.last_modified,
            "hash": self.hash,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "FileNode":
        """Load from dict."""
        return cls(
            file_path=data.get("file_path", ""),
            file_type=data.get("file_type", ""),
            language=data.get("language", ""),
            relative_path=data.get("relative_path", ""),
            imports=data.get("imports", []),
            exports=data.get("exports", []),
            is_entry_point=data.get("is_entry_point", False),
            is_test_file=data.get("is_test_file", False),
            is_config_file=data.get("is_config_file", False),
            line_count=data.get("line_count", 0),
            function_count=data.get("function_count", 0),
            class_count=data.get("class_count", 0),
            complexity_score=data.get("complexity_score", 0.0),
            last_modified=data.get("last_modified", ""),
            hash=data.get("hash", ""),
        )


@dataclass
class DependencyEdge:
    """Represents a dependency relationship between two files."""

    # Source and target
    from_file: str = ""
    to_file: str = ""

    # Relationship details
    dependency_type: str = ""
    imported_symbols: list[str] = field(default_factory=list)
    line_numbers: list[int] = field(default_factory=list)

    # Dependency strength and characteristics
    strength: float = 0.0
    is_circular: bool = False
    is_runtime: bool = True
    is_development: bool = False

    # Additional metadata
    call_count: int = 0
    first_seen_at: str = ""
    last_updated: str = ""

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            "from_file": self.from_file,
            "to_file": self.to_file,
            "dependency_type": self.dependency_type,
            "imported_symbols": self.imported_symbols,
            "line_numbers": self.line_numbers,
            "strength": self.strength,
            "is_circular": self.is_circular,
            "is_runtime": self.is_runtime,
            "is_development": self.is_development,
            "call_count": self.call_count,
            "first_seen_at": self.first_seen_at,
            "last_updated": self.last_updated,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DependencyEdge":
        """Load from dict."""
        return cls(
            from_file=data.get("from_file", ""),
            to_file=data.get("to_file", ""),
            dependency_type=data.get("dependency_type", ""),
            imported_symbols=data.get("imported_symbols", []),
            line_numbers=data.get("line_numbers", []),
            strength=data.get("strength", 0.0),
            is_circular=data.get("is_circular", False),
            is_runtime=data.get("is_runtime", True),
            is_development=data.get("is_development", False),
            call_count=data.get("call_count", 0),
            first_seen_at=data.get("first_seen_at", ""),
            last_updated=data.get("last_updated", ""),
        )


@dataclass
class GraphMetrics:
    """Metrics calculated from the codebase graph."""

    # Basic counts
    total_files: int = 0
    total_dependencies: int = 0
    total_functions: int = 0
    total_classes: int = 0

    # Complexity metrics
    average_complexity: float = 0.0
    max_complexity: float = 0.0
    circular_dependencies: int = 0
    orphan_files: int = 0

    # Coupling metrics
    average_coupling: float = 0.0
    highly_coupled_files: int = 0
    critical_files: list[str] = field(default_factory=list)

    # Language distribution
    language_distribution: dict[str, int] = field(default_factory=dict)

    # Service boundaries
    service_count: int = 0
    microservice_indicators: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            "total_files": self.total_files,
            "total_dependencies": self.total_dependencies,
            "total_functions": self.total_functions,
            "total_classes": self.total_classes,
            "average_complexity": self.average_complexity,
            "max_complexity": self.max_complexity,
            "circular_dependencies": self.circular_dependencies,
            "orphan_files": self.orphan_files,
            "average_coupling": self.average_coupling,
            "highly_coupled_files": self.highly_coupled_files,
            "critical_files": self.critical_files,
            "language_distribution": self.language_distribution,
            "service_count": self.service_count,
            "microservice_indicators": self.microservice_indicators,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "GraphMetrics":
        """Load from dict."""
        return cls(
            total_files=data.get("total_files", 0),
            total_dependencies=data.get("total_dependencies", 0),
            total_functions=data.get("total_functions", 0),
            total_classes=data.get("total_classes", 0),
            average_complexity=data.get("average_complexity", 0.0),
            max_complexity=data.get("max_complexity", 0.0),
            circular_dependencies=data.get("circular_dependencies", 0),
            orphan_files=data.get("orphan_files", 0),
            average_coupling=data.get("average_coupling", 0.0),
            highly_coupled_files=data.get("highly_coupled_files", 0),
            critical_files=data.get("critical_files", []),
            language_distribution=data.get("language_distribution", {}),
            service_count=data.get("service_count", 0),
            microservice_indicators=data.get("microservice_indicators", []),
        )


@dataclass
class CodebaseGraph:
    """Complete graph representation of a codebase."""

    # Graph structure
    nodes: list[FileNode] = field(default_factory=list)
    edges: list[DependencyEdge] = field(default_factory=list)

    # Analysis results
    metrics: GraphMetrics = field(default_factory=GraphMetrics)
    architecture_pattern: str = ArchitecturePattern.UNKNOWN.value
    service_boundaries: dict[str, list[str]] = field(default_factory=dict)

    # Metadata
    project_dir: str = ""
    analyzed_at: str = ""
    graph_hash: str = ""
    analyzer_version: str = "1.0.0"

    def get_node_by_path(self, file_path: str) -> FileNode | None:
        """Get a node by its file path."""
        for node in self.nodes:
            if node.file_path == file_path:
                return node
        return None

    def get_dependencies_for_file(self, file_path: str) -> list[DependencyEdge]:
        """Get all outgoing dependencies for a file."""
        return [edge for edge in self.edges if edge.from_file == file_path]

    def get_dependents_for_file(self, file_path: str) -> list[DependencyEdge]:
        """Get all incoming dependencies for a file."""
        return [edge for edge in self.edges if edge.to_file == file_path]

    def get_files_in_service(self, service_name: str) -> list[FileNode]:
        """Get all files belonging to a specific service."""
        service_files = self.service_boundaries.get(service_name, [])
        return [node for node in self.nodes if node.file_path in service_files]

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            "nodes": [node.to_dict() for node in self.nodes],
            "edges": [edge.to_dict() for edge in self.edges],
            "metrics": self.metrics.to_dict(),
            "architecture_pattern": self.architecture_pattern,
            "service_boundaries": self.service_boundaries,
            "project_dir": self.project_dir,
            "analyzed_at": self.analyzed_at,
            "graph_hash": self.graph_hash,
            "analyzer_version": self.analyzer_version,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CodebaseGraph":
        """Load from dict."""
        graph = cls(
            nodes=[FileNode.from_dict(node_data) for node_data in data.get("nodes", [])],
            edges=[DependencyEdge.from_dict(edge_data) for edge_data in data.get("edges", [])],
            architecture_pattern=data.get("architecture_pattern", ArchitecturePattern.UNKNOWN.value),
            service_boundaries=data.get("service_boundaries", {}),
            project_dir=data.get("project_dir", ""),
            analyzed_at=data.get("analyzed_at", ""),
            graph_hash=data.get("graph_hash", ""),
            analyzer_version=data.get("analyzer_version", "1.0.0"),
        )

        if "metrics" in data:
            graph.metrics = GraphMetrics.from_dict(data["metrics"])

        return graph
