"""
Data Models for Architecture Pattern Detection
==============================================

Core data structures for representing detected architecture patterns,
service boundaries, and confidence scores.
"""

from dataclasses import asdict, dataclass, field
from enum import Enum

from .graph_models import ArchitecturePattern


class LayerType(Enum):
    """Types of layers in layered architecture."""

    PRESENTATION = "presentation"
    APPLICATION = "application"
    BUSINESS_LOGIC = "business_logic"
    DATA_ACCESS = "data_access"
    INFRASTRUCTURE = "infrastructure"
    UNKNOWN = "unknown"


@dataclass
class PatternIndicator:
    """Evidence that contributed to pattern detection."""

    indicator_type: str = ""  # e.g., "directory_structure", "import_pattern", "framework"
    description: str = ""
    evidence: str = ""
    confidence_contribution: float = 0.0  # How much this adds to total confidence

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            "indicator_type": self.indicator_type,
            "description": self.description,
            "evidence": self.evidence,
            "confidence_contribution": self.confidence_contribution,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PatternIndicator":
        """Load from dict."""
        return cls(
            indicator_type=data.get("indicator_type", ""),
            description=data.get("description", ""),
            evidence=data.get("evidence", ""),
            confidence_contribution=data.get("confidence_contribution", 0.0),
        )


@dataclass
class ArchitecturePatternDetection:
    """Detected architecture pattern with confidence score and evidence."""

    pattern: ArchitecturePattern = ArchitecturePattern.UNKNOWN
    confidence_score: float = 0.0  # 0.0 to 1.0
    indicators: list[PatternIndicator] = field(default_factory=list)

    # Additional pattern-specific details
    description: str = ""
    strengths: list[str] = field(default_factory=list)
    concerns: list[str] = field(default_factory=list)

    # For layered architectures
    detected_layers: dict[str, list[str]] = field(default_factory=dict)  # layer -> files

    # For microservices
    service_count: int = 0
    independent_deployables: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            "pattern": self.pattern.value if isinstance(self.pattern, ArchitecturePattern) else self.pattern,
            "confidence_score": self.confidence_score,
            "indicators": [ind.to_dict() for ind in self.indicators],
            "description": self.description,
            "strengths": self.strengths,
            "concerns": self.concerns,
            "detected_layers": self.detected_layers,
            "service_count": self.service_count,
            "independent_deployables": self.independent_deployables,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ArchitecturePatternDetection":
        """Load from dict."""
        pattern_value = data.get("pattern", ArchitecturePattern.UNKNOWN.value)
        try:
            pattern = ArchitecturePattern(pattern_value)
        except ValueError:
            # If it's not a valid ArchitecturePattern, store as string
            pattern = pattern_value

        detection = cls(
            pattern=pattern,
            confidence_score=data.get("confidence_score", 0.0),
            description=data.get("description", ""),
            service_count=data.get("service_count", 0),
        )

        if "indicators" in data:
            detection.indicators = [
                PatternIndicator.from_dict(ind_data) for ind_data in data["indicators"]
            ]
        if "strengths" in data:
            detection.strengths = data["strengths"]
        if "concerns" in data:
            detection.concerns = data["concerns"]
        if "detected_layers" in data:
            detection.detected_layers = data["detected_layers"]
        if "independent_deployables" in data:
            detection.independent_deployables = data["independent_deployables"]

        return detection


@dataclass
class ExposedAPI:
    """An API endpoint exposed by a service."""

    path: str = ""
    method: str = ""  # GET, POST, etc.
    handler_file: str = ""
    description: str = ""
    auth_required: bool = False

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            "path": self.path,
            "method": self.method,
            "handler_file": self.handler_file,
            "description": self.description,
            "auth_required": self.auth_required,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ExposedAPI":
        """Load from dict."""
        return cls(
            path=data.get("path", ""),
            method=data.get("method", ""),
            handler_file=data.get("handler_file", ""),
            description=data.get("description", ""),
            auth_required=data.get("auth_required", False),
        )


@dataclass
class ServiceBoundary:
    """Detected boundary of a single service/module in the codebase."""

    # Service identification
    name: str = ""
    service_type: str = ""  # backend, frontend, worker, library, etc.
    confidence_score: float = 0.0  # 0.0 to 1.0

    # Entry points
    entry_points: list[str] = field(default_factory=list)  # Main files that start the service

    # Dependencies
    internal_dependencies: list[str] = field(default_factory=list)  # Files within this service
    external_dependencies: list[str] = field(default_factory=list)  # Dependencies on other services
    library_dependencies: list[str] = field(default_factory=list)  # External libraries/packages

    # Exposed interfaces
    exposed_apis: list[ExposedAPI] = field(default_factory=list)
    exported_modules: list[str] = field(default_factory=list)

    # Service metadata
    path: str = ""
    language: str = ""
    framework: str = ""
    file_count: int = 0

    # Service characteristics
    is_standalone: bool = True  # Can it run independently?
    has_database: bool = False
    has_background_jobs: bool = False
    has_messaging: bool = False

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            "name": self.name,
            "service_type": self.service_type,
            "confidence_score": self.confidence_score,
            "entry_points": self.entry_points,
            "internal_dependencies": self.internal_dependencies,
            "external_dependencies": self.external_dependencies,
            "library_dependencies": self.library_dependencies,
            "exposed_apis": [api.to_dict() for api in self.exposed_apis],
            "exported_modules": self.exported_modules,
            "path": self.path,
            "language": self.language,
            "framework": self.framework,
            "file_count": self.file_count,
            "is_standalone": self.is_standalone,
            "has_database": self.has_database,
            "has_background_jobs": self.has_background_jobs,
            "has_messaging": self.has_messaging,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ServiceBoundary":
        """Load from dict."""
        boundary = cls(
            name=data.get("name", ""),
            service_type=data.get("service_type", ""),
            confidence_score=data.get("confidence_score", 0.0),
            entry_points=data.get("entry_points", []),
            internal_dependencies=data.get("internal_dependencies", []),
            external_dependencies=data.get("external_dependencies", []),
            library_dependencies=data.get("library_dependencies", []),
            exported_modules=data.get("exported_modules", []),
            path=data.get("path", ""),
            language=data.get("language", ""),
            framework=data.get("framework", ""),
            file_count=data.get("file_count", 0),
            is_standalone=data.get("is_standalone", True),
            has_database=data.get("has_database", False),
            has_background_jobs=data.get("has_background_jobs", False),
            has_messaging=data.get("has_messaging", False),
        )

        if "exposed_apis" in data:
            boundary.exposed_apis = [
                ExposedAPI.from_dict(api_data) for api_data in data["exposed_apis"]
            ]

        return boundary


@dataclass
class ArchitectureAnalysis:
    """Complete architecture analysis for a codebase."""

    # Pattern detection
    primary_pattern: ArchitecturePatternDetection = field(
        default_factory=ArchitecturePatternDetection
    )
    secondary_patterns: list[ArchitecturePatternDetection] = field(default_factory=list)

    # Service boundaries
    services: list[ServiceBoundary] = field(default_factory=list)
    service_relationships: dict[str, list[str]] = field(default_factory=dict)  # service -> dependencies

    # Architecture health metrics
    cohesion_score: float = 0.0  # How related are elements within modules?
    coupling_score: float = 0.0  # How dependent are modules on each other?
    modularity_score: float = 0.0  # How well-separated are the modules?

    # Metadata
    analyzed_at: str = ""
    analyzer_version: str = "1.0.0"
    project_dir: str = ""

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            "primary_pattern": self.primary_pattern.to_dict(),
            "secondary_patterns": [p.to_dict() for p in self.secondary_patterns],
            "services": [s.to_dict() for s in self.services],
            "service_relationships": self.service_relationships,
            "cohesion_score": self.cohesion_score,
            "coupling_score": self.coupling_score,
            "modularity_score": self.modularity_score,
            "analyzed_at": self.analyzed_at,
            "analyzer_version": self.analyzer_version,
            "project_dir": self.project_dir,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ArchitectureAnalysis":
        """Load from dict."""
        analysis = cls(
            analyzed_at=data.get("analyzed_at", ""),
            analyzer_version=data.get("analyzer_version", "1.0.0"),
            project_dir=data.get("project_dir", ""),
        )

        if "primary_pattern" in data:
            analysis.primary_pattern = ArchitecturePatternDetection.from_dict(
                data["primary_pattern"]
            )
        if "secondary_patterns" in data:
            analysis.secondary_patterns = [
                ArchitecturePatternDetection.from_dict(p_data)
                for p_data in data["secondary_patterns"]
            ]
        if "services" in data:
            analysis.services = [
                ServiceBoundary.from_dict(s_data) for s_data in data["services"]
            ]
        if "service_relationships" in data:
            analysis.service_relationships = data["service_relationships"]
        if "cohesion_score" in data:
            analysis.cohesion_score = data["cohesion_score"]
        if "coupling_score" in data:
            analysis.coupling_score = data["coupling_score"]
        if "modularity_score" in data:
            analysis.modularity_score = data["modularity_score"]

        return analysis

    def get_service_by_name(self, name: str) -> ServiceBoundary | None:
        """Get a service by its name."""
        for service in self.services:
            if service.name == name:
                return service
        return None

    def get_high_confidence_services(self, threshold: float = 0.7) -> list[ServiceBoundary]:
        """Get services with confidence above threshold."""
        return [s for s in self.services if s.confidence_score >= threshold]
