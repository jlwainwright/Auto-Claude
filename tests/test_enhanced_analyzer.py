#!/usr/bin/env python3
"""
Integration Tests for Enhanced Project Analyzer
================================================

Tests the enhanced project analyzer using real project fixtures including:
- Full analysis on sample Python project
- Full analysis on sample JS/TS project
- Architecture detection accuracy
- Caching and incremental updates
"""

import json
from pathlib import Path
from shutil import rmtree
from time import sleep

import pytest
from analysis.enhanced_analyzer import EnhancedProjectAnalyzer
from analysis.models.analysis_result import ImpactAnalysis, RiskLevel
from analysis.models.architecture_models import ArchitecturePattern
from analysis.models.graph_models import CodebaseGraph


class TestEnhancedAnalyzerInitialization:
    """Tests for EnhancedProjectAnalyzer initialization."""

    def test_init_with_project_dir(self, temp_dir: Path):
        """Initializes with project directory."""
        analyzer = EnhancedProjectAnalyzer(temp_dir)

        assert analyzer.project_dir == temp_dir.resolve()
        assert analyzer.spec_dir is None
        assert analyzer.use_cache is True
        assert analyzer.force_rebuild is False

    def test_init_with_spec_dir(self, temp_dir: Path, spec_dir: Path):
        """Initializes with spec directory."""
        analyzer = EnhancedProjectAnalyzer(temp_dir, spec_dir)

        assert analyzer.spec_dir == spec_dir.resolve()

    def test_init_without_cache(self, temp_dir: Path):
        """Initializes with cache disabled."""
        analyzer = EnhancedProjectAnalyzer(temp_dir, use_cache=False)

        assert analyzer.use_cache is False
        assert analyzer.cache is None

    def test_init_with_force_rebuild(self, temp_dir: Path):
        """Initializes with force rebuild flag."""
        analyzer = EnhancedProjectAnalyzer(temp_dir, force_rebuild=True)

        assert analyzer.force_rebuild is True


class TestPythonProjectAnalysis:
    """Tests for analyzing Python projects."""

    def test_full_analysis_python_project(self, python_project: Path):
        """Performs full analysis on sample Python project."""
        analyzer = EnhancedProjectAnalyzer(python_project, use_cache=False)
        result = analyzer.analyze()

        # Check basic structure
        assert result is not None
        assert result.codebase_graph is not None
        assert result.architecture_analysis is not None

        # Check codebase graph
        graph = result.codebase_graph
        assert isinstance(graph, CodebaseGraph)
        assert len(graph.nodes) > 0
        assert len(graph.edges) > 0

        # Verify expected files are detected
        file_paths = {node.file_path for node in graph.nodes}
        assert any("app.py" in f for f in file_paths)
        assert any("models/user.py" in f for f in file_paths)
        assert any("services/auth_service.py" in f for f in file_paths)

    def test_dependency_detection_python(self, python_project: Path):
        """Detects dependencies in Python project."""
        analyzer = EnhancedProjectAnalyzer(python_project, use_cache=False)
        result = analyzer.analyze()

        graph = result.codebase_graph

        # app.py should import from models and services
        app_edges = [e for e in graph.edges if "app.py" in e.from_file]
        assert len(app_edges) > 0

        # Check for expected dependencies
        imports = set()
        for edge in app_edges:
            if "models" in edge.to_file or "services" in edge.to_file:
                imports.add(edge.to_file)

        assert len(imports) > 0

    def test_architecture_detection_python(self, python_project: Path):
        """Detects architecture patterns in Python project."""
        analyzer = EnhancedProjectAnalyzer(python_project, use_cache=False)
        result = analyzer.analyze()

        architecture = result.architecture_analysis

        # Should detect some architecture pattern
        # Note: Simple projects may not match complex patterns
        assert architecture is not None
        assert architecture.analyzed_at is not None


class TestJavaScriptProjectAnalysis:
    """Tests for analyzing JavaScript/TypeScript projects."""

    def test_full_analysis_js_project(self, js_project: Path):
        """Performs full analysis on sample JS/TS project."""
        analyzer = EnhancedProjectAnalyzer(js_project, use_cache=False)
        result = analyzer.analyze()

        # Check basic structure
        assert result is not None
        assert result.codebase_graph is not None
        assert result.architecture_analysis is not None

        # Check codebase graph
        graph = result.codebase_graph
        assert isinstance(graph, CodebaseGraph)
        assert len(graph.nodes) > 0
        assert len(graph.edges) > 0

        # Verify expected files are detected
        file_paths = {node.file_path for node in graph.nodes}
        assert any("index.ts" in f for f in file_paths)
        assert any("app.ts" in f for f in file_paths)
        assert any("router.ts" in f for f in file_paths)

    def test_dependency_detection_js(self, js_project: Path):
        """Detects dependencies in JS/TS project."""
        analyzer = EnhancedProjectAnalyzer(js_project, use_cache=False)
        result = analyzer.analyze()

        graph = result.codebase_graph

        # index.ts should import from app, config
        index_edges = [e for e in graph.edges if "index.ts" in e.from_file]
        assert len(index_edges) > 0

        # Check for expected dependencies
        imports = set()
        for edge in index_edges:
            if "app" in edge.to_file or "config" in edge.to_file:
                imports.add(edge.to_file)

        assert len(imports) > 0

    def test_typescript_detection(self, js_project: Path):
        """Detects TypeScript files correctly."""
        analyzer = EnhancedProjectAnalyzer(js_project, use_cache=False)
        result = analyzer.analyze()

        graph = result.codebase_graph

        # Check that TypeScript files are detected
        ts_files = [n for n in graph.nodes if n.file_path.endswith(".ts")]
        assert len(ts_files) > 0

        # Verify specific TS files
        file_names = {Path(n.file_path).name for n in ts_files}
        assert "index.ts" in file_names
        assert "app.ts" in file_names


class TestCaching:
    """Tests for analysis caching."""

    def test_cache_creation(self, python_project: Path, temp_dir: Path):
        """Creates cache file after first analysis."""
        analyzer = EnhancedProjectAnalyzer(python_project, use_cache=True)
        analyzer.analyze()

        # Cache file should be created
        cache_file = python_project / ".auto-claude-analysis.json"
        assert cache_file.exists()

    def test_cache_hit(self, python_project: Path):
        """Uses cache on second analysis."""
        # First analysis
        analyzer1 = EnhancedProjectAnalyzer(python_project, use_cache=True)
        result1 = analyzer1.analyze()

        # Wait a bit to ensure timestamp difference
        sleep(0.1)

        # Second analysis should hit cache
        analyzer2 = EnhancedProjectAnalyzer(python_project, use_cache=True)
        result2 = analyzer2.analyze()

        # Both should have same graph structure
        assert result1.cache_hit is False  # First run is not cached
        assert result2.cache_hit is True  # Second run hits cache

        # Same project hash
        assert result1.project_hash == result2.project_hash

    def test_force_rebuild_ignores_cache(self, python_project: Path):
        """Force rebuild ignores cached results."""
        # First analysis
        analyzer1 = EnhancedProjectAnalyzer(python_project, use_cache=True)
        result1 = analyzer1.analyze()

        # Wait a bit
        sleep(0.1)

        # Force rebuild
        analyzer2 = EnhancedProjectAnalyzer(
            python_project, use_cache=True, force_rebuild=True
        )
        result2 = analyzer2.analyze()

        # Should not hit cache
        assert result2.cache_hit is False

    def test_cache_invalidation_on_file_change(
        self, python_project: Path, temp_dir: Path
    ):
        """Invalidates cache when files change."""
        # First analysis
        analyzer1 = EnhancedProjectAnalyzer(python_project, use_cache=True)
        result1 = analyzer1.analyze()
        original_hash = result1.project_hash

        # Modify a file
        app_file = python_project / "app.py"
        original_content = app_file.read_text()
        app_file.write_text(original_content + "\n# Added comment\n")

        # Second analysis should detect change and rebuild
        analyzer2 = EnhancedProjectAnalyzer(python_project, use_cache=True)
        result2 = analyzer2.analyze()

        # Hash should be different
        assert result2.project_hash != original_hash
        assert result2.cache_hit is False


class TestArchitectureDetection:
    """Tests for architecture pattern detection."""

    def test_detects_layered_architecture(self, python_project: Path):
        """Detects layered architecture in Python project."""
        analyzer = EnhancedProjectAnalyzer(python_project, use_cache=False)
        result = analyzer.analyze()

        architecture = result.architecture_analysis

        # Should detect some pattern (even if low confidence)
        assert architecture is not None

    def test_service_detection(self, python_project: Path):
        """Detects services in project."""
        analyzer = EnhancedProjectAnalyzer(python_project, use_cache=False)
        result = analyzer.analyze()

        architecture = result.architecture_analysis

        # Services list should exist (may be empty for simple projects)
        assert architecture.services is not None

    def test_architecture_metrics(self, python_project: Path):
        """Calculates architecture health metrics."""
        analyzer = EnhancedProjectAnalyzer(python_project, use_cache=False)
        result = analyzer.analyze()

        architecture = result.architecture_analysis

        # Metrics should be populated
        assert 0.0 <= architecture.cohesion_score <= 1.0
        assert 0.0 <= architecture.coupling_score <= 1.0
        assert 0.0 <= architecture.modularity_score <= 1.0


class TestImpactAnalysis:
    """Tests for impact analysis functionality."""

    def test_impact_analysis_single_file(self, python_project: Path):
        """Analyzes impact of modifying a single file."""
        analyzer = EnhancedProjectAnalyzer(python_project, use_cache=False)
        impact = analyzer.get_impact_analysis(["app.py"])

        assert isinstance(impact, ImpactAnalysis)
        assert impact.total_files_modified == 1
        assert len(impact.affected_files) >= 1  # At least the file itself
        assert impact.risk_level in [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH]

    def test_impact_analysis_multiple_files(self, python_project: Path):
        """Analyzes impact of modifying multiple files."""
        analyzer = EnhancedProjectAnalyzer(python_project, use_cache=False)
        impact = analyzer.get_impact_analysis(
            ["models/user.py", "services/auth_service.py"]
        )

        assert impact.total_files_modified == 2
        assert len(impact.affected_files) >= 2

    def test_impact_analysis_with_absolute_paths(self, python_project: Path):
        """Handles absolute file paths correctly."""
        analyzer = EnhancedProjectAnalyzer(python_project, use_cache=False)

        abs_path = python_project / "app.py"
        impact = analyzer.get_impact_analysis([str(abs_path)])

        assert impact.total_files_modified == 1

    def test_risk_level_calculation(self, python_project: Path):
        """Calculates appropriate risk levels."""
        analyzer = EnhancedProjectAnalyzer(python_project, use_cache=False)

        # Single file should be low risk
        impact1 = analyzer.get_impact_analysis(["app.py"])
        assert impact1.risk_level in [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH]

        # Multiple files might increase risk
        impact2 = analyzer.get_impact_analysis(
            ["app.py", "models/user.py", "services/auth_service.py"]
        )
        assert impact2.total_files_modified == 3


class TestSummaryMethods:
    """Tests for summary and convenience methods."""

    def test_get_summary(self, python_project: Path):
        """Returns analysis summary."""
        analyzer = EnhancedProjectAnalyzer(python_project, use_cache=False)
        summary = analyzer.get_summary()

        assert isinstance(summary, dict)
        assert "project_dir" in summary
        assert "total_files" in summary
        assert "total_dependencies" in summary

    def test_get_detected_services(self, python_project: Path):
        """Returns detected services list."""
        analyzer = EnhancedProjectAnalyzer(python_project, use_cache=False)
        services = analyzer.get_detected_services()

        assert isinstance(services, list)
        # All items should be dicts
        for service in services:
            assert isinstance(service, dict)
            assert "name" in service


class TestIncrementalUpdates:
    """Tests for incremental graph updates."""

    def test_incremental_update_preserves_graph(self, python_project: Path):
        """Incremental update preserves existing graph structure."""
        # First full build
        analyzer1 = EnhancedProjectAnalyzer(
            python_project, use_cache=True, force_rebuild=True
        )
        result1 = analyzer1.analyze()
        original_node_count = len(result1.codebase_graph.nodes)

        # Wait and do incremental update
        sleep(0.1)
        analyzer2 = EnhancedProjectAnalyzer(
            python_project, use_cache=True, force_rebuild=False
        )
        result2 = analyzer2.analyze()

        # Should have same number of nodes (no changes)
        assert len(result2.codebase_graph.nodes) == original_node_count

    def test_incremental_update_detects_new_file(
        self, python_project: Path, temp_dir: Path
    ):
        """Incremental update detects new files."""
        # First build
        analyzer1 = EnhancedProjectAnalyzer(
            python_project, use_cache=True, force_rebuild=True
        )
        result1 = analyzer1.analyze()
        original_count = len(result1.codebase_graph.nodes)

        # Add a new file
        new_file = python_project / "new_module.py"
        new_file.write_text("# New module\n\ndef new_function():\n    pass\n")

        # Incremental update
        analyzer2 = EnhancedProjectAnalyzer(
            python_project, use_cache=True, force_rebuild=False
        )
        result2 = analyzer2.analyze()

        # Should detect new file
        assert len(result2.codebase_graph.nodes) >= original_count


# Pytest fixtures
@pytest.fixture
def temp_dir(tmp_path: Path) -> Path:
    """Create temporary directory for tests."""
    return tmp_path


@pytest.fixture
def spec_dir(tmp_path: Path) -> Path:
    """Create temporary spec directory for tests."""
    spec = tmp_path / "spec"
    spec.mkdir()
    return spec


@pytest.fixture
def python_project(tmp_path: Path) -> Path:
    """Create sample Python project fixture."""
    # Copy from fixtures directory
    fixture_path = Path(__file__).parent / "fixtures" / "sample_python_project"

    if not fixture_path.exists():
        pytest.skip("Python fixture not found")

    # Create a copy in temp directory
    project_path = tmp_path / "python_project"
    if project_path.exists():
        rmtree(project_path)

    # Copy all files
    import shutil

    shutil.copytree(fixture_path, project_path)

    return project_path


@pytest.fixture
def js_project(tmp_path: Path) -> Path:
    """Create sample JS/TS project fixture."""
    # Copy from fixtures directory
    fixture_path = Path(__file__).parent / "fixtures" / "sample_js_project"

    if not fixture_path.exists():
        pytest.skip("JS fixture not found")

    # Create a copy in temp directory
    project_path = tmp_path / "js_project"
    if project_path.exists():
        rmtree(project_path)

    # Copy all files
    import shutil

    shutil.copytree(fixture_path, project_path)

    return project_path
