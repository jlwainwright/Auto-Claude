"""
Context Builder
===============

Main builder class that orchestrates context building for tasks.
"""

import asyncio
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from analysis.enhanced_analyzer import EnhancedProjectAnalyzer
from .categorizer import FileCategorizer
from .graphiti_integration import fetch_graph_hints, is_graphiti_enabled
from .keyword_extractor import KeywordExtractor
from .models import FileMatch, TaskContext
from .pattern_discovery import PatternDiscoverer
from .search import CodeSearcher
from .service_matcher import ServiceMatcher


class ContextBuilder:
    """Builds task-specific context by searching the codebase."""

    def __init__(self, project_dir: Path, project_index: dict | None = None):
        self.project_dir = project_dir.resolve()
        self.project_index = project_index or self._load_project_index()

        # Initialize components
        self.searcher = CodeSearcher(self.project_dir)
        self.service_matcher = ServiceMatcher(self.project_index)
        self.keyword_extractor = KeywordExtractor()
        self.categorizer = FileCategorizer()
        self.pattern_discoverer = PatternDiscoverer(self.project_dir)

    def _load_project_index(self) -> dict:
        """Load project index from file or create new one (.auto-claude is the installed instance)."""
        index_file = self.project_dir / ".auto-claude" / "project_index.json"
        if index_file.exists():
            with open(index_file) as f:
                return json.load(f)

        # Try to create one
        from analyzer import analyze_project

        return analyze_project(self.project_dir)

    def _create_codebase_graph_summary(
        self, codebase_graph: Any
    ) -> dict[str, Any]:
        """
        Create a summary of the codebase graph for context.

        Args:
            codebase_graph: CodebaseGraph object from enhanced analysis

        Returns:
            Dictionary with graph summary (key files, dependency counts, etc.)
        """
        # Get key files (highly connected files)
        key_files = []
        if hasattr(codebase_graph, 'nodes'):
            # Sort nodes by dependency count (most connected first)
            nodes_by_connections = sorted(
                codebase_graph.nodes.values(),
                key=lambda n: len(getattr(n, 'imports', [])) + len(getattr(n, 'exported_by', [])),
                reverse=True
            )[:20]  # Top 20 most connected files

            key_files = [
                {
                    "path": getattr(node, 'path', ''),
                    "language": getattr(node, 'language', ''),
                    "dependency_count": len(getattr(node, 'imports', [])) + len(getattr(node, 'exported_by', [])),
                }
                for node in nodes_by_connections
            ]

        return {
            "total_files": len(getattr(codebase_graph, 'nodes', {})),
            "total_dependencies": len(getattr(codebase_graph, 'edges', [])),
            "key_files": key_files,
        }

    def _extract_architecture_patterns(self, analysis_result: Any) -> list[dict]:
        """
        Extract detected architecture patterns from analysis result.

        Args:
            analysis_result: EnhancedAnalysisResult from enhanced analysis

        Returns:
            List of detected patterns with confidence scores
        """
        patterns = []

        if hasattr(analysis_result, 'architecture_analysis'):
            arch_analysis = analysis_result.architecture_analysis
            if hasattr(arch_analysis, 'patterns'):
                for pattern in arch_analysis.patterns:
                    patterns.append({
                        "name": getattr(pattern, 'name', ''),
                        "confidence": getattr(pattern, 'confidence', 0.0),
                        "description": getattr(pattern, 'description', ''),
                    })

        return patterns

    def _extract_service_boundaries(self, analysis_result: Any) -> list[dict]:
        """
        Extract identified service boundaries from analysis result.

        Args:
            analysis_result: EnhancedAnalysisResult from enhanced analysis

        Returns:
            List of service boundaries
        """
        boundaries = []

        if hasattr(analysis_result, 'architecture_analysis'):
            arch_analysis = analysis_result.architecture_analysis
            if hasattr(arch_analysis, 'service_boundaries'):
                for boundary in arch_analysis.service_boundaries:
                    boundaries.append({
                        "name": getattr(boundary, 'name', ''),
                        "entry_points": getattr(boundary, 'entry_points', []),
                        "dependencies": getattr(boundary, 'dependencies', []),
                    })

        return boundaries

    def _extract_file_dependencies(
        self,
        analysis_result: Any,
        files_of_interest: list[str]
    ) -> dict[str, list[str]]:
        """
        Extract dependencies for specific files from analysis result.

        Args:
            analysis_result: EnhancedAnalysisResult from enhanced analysis
            files_of_interest: List of file paths to get dependencies for

        Returns:
            Dictionary mapping file paths to their dependencies
        """
        dependencies = {}

        if hasattr(analysis_result, 'codebase_graph'):
            graph = analysis_result.codebase_graph

            for file_path in files_of_interest:
                # Find the node for this file
                node = None
                if hasattr(graph, 'nodes'):
                    # Try exact match first
                    node = graph.nodes.get(file_path)

                    # Try relative match if not found
                    if not node:
                        for node_path, node_obj in graph.nodes.items():
                            if file_path in node_path or node_path in file_path:
                                node = node_obj
                                break

                if node:
                    deps = []
                    if hasattr(node, 'imports'):
                        deps = [str(imp) for imp in node.imports]
                    dependencies[file_path] = deps

        return dependencies

    def _add_enhanced_analysis(
        self,
        task: str,
        files_to_modify: list[dict],
        spec_dir: Path | None = None,
    ) -> tuple[dict | None, list[dict] | None, list[dict] | None, dict | None]:
        """
        Add enhanced analysis data to context.

        Args:
            task: Task description
            files_to_modify: List of files to be modified
            spec_dir: Optional spec directory for caching

        Returns:
            Tuple of (graph_summary, architecture_patterns, service_boundaries, file_dependencies)
        """
        try:
            # Initialize enhanced analyzer
            analyzer = EnhancedProjectAnalyzer(
                project_dir=self.project_dir,
                spec_dir=spec_dir,
                use_cache=True,
            )

            # Run enhanced analysis
            analysis_result = analyzer.analyze()

            # Create graph summary
            graph_summary = self._create_codebase_graph_summary(
                analysis_result.codebase_graph
            )

            # Extract architecture patterns
            architecture_patterns = self._extract_architecture_patterns(
                analysis_result
            )

            # Extract service boundaries
            service_boundaries = self._extract_service_boundaries(
                analysis_result
            )

            # Extract file dependencies for files to be modified
            files_of_interest = [f.get('path', '') for f in files_to_modify if isinstance(f, dict) and 'path' in f]
            file_dependencies = self._extract_file_dependencies(
                analysis_result,
                files_of_interest
            ) if files_of_interest else None

            return (
                graph_summary,
                architecture_patterns,
                service_boundaries,
                file_dependencies,
            )

        except Exception:
            # Enhanced analysis is optional - fail gracefully
            return None, None, None, None

    def build_context(
        self,
        task: str,
        services: list[str] | None = None,
        keywords: list[str] | None = None,
        include_graph_hints: bool = True,
        spec_dir: Path | None = None,
        include_enhanced_analysis: bool = True,
    ) -> TaskContext:
        """
        Build context for a specific task.

        Args:
            task: Description of the task
            services: List of service names to search (None = auto-detect)
            keywords: Additional keywords to search for
            include_graph_hints: Whether to include historical hints from Graphiti
            spec_dir: Optional spec directory for enhanced analysis caching
            include_enhanced_analysis: Whether to include enhanced analysis data

        Returns:
            TaskContext with relevant files and patterns
        """
        # Auto-detect services if not specified
        if not services:
            services = self.service_matcher.suggest_services(task)

        # Extract keywords from task if not provided
        if not keywords:
            keywords = self.keyword_extractor.extract_keywords(task)

        # Search each service
        all_matches: list[FileMatch] = []
        service_contexts = {}

        for service_name in services:
            service_info = self.project_index.get("services", {}).get(service_name)
            if not service_info:
                continue

            service_path = Path(service_info.get("path", service_name))
            if not service_path.is_absolute():
                service_path = self.project_dir / service_path

            # Search this service
            matches = self.searcher.search_service(service_path, service_name, keywords)
            all_matches.extend(matches)

            # Load or generate service context
            service_contexts[service_name] = self._get_service_context(
                service_path, service_name, service_info
            )

        # Categorize matches
        files_to_modify, files_to_reference = self.categorizer.categorize_matches(
            all_matches, task
        )

        # Discover patterns from reference files
        patterns = self.pattern_discoverer.discover_patterns(
            files_to_reference, keywords
        )

        # Get graph hints (synchronously wrap async call)
        graph_hints = []
        if include_graph_hints and is_graphiti_enabled():
            try:
                # Run the async function in a new event loop if necessary
                try:
                    loop = asyncio.get_running_loop()
                    # We're already in an async context - this shouldn't happen in CLI
                    # but handle it gracefully
                    graph_hints = []
                except RuntimeError:
                    # No event loop running - create one
                    graph_hints = asyncio.run(
                        fetch_graph_hints(task, str(self.project_dir))
                    )
            except Exception:
                # Graphiti is optional - fail gracefully
                graph_hints = []

        # Add enhanced analysis data (optional)
        codebase_graph_summary = None
        architecture_patterns = None
        service_boundaries = None
        file_dependencies = None

        if include_enhanced_analysis:
            files_to_modify_dict = [
                asdict(f) if isinstance(f, FileMatch) else f for f in files_to_modify
            ]
            (
                codebase_graph_summary,
                architecture_patterns,
                service_boundaries,
                file_dependencies,
            ) = self._add_enhanced_analysis(task, files_to_modify_dict, spec_dir)

        return TaskContext(
            task_description=task,
            scoped_services=services,
            files_to_modify=[
                asdict(f) if isinstance(f, FileMatch) else f for f in files_to_modify
            ],
            files_to_reference=[
                asdict(f) if isinstance(f, FileMatch) else f for f in files_to_reference
            ],
            patterns_discovered=patterns,
            service_contexts=service_contexts,
            graph_hints=graph_hints,
            codebase_graph_summary=codebase_graph_summary,
            architecture_patterns=architecture_patterns,
            service_boundaries=service_boundaries,
            file_dependencies=file_dependencies,
        )

    async def build_context_async(
        self,
        task: str,
        services: list[str] | None = None,
        keywords: list[str] | None = None,
        include_graph_hints: bool = True,
        spec_dir: Path | None = None,
        include_enhanced_analysis: bool = True,
    ) -> TaskContext:
        """
        Build context for a specific task (async version).

        This version is preferred when called from async code as it can
        properly await the graph hints retrieval.

        Args:
            task: Description of the task
            services: List of service names to search (None = auto-detect)
            keywords: Additional keywords to search for
            include_graph_hints: Whether to include historical hints from Graphiti
            spec_dir: Optional spec directory for enhanced analysis caching
            include_enhanced_analysis: Whether to include enhanced analysis data

        Returns:
            TaskContext with relevant files and patterns
        """
        # Auto-detect services if not specified
        if not services:
            services = self.service_matcher.suggest_services(task)

        # Extract keywords from task if not provided
        if not keywords:
            keywords = self.keyword_extractor.extract_keywords(task)

        # Search each service
        all_matches: list[FileMatch] = []
        service_contexts = {}

        for service_name in services:
            service_info = self.project_index.get("services", {}).get(service_name)
            if not service_info:
                continue

            service_path = Path(service_info.get("path", service_name))
            if not service_path.is_absolute():
                service_path = self.project_dir / service_path

            # Search this service
            matches = self.searcher.search_service(service_path, service_name, keywords)
            all_matches.extend(matches)

            # Load or generate service context
            service_contexts[service_name] = self._get_service_context(
                service_path, service_name, service_info
            )

        # Categorize matches
        files_to_modify, files_to_reference = self.categorizer.categorize_matches(
            all_matches, task
        )

        # Discover patterns from reference files
        patterns = self.pattern_discoverer.discover_patterns(
            files_to_reference, keywords
        )

        # Get graph hints asynchronously
        graph_hints = []
        if include_graph_hints:
            graph_hints = await fetch_graph_hints(task, str(self.project_dir))

        # Add enhanced analysis data (optional)
        codebase_graph_summary = None
        architecture_patterns = None
        service_boundaries = None
        file_dependencies = None

        if include_enhanced_analysis:
            files_to_modify_dict = [
                asdict(f) if isinstance(f, FileMatch) else f for f in files_to_modify
            ]
            (
                codebase_graph_summary,
                architecture_patterns,
                service_boundaries,
                file_dependencies,
            ) = self._add_enhanced_analysis(task, files_to_modify_dict, spec_dir)

        return TaskContext(
            task_description=task,
            scoped_services=services,
            files_to_modify=[
                asdict(f) if isinstance(f, FileMatch) else f for f in files_to_modify
            ],
            files_to_reference=[
                asdict(f) if isinstance(f, FileMatch) else f for f in files_to_reference
            ],
            patterns_discovered=patterns,
            service_contexts=service_contexts,
            graph_hints=graph_hints,
            codebase_graph_summary=codebase_graph_summary,
            architecture_patterns=architecture_patterns,
            service_boundaries=service_boundaries,
            file_dependencies=file_dependencies,
        )

    def _get_service_context(
        self,
        service_path: Path,
        service_name: str,
        service_info: dict,
    ) -> dict:
        """Get or generate context for a service."""
        # Check for SERVICE_CONTEXT.md
        context_file = service_path / "SERVICE_CONTEXT.md"
        if context_file.exists():
            return {
                "source": "SERVICE_CONTEXT.md",
                "content": context_file.read_text()[:2000],  # First 2000 chars
            }

        # Generate basic context from service info
        return {
            "source": "generated",
            "language": service_info.get("language"),
            "framework": service_info.get("framework"),
            "type": service_info.get("type"),
            "entry_point": service_info.get("entry_point"),
            "key_directories": service_info.get("key_directories", {}),
        }
