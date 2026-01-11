"""
Enhanced Analysis Result Model
==============================

Comprehensive result model that combines codebase graph analysis,
architecture pattern detection, service boundaries, and metadata
for caching and persistence.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from hashlib import sha256

from .architecture_models import ArchitectureAnalysis
from .graph_models import CodebaseGraph


class RiskLevel(Enum):
    """Risk level for impact analysis."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class ImpactAnalysis:
    """Analysis of the impact of modifying specific files."""

    # Files affected by the changes
    affected_files: list[str] = field(default_factory=list)

    # Services affected by the changes
    affected_services: list[str] = field(default_factory=list)

    # Risk level of the changes
    risk_level: RiskLevel = RiskLevel.LOW

    # Additional metadata
    total_files_modified: int = 0
    total_dependents: int = 0
    critical_files_affected: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            "affected_files": self.affected_files,
            "affected_services": self.affected_services,
            "risk_level": self.risk_level.value,
            "total_files_modified": self.total_files_modified,
            "total_dependents": self.total_dependents,
            "critical_files_affected": self.critical_files_affected,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ImpactAnalysis":
        """Load from dict."""
        risk_level_str = data.get("risk_level", "low")
        try:
            risk_level = RiskLevel(risk_level_str)
        except ValueError:
            risk_level = RiskLevel.LOW

        return cls(
            affected_files=data.get("affected_files", []),
            affected_services=data.get("affected_services", []),
            risk_level=risk_level,
            total_files_modified=data.get("total_files_modified", 0),
            total_dependents=data.get("total_dependents", 0),
            critical_files_affected=data.get("critical_files_affected", []),
        )


@dataclass
class EnhancedAnalysisResult:
    """Complete analysis result combining graph, architecture, and metadata."""

    # Core analysis components
    codebase_graph: CodebaseGraph = field(default_factory=CodebaseGraph)
    architecture_analysis: ArchitectureAnalysis = field(default_factory=ArchitectureAnalysis)

    # Metadata for caching and validation
    analysis_timestamp: str = ""
    project_hash: str = ""
    analyzer_version: str = "2.0.0"

    # Analysis metadata
    project_dir: str = ""
    total_files_analyzed: int = 0
    analysis_duration_seconds: float = 0.0

    # Caching metadata
    cache_key: str = ""
    is_cached: bool = False
    cache_hit: bool = False
    file_modification_times: dict[str, float] = field(default_factory=dict)

    def __post_init__(self):
        """Initialize derived fields after creation."""
        if not self.analysis_timestamp:
            self.analysis_timestamp = datetime.now().isoformat()

        if not self.project_hash and self.project_dir:
            self.project_hash = self._compute_project_hash()

        if not self.cache_key and self.project_hash:
            self.cache_key = self._compute_cache_key()

        if self.codebase_graph:
            self.total_files_analyzed = len(self.codebase_graph.nodes)

    def _compute_project_hash(self) -> str:
        """Compute a hash of the project for cache validation."""
        if not self.project_dir:
            return ""

        # Create hash from project directory and analyzer version
        hash_input = f"{self.project_dir}:{self.analyzer_version}"
        return sha256(hash_input.encode()).hexdigest()[:16]

    def _compute_cache_key(self) -> str:
        """Compute a unique cache key for this analysis."""
        components = [
            self.project_hash,
            self.analyzer_version,
            str(self.total_files_analyzed),
        ]
        return sha256(":".join(components).encode()).hexdigest()[:32]

    def get_primary_pattern(self) -> str:
        """Get the primary architecture pattern."""
        if (
            self.architecture_analysis
            and self.architecture_analysis.primary_pattern
        ):
            pattern = self.architecture_analysis.primary_pattern.pattern
            if hasattr(pattern, "value"):
                return pattern.value
            return str(pattern)
        return "unknown"

    def get_service_count(self) -> int:
        """Get the number of detected services."""
        if self.architecture_analysis and self.architecture_analysis.services:
            return len(self.architecture_analysis.services)
        return 0

    def get_high_confidence_services(self, threshold: float = 0.7) -> list:
        """Get services with confidence above threshold."""
        if self.architecture_analysis:
            return self.architecture_analysis.get_high_confidence_services(threshold)
        return []

    def get_total_dependencies(self) -> int:
        """Get total number of dependencies detected."""
        if self.codebase_graph and self.codebase_graph.edges:
            return len(self.codebase_graph.edges)
        return 0

    def get_circular_dependency_count(self) -> int:
        """Get the number of circular dependencies."""
        if self.codebase_graph and self.codebase_graph.metrics:
            return self.codebase_graph.metrics.circular_dependencies
        return 0

    def get_architecture_health_score(self) -> dict:
        """Get architecture health metrics as a dict."""
        if not self.architecture_analysis:
            return {"cohesion": 0.0, "coupling": 0.0, "modularity": 0.0}

        return {
            "cohesion": self.architecture_analysis.cohesion_score,
            "coupling": self.architecture_analysis.coupling_score,
            "modularity": self.architecture_analysis.modularity_score,
        }

    def is_stale(self, max_age_hours: float = 24.0) -> bool:
        """Check if the analysis is stale based on age."""
        if not self.analysis_timestamp:
            return True

        try:
            analysis_time = datetime.fromisoformat(self.analysis_timestamp)
            age_hours = (datetime.now() - analysis_time).total_seconds() / 3600
            return age_hours > max_age_hours
        except (ValueError, TypeError):
            return True

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            "codebase_graph": self.codebase_graph.to_dict(),
            "architecture_analysis": self.architecture_analysis.to_dict(),
            "analysis_timestamp": self.analysis_timestamp,
            "project_hash": self.project_hash,
            "analyzer_version": self.analyzer_version,
            "project_dir": self.project_dir,
            "total_files_analyzed": self.total_files_analyzed,
            "analysis_duration_seconds": self.analysis_duration_seconds,
            "cache_key": self.cache_key,
            "is_cached": self.is_cached,
            "cache_hit": self.cache_hit,
            "file_modification_times": self.file_modification_times,
        }

    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        import json

        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: dict) -> "EnhancedAnalysisResult":
        """Load from dict."""
        result = cls(
            analysis_timestamp=data.get("analysis_timestamp", ""),
            project_hash=data.get("project_hash", ""),
            analyzer_version=data.get("analyzer_version", "2.0.0"),
            project_dir=data.get("project_dir", ""),
            total_files_analyzed=data.get("total_files_analyzed", 0),
            analysis_duration_seconds=data.get("analysis_duration_seconds", 0.0),
            cache_key=data.get("cache_key", ""),
            is_cached=data.get("is_cached", False),
            cache_hit=data.get("cache_hit", False),
            file_modification_times=data.get("file_modification_times", {}),
        )

        if "codebase_graph" in data:
            result.codebase_graph = CodebaseGraph.from_dict(data["codebase_graph"])
        if "architecture_analysis" in data:
            result.architecture_analysis = ArchitectureAnalysis.from_dict(
                data["architecture_analysis"]
            )

        return result

    @classmethod
    def from_json(cls, json_str: str) -> "EnhancedAnalysisResult":
        """Load from JSON string."""
        import json

        data = json.loads(json_str)
        return cls.from_dict(data)

    def save_to_file(self, file_path: str) -> None:
        """Save analysis result to a JSON file."""
        with open(file_path, "w") as f:
            f.write(self.to_json())

    @classmethod
    def load_from_file(cls, file_path: str) -> "EnhancedAnalysisResult":
        """Load analysis result from a JSON file."""
        with open(file_path, "r") as f:
            return cls.from_json(f.read())

    def summary(self) -> str:
        """Get a human-readable summary of the analysis."""
        lines = [
            "=== Enhanced Analysis Result Summary ===",
            f"Primary Pattern: {self.get_primary_pattern()}",
            f"Services Detected: {self.get_service_count()}",
            f"Files Analyzed: {self.total_files_analyzed}",
            f"Total Dependencies: {self.get_total_dependencies()}",
            f"Circular Dependencies: {self.get_circular_dependency_count()}",
            "",
            "Architecture Health:",
            f"  Cohesion: {self.architecture_analysis.cohesion_score:.2f}",
            f"  Coupling: {self.architecture_analysis.coupling_score:.2f}",
            f"  Modularity: {self.architecture_analysis.modularity_score:.2f}",
            "",
            f"Analysis Time: {self.analysis_timestamp}",
            f"Duration: {self.analysis_duration_seconds:.2f}s",
            f"Cached: {self.is_cached}",
        ]
        return "\n".join(lines)
