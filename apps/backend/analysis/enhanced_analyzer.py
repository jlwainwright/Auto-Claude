"""
Enhanced Project Analyzer
=========================

Orchestrates enhanced project analysis combining dependency graphs,
architecture pattern detection, and service boundary detection.
Provides caching and backward compatibility with ProjectAnalyzer.
"""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import Any

from .architecture.pattern_detector import ArchitecturePatternDetector
from .architecture.service_boundary_detector import ServiceBoundaryDetector
from .cache import AnalysisCache
from .dependency.graph_builder import DependencyGraphBuilder
from .models.analysis_result import EnhancedAnalysisResult
from .models.architecture_models import (
    ArchitectureAnalysis,
    ArchitecturePatternDetection,
    ServiceBoundary,
)
from .models.graph_models import ArchitecturePattern, CodebaseGraph


class EnhancedProjectAnalyzer:
    """
    Enhanced project analyzer that combines multiple analysis techniques.

    Features:
    1. Dependency graph construction
    2. Architecture pattern detection
    3. Service boundary detection
    4. Caching with incremental updates
    5. Backward compatibility with ProjectAnalyzer
    """

    def __init__(
        self,
        project_dir: Path | str,
        spec_dir: Path | None = None,
        use_cache: bool = True,
        force_rebuild: bool = False,
    ):
        """
        Initialize the enhanced analyzer.

        Args:
            project_dir: Root directory of the project to analyze
            spec_dir: Optional spec directory for storing cache
            use_cache: Whether to use caching (default: True)
            force_rebuild: Force a full rebuild even if cache exists
        """
        self.project_dir = Path(project_dir).resolve()
        self.spec_dir = Path(spec_dir).resolve() if spec_dir else None
        self.use_cache = use_cache
        self.force_rebuild = force_rebuild

        # Initialize components
        self.graph_builder = DependencyGraphBuilder(self.project_dir, self.spec_dir)
        self.cache = AnalysisCache(self.project_dir, self.spec_dir) if use_cache else None

    def analyze(self) -> EnhancedAnalysisResult:
        """
        Perform full enhanced project analysis.

        Returns:
            EnhancedAnalysisResult with complete analysis data
        """
        start_time = time.time()

        # Check cache first
        if self.use_cache and not self.force_rebuild:
            cached_result = self.cache.load_cache() if self.cache else None
            if cached_result and not self.cache.should_invalidate(cached_result):
                # Cache hit - return cached result
                cached_result.cache_hit = True
                return cached_result

        # Build dependency graph
        codebase_graph = self.graph_builder.build_incremental(force=self.force_rebuild)

        # Perform architecture analysis
        architecture_analysis = self._perform_architecture_analysis(codebase_graph)

        # Calculate analysis duration
        duration = time.time() - start_time

        # Create enhanced result
        result = EnhancedAnalysisResult(
            codebase_graph=codebase_graph,
            architecture_analysis=architecture_analysis,
            project_dir=str(self.project_dir),
            analysis_duration_seconds=duration,
        )

        # Update cache metadata
        if self.cache:
            all_files = list(self.project_dir.rglob("*"))
            source_files = [
                f
                for f in all_files
                if f.is_file()
                and f.suffix in {".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs"}
            ]
            self.cache.update_cache_metadata(result, source_files)

        # Save to cache
        if self.use_cache and self.cache:
            self.cache.save_cache(result)

        return result

    def _perform_architecture_analysis(
        self, codebase_graph: CodebaseGraph
    ) -> ArchitectureAnalysis:
        """
        Perform architecture pattern and service boundary detection.

        Args:
            codebase_graph: The dependency graph to analyze

        Returns:
            ArchitectureAnalysis with detected patterns and services
        """
        # Initialize analysis
        analysis = ArchitectureAnalysis(
            project_dir=str(self.project_dir),
            analyzed_at=datetime.now().isoformat(),
        )

        # Create a basic analysis dict for the pattern detector
        analysis_dict: dict[str, Any] = {}

        # Detect architecture patterns
        pattern_detector = ArchitecturePatternDetector(self.project_dir, analysis_dict)
        pattern_detector.detect_all_patterns()

        # Convert detected patterns to ArchitecturePatternDetection objects
        detected_patterns = analysis_dict.get("architecture_patterns", {})

        # Create pattern detections list
        pattern_detections = []
        for pattern_name, pattern_data in detected_patterns.items():
            detection = ArchitecturePatternDetection(
                pattern=ArchitecturePattern(pattern_name),
                confidence_score=pattern_data.get("confidence", 0.0) / 100.0,  # Convert to 0-1
                indicators=[],
                description=f"Detected {pattern_name} architecture pattern",
                service_count=pattern_data.get("service_count", 0),
                independent_deployables=pattern_data.get("services", []),
            )
            pattern_detections.append(detection)

        # Sort by confidence and set primary/secondary
        pattern_detections.sort(key=lambda p: p.confidence_score, reverse=True)

        if pattern_detections:
            analysis.primary_pattern = pattern_detections[0]
            analysis.secondary_patterns = pattern_detections[1:]

        # Detect service boundaries
        boundary_detector = ServiceBoundaryDetector(self.project_dir, analysis_dict)
        boundary_detector.detect_boundaries()

        # Convert detected services to ServiceBoundary objects
        detected_services = analysis_dict.get("services", {})
        deployable_units = detected_services.get("deployable_units", {})

        for service_name, service_data in deployable_units.items():
            service = self._create_service_boundary(
                service_name, service_data, analysis_dict, codebase_graph
            )
            analysis.services.append(service)

        # Map service relationships
        service_deps = analysis_dict.get("service_dependencies", {})
        for service_name, dependencies in service_deps.items():
            dep_targets = [dep.get("target", "") for dep in dependencies if "target" in dep]
            if dep_targets:
                analysis.service_relationships[service_name] = dep_targets

        # Calculate architecture health metrics
        self._calculate_architecture_metrics(analysis, codebase_graph)

        return analysis

    def _create_service_boundary(
        self,
        service_name: str,
        service_data: dict[str, Any],
        analysis_dict: dict[str, Any],
        codebase_graph: CodebaseGraph,
    ) -> ServiceBoundary:
        """
        Create a ServiceBoundary object from detected service data.

        Args:
            service_name: Name of the service
            service_data: Raw service detection data
            analysis_dict: Full analysis dictionary
            codebase_graph: Dependency graph

        Returns:
            ServiceBoundary object
        """
        service_path = self.project_dir / service_data.get("path", service_name)

        # Get service type
        service_type = service_data.get("type", "unknown")

        # Get entry points
        entry_points = self._get_entry_points(service_path)

        # Get language and framework
        language, framework = self._get_service_language_and_framework(service_path)

        # Get internal dependencies (files in this service)
        internal_deps = []
        for node in codebase_graph.nodes:
            node_path = Path(node.file_path)
            # Check if node is within this service
            try:
                rel_path = node_path.relative_to(self.project_dir)
                service_rel = service_path.relative_to(self.project_dir)
                if str(rel_path).startswith(str(service_rel)):
                    internal_deps.append(node.file_path)
            except ValueError:
                # Node is not relative to project
                continue

        # Get external dependencies (on other services)
        external_deps = []
        service_relationships = analysis_dict.get("service_dependencies", {}).get(
            service_name, []
        )
        for dep in service_relationships:
            if "target" in dep:
                external_deps.append(dep["target"])

        return ServiceBoundary(
            name=service_name,
            service_type=service_type,
            confidence_score=0.8,  # Default confidence for detected services
            entry_points=entry_points,
            internal_dependencies=internal_deps[:20],  # Limit to 20
            external_dependencies=external_deps,
            library_dependencies=[],  # Could be extracted from package files
            path=str(service_path.relative_to(self.project_dir)),
            language=language,
            framework=framework,
            file_count=len(internal_deps),
            is_standalone=True,  # Assume standalone if detected as service
            has_database=False,  # Could be detected from config
            has_background_jobs=False,
            has_messaging=False,
        )

    def _get_entry_points(self, service_path: Path) -> list[str]:
        """Get entry points for a service."""
        entry_points = []

        # Common entry point patterns
        entry_patterns = [
            "main.py",
            "app.py",
            "__main__.py",
            "server.py",
            "index.js",
            "index.ts",
            "main.js",
            "main.ts",
            "server.js",
            "server.ts",
        ]

        for pattern in entry_patterns:
            entry_file = service_path / pattern
            if entry_file.exists():
                entry_points.append(str(entry_file.relative_to(self.project_dir)))

        return entry_points

    def _get_service_language_and_framework(
        self, service_path: Path
    ) -> tuple[str, str]:
        """
        Detect the language and framework for a service.

        Returns:
            Tuple of (language, framework)
        """
        # Check package files
        if (service_path / "package.json").exists():
            return "JavaScript", "Node.js"

        # Check Python files
        py_files = list(service_path.glob("*.py"))
        if py_files:
            return "Python", ""

        # Check Go files
        go_files = list(service_path.glob("*.go"))
        if go_files:
            return "Go", ""

        # Check Rust files
        rs_files = list(service_path.glob("*.rs"))
        if rs_files:
            return "Rust", ""

        return "Unknown", ""

    def _calculate_architecture_metrics(
        self, analysis: ArchitectureAnalysis, codebase_graph: CodebaseGraph
    ) -> None:
        """
        Calculate architecture health metrics.

        Args:
            analysis: ArchitectureAnalysis to update
            codebase_graph: Dependency graph to analyze
        """
        services = analysis.services
        num_services = len(services)

        if num_services == 0:
            # No services detected - use basic graph metrics
            analysis.cohesion_score = 0.5
            analysis.coupling_score = codebase_graph.metrics.average_coupling / 100.0
            analysis.modularity_score = 0.0
            return

        # Calculate cohesion: internal dependencies vs total dependencies
        total_internal = 0
        total_external = 0

        for service in services:
            total_internal += len(service.internal_dependencies)
            total_external += len(service.external_dependencies)

        total_deps = total_internal + total_external
        if total_deps > 0:
            analysis.cohesion_score = total_internal / total_deps
        else:
            analysis.cohesion_score = 0.5

        # Calculate coupling: average external dependencies per service
        if num_services > 0:
            avg_external = total_external / num_services
            # Normalize: assume 10+ external deps is high coupling
            analysis.coupling_score = min(avg_external / 10.0, 1.0)
        else:
            analysis.coupling_score = 0.0

        # Calculate modularity: based on service count and independence
        # More services with low coupling = high modularity
        if num_services > 1:
            # Penalize high coupling
            coupling_penalty = analysis.coupling_score * 0.5
            # Reward multiple services (diminishing returns)
            service_bonus = min(num_services / 10.0, 0.5)
            analysis.modularity_score = min(service_bonus + (1.0 - coupling_penalty), 1.0)
        else:
            # Single service - low modularity
            analysis.modularity_score = 0.2

    def get_summary(self) -> dict[str, Any]:
        """
        Get a summary of the analysis (for backward compatibility).

        Returns:
            Dict with basic analysis information
        """
        result = self.analyze()

        return {
            "project_dir": str(self.project_dir),
            "architecture_pattern": result.get_primary_pattern(),
            "services": [s.name for s in result.architecture_analysis.services],
            "total_files": result.total_files_analyzed,
            "total_dependencies": result.get_total_dependencies(),
            "circular_dependencies": result.get_circular_dependency_count(),
            "cohesion": result.architecture_analysis.cohesion_score,
            "coupling": result.architecture_analysis.coupling_score,
            "modularity": result.architecture_analysis.modularity_score,
        }

    def get_detected_services(self) -> list[dict[str, Any]]:
        """
        Get list of detected services with their details.

        Returns:
            List of service information dicts
        """
        result = self.analyze()
        services = []

        for service in result.architecture_analysis.services:
            services.append(
                {
                    "name": service.name,
                    "type": service.service_type,
                    "path": service.path,
                    "language": service.language,
                    "framework": service.framework,
                    "file_count": service.file_count,
                    "entry_points": service.entry_points,
                    "confidence": service.confidence_score,
                }
            )

        return services

    def print_summary(self) -> None:
        """Print a human-readable summary of the analysis."""
        result = self.analyze()
        architecture = result.architecture_analysis

        print(f"\n=== Enhanced Project Analysis Summary ===")
        print(f"Project: {self.project_dir}")
        print(f"Primary Pattern: {result.get_primary_pattern()}")
        print(f"Services Detected: {len(architecture.services)}")
        print(f"Total Files Analyzed: {result.total_files_analyzed}")
        print(f"Analysis Duration: {result.analysis_duration_seconds:.2f}s")
        print(f"\nServices:")
        for service in architecture.services:
            print(f"  - {service.name} ({service.service_type})")
        print(f"\nArchitecture Health:")
        print(f"  Cohesion: {architecture.cohesion_score:.2f}")
        print(f"  Coupling: {architecture.coupling_score:.2f}")
        print(f"  Modularity: {architecture.modularity_score:.2f}")
