"""
Python Dependency Parser
========================

Extracts and analyzes imports from Python source files using AST parsing.
Categorizes imports as standard library, third-party, or local dependencies.
Builds cross-file dependency relationships.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import Any


# Python standard library modules (Python 3.12)
STANDARD_LIBRARY = {
    # Common modules
    "abc", "aifc", "argparse", "array", "ast", "asynchat", "asyncio", "asyncore",
    "atexit", "audioop", "base64", "bdb", "binascii", "binhex", "bisect", "builtins",
    "bz2", "calendar", "cgi", "cgitb", "chunk", "cmath", "cmd", "code", "codecs",
    "codeop", "collections", "colorsys", "compileall", "concurrent", "configparser",
    "contextlib", "contextvars", "copy", "copyreg", "cProfile", "crypt", "csv",
    "ctypes", "curses", "dataclasses", "datetime", "dbm", "decimal", "difflib",
    "dis", "distutils", "doctest", "email", "encodings", "enum", "errno", "faulthandler",
    "fcntl", "filecmp", "fileinput", "fnmatch", "formatter", "fractions", "ftplib",
    "functools", "gc", "getopt", "getpass", "gettext", "glob", "graphlib", "grp",
    "gzip", "hashlib", "heapq", "hmac", "html", "http", "imaplib", "imghdr", "imp",
    "importlib", "inspect", "io", "ipaddress", "itertools", "json", "keyword",
    "lib2to3", "linecache", "locale", "logging", "lzma", "mailbox", "mailcap",
    "marshal", "math", "mimetypes", "mmap", "modulefinder", "msilib", "msvcrt",
    "multiprocessing", "netrc", "nis", "nntplib", "numbers", "operator", "optparse",
    "os", "ossaudiodev", "pathlib", "pdb", "pickle", "pickletools", "pipes", "pkgutil",
    "platform", "plistlib", "poplib", "posix", "posixpath", "pprint", "profile",
    "pstats", "pty", "pwd", "py_compile", "pyclbr", "pydoc", "queue", "quopri",
    "random", "re", "readline", "reprlib", "resource", "rlcompleter", "runpy",
    "sched", "secrets", "select", "selectors", "shelve", "shlex", "shutil", "signal",
    "site", "smtpd", "smtplib", "sndhdr", "socket", "socketserver", "spwd", "sqlite3",
    "ssl", "stat", "statistics", "string", "stringprep", "struct", "subprocess",
    "sunau", "symbol", "symtable", "sys", "sysconfig", "syslog", "tabnanny", "tarfile",
    "telnetlib", "tempfile", "termios", "test", "textwrap", "threading", "time",
    "timeit", "tkinter", "token", "tokenize", "tomllib", "trace", "traceback",
    "tracemalloc", "tty", "turtle", "turtledemo", "types", "typing", "typing_extensions",
    "unicodedata", "unittest", "urllib", "uu", "uuid", "venv", "warnings", "wave",
    "weakref", "webbrowser", "winreg", "winsound", "wsgiref", "xdrlib", "xml",
    "xmlrpc", "zipapp", "zipfile", "zipimport", "zlib",
    # Common stdlib submodules
    "collections.abc", "concurrent.futures", "contextvars", "email.mime",
    "email.mime.multipart", "email.mime.text", "encodings.utf_8",
    "importlib.metadata", "importlib.resources", "pathlib", "typing_extensions",
    "urllib.parse", "urllib.request", "urllib.error", "xml.etree", "xml.etree.ElementTree",
}


class ImportInfo:
    """Represents a single import statement."""

    def __init__(
        self,
        module: str,
        alias: str | None = None,
        import_type: str = "absolute",
        level: int = 0,
        line_number: int = 0,
    ):
        self.module = module
        self.alias = alias
        self.import_type = import_type  # "absolute" or "relative"
        self.level = level  # For relative imports (0=absolute, 1=., 2=.., etc.)
        self.line_number = line_number

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "module": self.module,
            "alias": self.alias,
            "import_type": self.import_type,
            "level": self.level,
            "line_number": self.line_number,
        }


class DependencyRelation:
    """Represents a dependency relationship between files."""

    def __init__(
        self,
        source_file: Path,
        target_module: str,
        import_type: str = "unknown",
        is_standard_lib: bool = False,
        is_third_party: bool = False,
        is_local: bool = False,
    ):
        self.source_file = source_file
        self.target_module = target_module
        self.import_type = import_type
        self.is_standard_lib = is_standard_lib
        self.is_third_party = is_third_party
        self.is_local = is_local

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "source_file": str(self.source_file),
            "target_module": self.target_module,
            "import_type": self.import_type,
            "is_standard_lib": self.is_standard_lib,
            "is_third_party": self.is_third_party,
            "is_local": self.is_local,
        }


class PythonDependencyParser:
    """Parses Python files to extract imports and build dependency relationships."""

    def __init__(self, project_root: Path | None = None):
        """
        Initialize the parser.

        Args:
            project_root: Root directory of the project. Used to determine local imports.
        """
        self.project_root = Path(project_root).resolve() if project_root else None

    def parse_file(self, file_path: Path) -> list[ImportInfo]:
        """
        Parse a Python file and extract all imports.

        Args:
            file_path: Path to the Python file.

        Returns:
            List of ImportInfo objects representing all imports found.
        """
        try:
            content = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return []

        try:
            tree = ast.parse(content, filename=str(file_path))
        except SyntaxError:
            return []

        imports: list[ImportInfo] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                # Handle: import module [, module2]
                for alias in node.names:
                    imports.append(
                        ImportInfo(
                            module=alias.name,
                            alias=alias.asname,
                            import_type="absolute",
                            line_number=node.lineno,
                        )
                    )

            elif isinstance(node, ast.ImportFrom):
                # Handle: from module import name [, name2]
                # Handle: from . import module
                # Handle: from ..package import module

                module = node.module or ""
                level = node.level  # 0=absolute, 1=., 2=..

                # For relative imports, construct the relative path
                if level > 0:
                    import_type = "relative"
                    # The actual module being imported from
                    if module:
                        # from .module import name
                        full_module = "." * level + module
                    else:
                        # from . import name
                        full_module = "." * level + node.names[0].name if node.names else "." * level
                else:
                    import_type = "absolute"
                    full_module = module

                for alias in node.names:
                    imports.append(
                        ImportInfo(
                            module=full_module,
                            alias=alias.asname,
                            import_type=import_type,
                            level=level,
                            line_number=node.lineno,
                        )
                    )

        return imports

    def categorize_import(
        self,
        import_info: ImportInfo,
        source_file: Path,
        local_modules: set[str] | None = None,
    ) -> str:
        """
        Categorize an import as standard library, third-party, or local.

        Args:
            import_info: The import to categorize.
            source_file: The file containing the import (for resolving relative imports).
            local_modules: Set of known local module names.

        Returns:
            One of: "standard", "third_party", "local"
        """
        # Get the root module name (before first dot)
        module_parts = import_info.module.lstrip(".").split(".")
        root_module = module_parts[0] if module_parts else ""

        # Handle relative imports
        if import_info.import_type == "relative":
            return "local"

        # Check if it's a standard library module
        if root_module in STANDARD_LIBRARY:
            return "standard"

        # Check if it's a known local module
        if local_modules and root_module in local_modules:
            return "local"

        # Try to resolve the module to see if it's local
        if self._is_local_module(root_module, source_file):
            return "local"

        # Otherwise, it's third-party
        return "third_party"

    def _is_local_module(self, module_name: str, source_file: Path) -> bool:
        """
        Check if a module is local to the project.

        Args:
            module_name: Name of the module to check.
            source_file: The file importing the module.

        Returns:
            True if the module is local, False otherwise.
        """
        if not self.project_root:
            return False

        # Check if there's a directory or file with this module name
        # in the project root
        module_dir = self.project_root / module_name
        module_file = self.project_root / f"{module_name}.py"

        if module_dir.exists() or module_file.exists():
            return True

        # Check in the same directory as the source file
        source_dir = source_file.parent
        local_module_dir = source_dir / module_name
        local_module_file = source_dir / f"{module_name}.py"

        if local_module_dir.exists() or local_module_file.exists():
            return True

        return False

    def build_dependency_graph(
        self,
        files: list[Path],
        local_modules: set[str] | None = None,
    ) -> dict[str, list[DependencyRelation]]:
        """
        Build a dependency graph for multiple Python files.

        Args:
            files: List of Python files to analyze.
            local_modules: Set of known local module names.

        Returns:
            Dictionary mapping file paths to their dependency relations.
        """
        dependency_graph: dict[str, list[DependencyRelation]] = {}

        for file_path in files:
            imports = self.parse_file(file_path)
            relations: list[DependencyRelation] = []

            for import_info in imports:
                category = self.categorize_import(import_info, file_path, local_modules)

                relation = DependencyRelation(
                    source_file=file_path,
                    target_module=import_info.module,
                    import_type=import_info.import_type,
                    is_standard_lib=(category == "standard"),
                    is_third_party=(category == "third_party"),
                    is_local=(category == "local"),
                )
                relations.append(relation)

            dependency_graph[str(file_path)] = relations

        return dependency_graph

    def get_local_modules(self, project_root: Path) -> set[str]:
        """
        Scan the project to discover local module names.

        Args:
            project_root: Root directory of the project.

        Returns:
            Set of local module names.
        """
        local_modules = set()

        # Look for Python packages (directories with __init__.py)
        for item in project_root.iterdir():
            if item.is_dir() and not item.name.startswith("_"):
                if (item / "__init__.py").exists():
                    local_modules.add(item.name)

        # Look for standalone .py files
        for item in project_root.glob("*.py"):
            if not item.name.startswith("_"):
                local_modules.add(item.stem)

        return local_modules

    def resolve_import_path(
        self,
        import_info: ImportInfo,
        source_file: Path,
    ) -> Path | None:
        """
        Resolve an import to an actual file path.

        Args:
            import_info: The import to resolve.
            source_file: The file containing the import.

        Returns:
            Path to the imported module, or None if not found.
        """
        if not self.project_root:
            return None

        # Handle relative imports
        if import_info.import_type == "relative":
            module_name = import_info.module.lstrip(".")
            source_dir = source_file.parent

            # Go up the directory hierarchy based on level
            for _ in range(import_info.level - 1):
                if source_dir.parent != self.project_root:
                    source_dir = source_dir.parent

            # Try to find the module
            module_path = source_dir / module_name
            if module_path.is_dir() and (module_path / "__init__.py").exists():
                return module_path / "__init__.py"

            module_file = source_dir / f"{module_name}.py"
            if module_file.exists():
                return module_file

            return None

        # Handle absolute imports
        module_parts = import_info.module.split(".")
        root_module = module_parts[0]

        # Check project root
        module_dir = self.project_root / root_module
        if module_dir.is_dir() and (module_dir / "__init__.py").exists():
            # Navigate through submodules
            current_path = module_dir
            for part in module_parts[1:]:
                next_path = current_path / part
                if next_path.is_dir() and (next_path / "__init__.py").exists():
                    current_path = next_path
                else:
                    module_file = current_path / f"{part}.py"
                    if module_file.exists():
                        return module_file
                    return None
            return current_path / "__init__.py"

        # Check for single file module
        module_file = self.project_root / f"{root_module}.py"
        if module_file.exists():
            return module_file

        # Not a local module
        return None

    def analyze_dependencies(
        self,
        file_path: Path,
        local_modules: set[str] | None = None,
    ) -> dict[str, Any]:
        """
        Perform a comprehensive dependency analysis of a single file.

        Args:
            file_path: Path to the Python file.
            local_modules: Set of known local module names.

        Returns:
            Dictionary containing analysis results.
        """
        imports = self.parse_file(file_path)

        standard_libs = []
        third_parties = []
        local_imports = []

        for imp in imports:
            category = self.categorize_import(imp, file_path, local_modules)

            import_dict = imp.to_dict()
            import_dict["category"] = category

            if category == "standard":
                standard_libs.append(import_dict)
            elif category == "third_party":
                third_parties.append(import_dict)
            else:
                local_imports.append(import_dict)

        return {
            "file": str(file_path),
            "total_imports": len(imports),
            "standard_library": standard_libs,
            "third_party": third_parties,
            "local": local_imports,
            "imports": [imp.to_dict() for imp in imports],
        }
