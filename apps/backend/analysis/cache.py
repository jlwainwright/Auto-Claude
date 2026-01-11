"""
Analysis Cache System
=====================

Caching layer for enhanced project analysis results.
Stores analysis results with hash-based invalidation and partial update support.
"""

import hashlib
import json
from datetime import datetime
from pathlib import Path

from .models.analysis_result import EnhancedAnalysisResult


class AnalysisCache:
    """
    Cache manager for enhanced analysis results.

    Features:
    1. Stores EnhancedAnalysisResult as JSON in .auto-claude-analysis.json
    2. Computes file hashes for change detection
    3. Supports partial invalidation (only re-analyze changed files)
    4. Tracks per-file modification times
    """

    CACHE_FILENAME = ".auto-claude-analysis.json"

    def __init__(self, project_dir: Path, spec_dir: Path | None = None):
        """
        Initialize cache manager.

        Args:
            project_dir: Root directory of the project
            spec_dir: Optional spec directory for storing cache
        """
        self.project_dir = Path(project_dir).resolve()
        self.spec_dir = Path(spec_dir).resolve() if spec_dir else None

    def get_cache_path(self) -> Path:
        """Get the path where cache should be stored."""
        if self.spec_dir:
            return self.spec_dir / self.CACHE_FILENAME
        return self.project_dir / self.CACHE_FILENAME

    def load_cache(self) -> EnhancedAnalysisResult | None:
        """Load cached analysis result if it exists."""
        cache_path = self.get_cache_path()
        if not cache_path.exists():
            return None

        try:
            with open(cache_path) as f:
                data = json.load(f)
            return EnhancedAnalysisResult.from_dict(data)
        except (OSError, json.JSONDecodeError, KeyError):
            return None

    def save_cache(self, result: EnhancedAnalysisResult) -> None:
        """Save analysis result to cache."""
        cache_path = self.get_cache_path()
        cache_path.parent.mkdir(parents=True, exist_ok=True)

        # Update metadata
        result.is_cached = True
        result.cache_hit = False

        with open(cache_path, "w") as f:
            json.dump(result.to_dict(), f, indent=2)

    def compute_project_hash(self) -> str:
        """
        Compute a hash of key project files to detect changes.

        This reuses the pattern from ProjectAnalyzer.compute_project_hash.
        """
        hash_files = [
            # JavaScript/TypeScript
            "package.json",
            "package-lock.json",
            "yarn.lock",
            "pnpm-lock.yaml",
            # Python
            "pyproject.toml",
            "requirements.txt",
            "Pipfile",
            "poetry.lock",
            # Rust
            "Cargo.toml",
            "Cargo.lock",
            # Go
            "go.mod",
            "go.sum",
            # Ruby
            "Gemfile",
            "Gemfile.lock",
            # PHP
            "composer.json",
            "composer.lock",
            # Dart/Flutter
            "pubspec.yaml",
            "pubspec.lock",
            # Java/Kotlin/Scala
            "pom.xml",
            "build.gradle",
            "build.gradle.kts",
            "settings.gradle",
            "settings.gradle.kts",
            "build.sbt",
            # Swift
            "Package.swift",
            # Infrastructure
            "Makefile",
            "Dockerfile",
            "docker-compose.yml",
            "docker-compose.yaml",
        ]

        # Glob patterns for project files that can be anywhere in the tree
        glob_patterns = [
            "*.csproj",  # C# projects
            "*.sln",  # Visual Studio solutions
            "*.fsproj",  # F# projects
            "*.vbproj",  # VB.NET projects
        ]

        hasher = hashlib.md5(usedforsecurity=False)
        files_found = 0

        for filename in hash_files:
            filepath = self.project_dir / filename
            if filepath.exists():
                try:
                    stat = filepath.stat()
                    hasher.update(f"{filename}:{stat.st_mtime}:{stat.st_size}".encode())
                    files_found += 1
                except OSError:
                    continue

        # Check glob patterns for project files that can be anywhere
        for pattern in glob_patterns:
            for filepath in self.project_dir.glob(f"**/{pattern}"):
                try:
                    stat = filepath.stat()
                    rel_path = filepath.relative_to(self.project_dir)
                    hasher.update(f"{rel_path}:{stat.st_mtime}:{stat.st_size}".encode())
                    files_found += 1
                except OSError:
                    continue

        # If no config files found, hash the project directory structure
        if files_found == 0:
            source_exts = [
                "*.py",
                "*.js",
                "*.ts",
                "*.go",
                "*.rs",
                "*.dart",
                "*.cs",
                "*.swift",
                "*.kt",
                "*.java",
            ]
            for ext in source_exts:
                count = len(list(self.project_dir.glob(f"**/{ext}")))
                hasher.update(f"{ext}:{count}".encode())
            hasher.update(self.project_dir.name.encode())

        return hasher.hexdigest()

    def get_file_modification_times(self, file_paths: list[Path]) -> dict[str, float]:
        """
        Get modification times for a list of files.

        Args:
            file_paths: List of file paths to check

        Returns:
            Dict mapping file paths (as strings) to modification timestamps
        """
        mod_times = {}
        for file_path in file_paths:
            try:
                stat = file_path.stat()
                mod_times[str(file_path)] = stat.st_mtime
            except OSError:
                continue
        return mod_times

    def compute_file_hash(self, file_path: Path) -> str:
        """
        Compute hash for a single file.

        Args:
            file_path: Path to the file

        Returns:
            Hex digest of file hash
        """
        if not file_path.exists():
            return ""

        try:
            hasher = hashlib.md5(usedforsecurity=False)
            stat = file_path.stat()
            hasher.update(f"{file_path}:{stat.st_mtime}:{stat.st_size}".encode())
            return hasher.hexdigest()
        except OSError:
            return ""

    def should_invalidate(self, cached_result: EnhancedAnalysisResult) -> bool:
        """
        Check if cache should be invalidated based on project changes.

        Args:
            cached_result: Previously cached analysis result

        Returns:
            True if cache should be invalidated
        """
        current_hash = self.compute_project_hash()

        # If project hash changed, invalidate cache
        if current_hash != cached_result.project_hash:
            return True

        # Check if analysis is stale (older than 24 hours by default)
        if cached_result.is_stale(max_age_hours=24.0):
            return True

        return False

    def get_changed_files(
        self, cached_result: EnhancedAnalysisResult, current_files: list[Path]
    ) -> list[Path]:
        """
        Identify which files have changed since last analysis.

        This supports partial invalidation by only re-analyzing changed files.

        Args:
            cached_result: Previously cached analysis result
            current_files: Current list of files in the project

        Returns:
            List of files that have changed (added, modified, or deleted)
        """
        changed_files = []

        # Get current modification times
        current_mod_times = self.get_file_modification_times(current_files)

        # Extract cached modification times if available
        cached_mod_times = {}
        if hasattr(cached_result, "file_modification_times"):
            cached_mod_times = cached_result.file_modification_times or {}

        # Check for modified files
        for file_path_str, mod_time in current_mod_times.items():
            if file_path_str in cached_mod_times:
                # File exists in both, check if modified
                if mod_time != cached_mod_times[file_path_str]:
                    changed_files.append(Path(file_path_str))
            else:
                # New file
                changed_files.append(Path(file_path_str))

        # Check for deleted files (files in cache but not in current)
        cached_file_set = set(cached_mod_times.keys())
        current_file_set = set(current_mod_times.keys())
        deleted_files = cached_file_set - current_file_set

        for file_path_str in deleted_files:
            changed_files.append(Path(file_path_str))

        return changed_files

    def is_cache_hit(self, cached_result: EnhancedAnalysisResult | None) -> bool:
        """
        Check if cache can be used (valid and not stale).

        Args:
            cached_result: Previously cached analysis result

        Returns:
            True if cache is valid and can be used
        """
        if not cached_result:
            return False

        return not self.should_invalidate(cached_result)

    def update_cache_metadata(
        self, result: EnhancedAnalysisResult, file_paths: list[Path]
    ) -> None:
        """
        Update cache metadata with current file information.

        Args:
            result: Analysis result to update
            file_paths: List of analyzed files
        """
        # Store file modification times for partial invalidation
        result.file_modification_times = self.get_file_modification_times(file_paths)

        # Update project hash
        result.project_hash = self.compute_project_hash()

        # Update timestamp
        result.analysis_timestamp = datetime.now().isoformat()
