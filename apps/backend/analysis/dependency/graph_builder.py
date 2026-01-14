"""
Dependency Graph Builder
========================

Main orchestrator for building codebase dependency graphs.
Detects file types, delegates to appropriate parsers, resolves imports,
and builds FileNode and DependencyEdge objects into a complete CodebaseGraph.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from ..models.graph_models import CodebaseGraph, DependencyEdge, DependencyType, FileNode, GraphMetrics
from .js_parser import JSDependencyParser
from .python_parser import PythonDependencyParser


class DependencyGraphBuilder:
    """Builds codebase dependency graphs from source files."""

    # File extensions by language
    PYTHON_EXTENSIONS = {".py"}
    JS_EXTENSIONS = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}

    # Directories to skip
    SKIP_DIRS = {
        "__pycache__",
        "node_modules",
        ".git",
        ".venv",
        "venv",
        "env",
        "dist",
        "build",
        ".next",
        ".nuxt",
        "target",
        "bin",
        "obj",
    }

    # Files to skip
    SKIP_PATTERNS = {
        "*.pyc",
        "*.pyo",
        "*.pyd",
        "*.so",
        "*.dylib",
        "*.dll",
        "*.exe",
        "*.min.js",
        "*.min.css",
        "*.map",
    }

    # Cache filename
    CACHE_FILENAME = ".auto-claude-graph.json"

    def __init__(self, project_root: Path | str, spec_dir: Path | None = None):
        """
        Initialize the graph builder.

        Args:
            project_root: Root directory of the project to analyze.
            spec_dir: Optional spec directory for storing cache.
        """
        self.project_root = Path(project_root).resolve()
        self.spec_dir = Path(spec_dir).resolve() if spec_dir else None
        self.python_parser = PythonDependencyParser(self.project_root)
        self.js_parser = JSDependencyParser(self.project_root)

        # Cache for discovered local modules
        self._local_modules: set[str] | None = None

    def build(self, files: list[Path] | None = None) -> CodebaseGraph:
        """
        Build a complete dependency graph for the project.

        Args:
            files: Optional list of specific files to analyze.
                   If None, all supported files in the project will be analyzed.

        Returns:
            Complete CodebaseGraph with nodes, edges, and metrics.
        """
        # Discover files to analyze
        if files is None:
            files = self._discover_files()

        # Build nodes (FileNodes)
        nodes = self._build_nodes(files)

        # Build edges (DependencyEdges)
        edges = self._build_edges(nodes)

        # Detect circular dependencies
        self._detect_circular_dependencies(edges)

        # Build complete graph
        graph = CodebaseGraph(
            nodes=nodes,
            edges=edges,
            metrics=self._calculate_metrics(nodes, edges),
            project_dir=str(self.project_root),
        )

        return graph

    def _discover_files(self) -> list[Path]:
        """
        Discover all supported source files in the project.

        Returns:
            List of file paths to analyze.
        """
        files = []
        all_extensions = self.PYTHON_EXTENSIONS | self.JS_EXTENSIONS

        for file_path in self.project_root.rglob("*"):
            # Skip directories
            if not file_path.is_file():
                continue

            # Skip if in skipped directory
            if any(skip_dir in file_path.parts for skip_dir in self.SKIP_DIRS):
                continue

            # Check file extension
            if file_path.suffix in all_extensions:
                files.append(file_path)

        return files

    def _build_nodes(self, files: list[Path]) -> list[FileNode]:
        """
        Build FileNode objects from source files.

        Args:
            files: List of file paths to analyze.

        Returns:
            List of FileNode objects.
        """
        nodes = []

        for file_path in files:
            # Determine language and file type
            language = self._detect_language(file_path)
            file_type = self._detect_file_type(file_path)

            # Get file metadata
            try:
                stat = file_path.stat()
                line_count = self._count_lines(file_path)
                file_hash = self._hash_file(file_path)
            except OSError:
                # Skip files that can't be read
                continue

            # Create node
            node = FileNode(
                file_path=str(file_path),
                file_type=file_type,
                language=language,
                relative_path=str(file_path.relative_to(self.project_root)),
                imports=[],
                exports=[],
                is_entry_point=self._is_entry_point(file_path),
                is_test_file=self._is_test_file(file_path),
                is_config_file=self._is_config_file(file_path),
                line_count=line_count,
                function_count=0,  # Could be enhanced with AST analysis
                class_count=0,  # Could be enhanced with AST analysis
                complexity_score=0.0,  # Could be enhanced with complexity analysis
                last_modified=str(stat.st_mtime),
                hash=file_hash,
            )

            nodes.append(node)

        return nodes

    def _build_edges(self, nodes: list[FileNode]) -> list[DependencyEdge]:
        """
        Build DependencyEdge objects by parsing each file.

        Args:
            nodes: List of FileNode objects.

        Returns:
            List of DependencyEdge objects.
        """
        edges = []
        node_by_path: dict[str, FileNode] = {node.file_path: node for node in nodes}

        # Get local modules once
        if self._local_modules is None:
            self._local_modules = self._get_local_modules()

        for node in nodes:
            file_path = Path(node.file_path)
            language = node.language

            # Parse based on language
            if language == "Python":
                edges.extend(self._build_python_edges(file_path, node, node_by_path))
            elif language in ["JavaScript", "TypeScript"]:
                edges.extend(self._build_js_edges(file_path, node, node_by_path))

        return edges

    def _build_python_edges(
        self,
        file_path: Path,
        source_node: FileNode,
        node_by_path: dict[str, FileNode],
    ) -> list[DependencyEdge]:
        """Build dependency edges for a Python file."""
        edges = []
        imports = self.python_parser.parse_file(file_path)

        # Update node's imports list
        source_node.imports = [imp.module for imp in imports]

        for imp in imports:
            # Resolve import to file path
            target_path = self.python_parser.resolve_import_path(imp, file_path)

            if target_path and str(target_path) in node_by_path:
                target_node = node_by_path[str(target_path)]

                # Determine dependency type
                dep_type = DependencyType.IMPORT.value
                if imp.import_type == "relative":
                    dep_type = DependencyType.IMPORT.value

                # Create edge
                edge = DependencyEdge(
                    from_file=source_node.file_path,
                    to_file=target_node.file_path,
                    dependency_type=dep_type,
                    imported_symbols=[imp.module],
                    line_numbers=[imp.line_number],
                    strength=1.0,
                    is_circular=False,  # Will be detected later
                    is_runtime=True,
                    is_development=False,
                )

                edges.append(edge)

        return edges

    def _build_js_edges(
        self,
        file_path: Path,
        source_node: FileNode,
        node_by_path: dict[str, FileNode],
    ) -> list[DependencyEdge]:
        """Build dependency edges for a JS/TS file."""
        edges = []
        result = self.js_parser.parse_file(file_path)

        # Update node's imports and exports
        imports_data = result.get("imports", [])
        exports_data = result.get("exports", [])

        source_node.imports = [imp["module"] for imp in imports_data]
        source_node.exports = [exp["name"] for exp in exports_data]

        for imp in imports_data:
            # Convert to JSImportInfo-like dict for resolver
            imp_info = {
                "module": imp["module"],
                "import_type": imp.get("import_type", "es6"),
                "is_dynamic": imp.get("is_dynamic", False),
                "specifiers": imp.get("specifiers", []),
                "line_number": imp.get("line_number", 0),
            }

            # Resolve import to file path
            target_path = self.js_parser.resolve_import_path(imp_info, file_path)

            if target_path and str(target_path) in node_by_path:
                target_node = node_by_path[str(target_path)]

                # Determine dependency type
                dep_type = DependencyType.IMPORT.value
                if imp.get("is_dynamic"):
                    dep_type = DependencyType.DYNAMIC_IMPORT.value
                elif imp.get("import_type") == "commonjs":
                    dep_type = DependencyType.REQUIRE_CALL.value

                # Extract imported symbols
                symbols = [imp["module"]]
                for spec in imp.get("specifiers", []):
                    symbols.append(spec.get("name", ""))

                # Create edge
                edge = DependencyEdge(
                    from_file=source_node.file_path,
                    to_file=target_node.file_path,
                    dependency_type=dep_type,
                    imported_symbols=symbols,
                    line_numbers=[imp.get("line_number", 0)],
                    strength=1.0,
                    is_circular=False,  # Will be detected later
                    is_runtime=True,
                    is_development=False,
                )

                edges.append(edge)

        return edges

    def _detect_circular_dependencies(self, edges: list[DependencyEdge]) -> None:
        """
        Detect circular dependencies using DFS.

        Modifies edges in-place to mark circular dependencies.

        Args:
            edges: List of DependencyEdge objects to analyze.
        """
        # Build adjacency list
        graph: dict[str, set[str]] = {}
        for edge in edges:
            if edge.from_file not in graph:
                graph[edge.from_file] = set()
            graph[edge.from_file].add(edge.to_file)

        # Detect cycles using DFS
        visited: set[str] = set()
        rec_stack: set[str] = set()
        cycles: set[tuple[str, str]] = set()

        def dfs(node: str, path: list[str]) -> None:
            """DFS to detect cycles."""
            visited.add(node)
            rec_stack.add(node)

            for neighbor in graph.get(node, set()):
                if neighbor not in visited:
                    dfs(neighbor, path + [node])
                elif neighbor in rec_stack:
                    # Found a cycle
                    cycle_start = path.index(neighbor)
                    cycle_path = path[cycle_start:] + [node, neighbor]
                    # Mark all edges in the cycle
                    for i in range(len(cycle_path) - 1):
                        cycles.add((cycle_path[i], cycle_path[i + 1]))

            rec_stack.remove(node)

        for node in graph:
            if node not in visited:
                dfs(node, [])

        # Mark edges as circular
        for edge in edges:
            if (edge.from_file, edge.to_file) in cycles:
                edge.is_circular = True

    def _calculate_metrics(self, nodes: list[FileNode], edges: list[DependencyEdge]) -> GraphMetrics:
        """
        Calculate graph metrics.

        Args:
            nodes: List of FileNode objects.
            edges: List of DependencyEdge objects.

        Returns:
            GraphMetrics object with calculated metrics.
        """
        # Basic counts
        total_files = len(nodes)
        total_dependencies = len(edges)

        # Count circular dependencies
        circular_deps = sum(1 for edge in edges if edge.is_circular)

        # Find orphan files (no incoming or outgoing edges)
        files_with_edges = set()
        for edge in edges:
            files_with_edges.add(edge.from_file)
            files_with_edges.add(edge.to_file)
        orphan_files = total_files - len(files_with_edges)

        # Calculate coupling
        coupling_by_file: dict[str, int] = {}
        for node in nodes:
            outgoing = sum(1 for edge in edges if edge.from_file == node.file_path)
            incoming = sum(1 for edge in edges if edge.to_file == node.file_path)
            coupling_by_file[node.file_path] = outgoing + incoming

        avg_coupling = (
            sum(coupling_by_file.values()) / len(coupling_by_file) if coupling_by_file else 0.0
        )

        # Find highly coupled files (top 20%)
        if coupling_by_file:
            threshold = sorted(coupling_by_file.values())[int(len(coupling_by_file) * 0.8)] if len(coupling_by_file) > 1 else 0
            critical_files = [
                file_path
                for file_path, coupling in coupling_by_file.items()
                if coupling >= threshold and coupling > 0
            ]
        else:
            critical_files = []

        # Language distribution
        language_dist: dict[str, int] = {}
        for node in nodes:
            language_dist[node.language] = language_dist.get(node.language, 0) + 1

        return GraphMetrics(
            total_files=total_files,
            total_dependencies=total_dependencies,
            total_functions=sum(node.function_count for node in nodes),
            total_classes=sum(node.class_count for node in nodes),
            average_complexity=sum(node.complexity_score for node in nodes) / len(nodes) if nodes else 0.0,
            max_complexity=max((node.complexity_score for node in nodes), default=0.0),
            circular_dependencies=circular_deps,
            orphan_files=orphan_files,
            average_coupling=avg_coupling,
            highly_coupled_files=len(critical_files),
            critical_files=critical_files,
            language_distribution=language_dist,
        )

    def _detect_language(self, file_path: Path) -> str:
        """Detect the programming language of a file."""
        suffix = file_path.suffix

        if suffix in self.PYTHON_EXTENSIONS:
            return "Python"
        elif suffix in {".ts", ".tsx"}:
            return "TypeScript"
        elif suffix in {".js", ".jsx", ".mjs", ".cjs"}:
            return "JavaScript"

        return "Unknown"

    def _detect_file_type(self, file_path: Path) -> str:
        """Detect the type of file (source, test, config, etc.)."""
        if self._is_test_file(file_path):
            return "test"
        elif self._is_config_file(file_path):
            return "config"
        elif self._is_entry_point(file_path):
            return "entry_point"
        else:
            return "source"

    def _is_entry_point(self, file_path: Path) -> bool:
        """Check if file is a main entry point."""
        name = file_path.name
        return name in {
            "main.py",
            "app.py",
            "__main__.py",
            "index.js",
            "index.ts",
            "main.js",
            "main.ts",
            "server.js",
            "server.ts",
        }

    def _is_test_file(self, file_path: Path) -> bool:
        """Check if file is a test file."""
        path_parts = file_path.parts
        name = file_path.name

        # Check if in test directory
        if "test" in path_parts or "tests" in path_parts or "__tests__" in path_parts:
            return True

        # Check if name starts/ends with test
        return name.startswith("test_") or name.startswith("test.") or name.endswith("_test.py") or name.endswith(".test.js") or name.endswith(".test.ts")

    def _is_config_file(self, file_path: Path) -> bool:
        """Check if file is a configuration file."""
        name = file_path.name
        return name in {
            "package.json",
            "tsconfig.json",
            "jsconfig.json",
            "setup.py",
            "pyproject.toml",
            "requirements.txt",
            "Dockerfile",
            "docker-compose.yml",
            ".gitignore",
            ".env.example",
        }

    def _count_lines(self, file_path: Path) -> int:
        """Count lines in a file."""
        try:
            return len(file_path.read_text(encoding="utf-8").splitlines())
        except (OSError, UnicodeDecodeError):
            return 0

    def _hash_file(self, file_path: Path) -> str:
        """Calculate hash of file contents for caching."""
        try:
            content = file_path.read_bytes()
            return hashlib.sha256(content).hexdigest()
        except OSError:
            return ""

    def _get_local_modules(self) -> set[str]:
        """Get all local module names in the project."""
        local_modules = set()

        # Python modules
        python_modules = self.python_parser.get_local_modules(self.project_root)
        local_modules.update(python_modules)

        # JS/TS modules (from package.json)
        js_modules = self.js_parser.get_local_modules(self.project_root)
        local_modules.update(js_modules)

        return local_modules

    def get_cache_path(self) -> Path:
        """Get the path where graph cache should be stored."""
        if self.spec_dir:
            return self.spec_dir / self.CACHE_FILENAME
        return self.project_root / self.CACHE_FILENAME

    def load_cached_graph(self) -> CodebaseGraph | None:
        """
        Load cached dependency graph if it exists.

        Returns:
            Cached CodebaseGraph or None if cache doesn't exist/invalid.
        """
        cache_path = self.get_cache_path()
        if not cache_path.exists():
            return None

        try:
            with open(cache_path) as f:
                data = json.load(f)
            return CodebaseGraph.from_dict(data)
        except (OSError, json.JSONDecodeError, KeyError):
            return None

    def save_graph(self, graph: CodebaseGraph) -> None:
        """
        Save dependency graph to cache.

        Args:
            graph: CodebaseGraph to save.
        """
        cache_path = self.get_cache_path()
        cache_path.parent.mkdir(parents=True, exist_ok=True)

        # Update metadata
        graph.analyzed_at = datetime.now().isoformat()
        graph.graph_hash = self._compute_graph_hash(graph)

        with open(cache_path, "w") as f:
            json.dump(graph.to_dict(), f, indent=2)

    def build_incremental(self, force: bool = False) -> CodebaseGraph:
        """
        Build dependency graph with incremental updates.

        Only re-parses files that have changed since last analysis.

        Args:
            force: Force full rebuild even if cache exists.

        Returns:
            Complete CodebaseGraph with updated nodes and edges.
        """
        # Try to load cached graph
        cached_graph = None if force else self.load_cached_graph()

        if cached_graph is None:
            # No cache or force rebuild - do full build
            return self.build()

        # Discover current files
        current_files = self._discover_files()

        # Detect changed files
        changed_files = self._get_changed_files(cached_graph, current_files)

        if not changed_files:
            # No changes - return cached graph
            return cached_graph

        # Build node lookup from cached graph
        cached_nodes_by_path: dict[str, FileNode] = {
            node.file_path: node for node in cached_graph.nodes
        }

        # Determine new files and deleted files
        current_file_paths = {str(f) for f in current_files}
        cached_file_paths = set(cached_nodes_by_path.keys())

        new_files = current_file_paths - cached_file_paths
        deleted_files = cached_file_paths - current_file_paths
        modified_files = set(str(f) for f in changed_files) - new_files

        # Start with cached graph
        nodes = list(cached_graph.nodes)
        edges = list(cached_graph.edges)

        # Handle deleted files
        if deleted_files:
            nodes, edges = self._handle_deleted_files(deleted_files, nodes, edges)

        # Handle new files
        if new_files:
            new_nodes, new_edges = self._handle_new_files(
                [Path(f) for f in new_files], nodes
            )
            nodes.extend(new_nodes)
            edges.extend(new_edges)

        # Handle modified files
        if modified_files:
            nodes, edges = self._handle_modified_files(
                [Path(f) for f in modified_files], nodes, edges
            )

        # Re-detect circular dependencies
        self._detect_circular_dependencies(edges)

        # Build complete graph
        graph = CodebaseGraph(
            nodes=nodes,
            edges=edges,
            metrics=self._calculate_metrics(nodes, edges),
            project_dir=str(self.project_root),
            architecture_pattern=cached_graph.architecture_pattern,
            service_boundaries=cached_graph.service_boundaries,
            analyzer_version=cached_graph.analyzer_version,
        )

        # Save updated graph
        self.save_graph(graph)

        return graph

    def _compute_graph_hash(self, graph: CodebaseGraph) -> str:
        """
        Compute hash of graph for change detection.

        Args:
            graph: CodebaseGraph to hash.

        Returns:
            Hex digest hash.
        """
        hasher = hashlib.md5(usedforsecurity=False)

        # Hash node file paths and their hashes
        for node in sorted(graph.nodes, key=lambda n: n.file_path):
            hasher.update(f"{node.file_path}:{node.hash}".encode())

        return hasher.hexdigest()

    def _get_changed_files(
        self, cached_graph: CodebaseGraph, current_files: list[Path]
    ) -> list[Path]:
        """
        Identify files that have changed since last analysis.

        Args:
            cached_graph: Previously cached graph.
            current_files: Current list of files in the project.

        Returns:
            List of files that have changed (new or modified).
        """
        changed_files = []
        cached_nodes_by_path: dict[str, FileNode] = {
            node.file_path: node for node in cached_graph.nodes
        }

        for file_path in current_files:
            file_path_str = str(file_path)

            # Check if file is new
            if file_path_str not in cached_nodes_by_path:
                changed_files.append(file_path)
                continue

            # Check if file has been modified by comparing hashes
            current_hash = self._hash_file(file_path)
            cached_node = cached_nodes_by_path[file_path_str]

            if current_hash != cached_node.hash:
                changed_files.append(file_path)

        return changed_files

    def _handle_deleted_files(
        self, deleted_files: set[str], nodes: list[FileNode], edges: list[DependencyEdge]
    ) -> tuple[list[FileNode], list[DependencyEdge]]:
        """
        Remove nodes and edges for deleted files.

        Args:
            deleted_files: Set of deleted file paths.
            nodes: Current list of nodes.
            edges: Current list of edges.

        Returns:
            Tuple of updated (nodes, edges).
        """
        # Remove nodes for deleted files
        nodes = [node for node in nodes if node.file_path not in deleted_files]

        # Remove edges involving deleted files
        edges = [
            edge
            for edge in edges
            if edge.from_file not in deleted_files and edge.to_file not in deleted_files
        ]

        return nodes, edges

    def _handle_new_files(
        self, new_files: list[Path], existing_nodes: list[FileNode]
    ) -> tuple[list[FileNode], list[DependencyEdge]]:
        """
        Add nodes and edges for new files.

        Args:
            new_files: List of new file paths.
            existing_nodes: Current list of nodes (for edge resolution).

        Returns:
            Tuple of (new_nodes, new_edges).
        """
        # Build nodes for new files
        new_nodes = self._build_nodes(new_files)

        # Build edges for new files
        all_nodes = existing_nodes + new_nodes
        new_edges = []
        node_by_path: dict[str, FileNode] = {node.file_path: node for node in all_nodes}

        # Get local modules once
        if self._local_modules is None:
            self._local_modules = self._get_local_modules()

        for node in new_nodes:
            file_path = Path(node.file_path)
            language = node.language

            # Parse based on language
            if language == "Python":
                new_edges.extend(self._build_python_edges(file_path, node, node_by_path))
            elif language in ["JavaScript", "TypeScript"]:
                new_edges.extend(self._build_js_edges(file_path, node, node_by_path))

        return new_nodes, new_edges

    def _handle_modified_files(
        self, modified_files: list[Path], nodes: list[FileNode], edges: list[DependencyEdge]
    ) -> tuple[list[FileNode], list[DependencyEdge]]:
        """
        Update nodes and edges for modified files.

        Args:
            modified_files: List of modified file paths.
            nodes: Current list of nodes.
            edges: Current list of edges.

        Returns:
            Tuple of updated (nodes, edges).
        """
        # Build node lookup
        node_by_path: dict[str, FileNode] = {node.file_path: node for node in nodes}

        for file_path in modified_files:
            file_path_str = str(file_path)

            # Remove old edges for this file
            edges = [edge for edge in edges if edge.from_file != file_path_str]

            # Update the node
            if file_path_str in node_by_path:
                node = node_by_path[file_path_str]
                self._update_node(node, file_path)

                # Build new edges for this file
                language = node.language

                if language == "Python":
                    new_edges = self._build_python_edges(file_path, node, node_by_path)
                    edges.extend(new_edges)
                elif language in ["JavaScript", "TypeScript"]:
                    new_edges = self._build_js_edges(file_path, node, node_by_path)
                    edges.extend(new_edges)

        return nodes, edges

    def _update_node(self, node: FileNode, file_path: Path) -> None:
        """
        Update a FileNode with current file data.

        Args:
            node: FileNode to update.
            file_path: Current file path.
        """
        # Get file metadata
        try:
            stat = file_path.stat()
            node.line_count = self._count_lines(file_path)
            node.hash = self._hash_file(file_path)
            node.last_modified = str(stat.st_mtime)
        except OSError:
            # Skip files that can't be read
            return

        # Clear and reset imports/exports
        node.imports = []
        node.exports = []
