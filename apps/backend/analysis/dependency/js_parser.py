"""
JS/TS Dependency Parser
========================

Extracts and analyzes imports from JavaScript and TypeScript source files.
Supports ES6 modules, CommonJS, and dynamic imports.
Handles path aliases from tsconfig.json and jsconfig.json.
Tracks named and default exports.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any


class JSImportInfo:
    """Represents a single import statement in JS/TS."""

    def __init__(
        self,
        module: str,
        import_type: str = "es6",
        is_dynamic: bool = False,
        specifiers: list[dict[str, Any]] | None = None,
        line_number: int = 0,
    ):
        self.module = module
        self.import_type = import_type  # "es6", "commonjs", "dynamic"
        self.is_dynamic = is_dynamic
        self.specifiers = specifiers or []
        self.line_number = line_number

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "module": self.module,
            "import_type": self.import_type,
            "is_dynamic": self.is_dynamic,
            "specifiers": self.specifiers,
            "line_number": self.line_number,
        }


class JSExportInfo:
    """Represents a single export statement in JS/TS."""

    def __init__(
        self,
        name: str,
        export_type: str = "named",
        is_default: bool = False,
        line_number: int = 0,
    ):
        self.name = name
        self.export_type = export_type  # "named", "default", "wildcard"
        self.is_default = is_default
        self.line_number = line_number

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "name": self.name,
            "export_type": self.export_type,
            "is_default": self.is_default,
            "line_number": self.line_number,
        }


class JSDependencyParser:
    """Parses JavaScript/TypeScript files to extract imports and exports."""

    def __init__(self, project_root: Path | None = None):
        """
        Initialize the parser.

        Args:
            project_root: Root directory of the project. Used to resolve path aliases.
        """
        self.project_root = Path(project_root).resolve() if project_root else None
        self._path_aliases: dict[str, str] = {}
        self._load_path_aliases()

    def _load_path_aliases(self) -> None:
        """Load path aliases from tsconfig.json or jsconfig.json."""
        if not self.project_root:
            return

        config_files = ["tsconfig.json", "jsconfig.json"]
        for config_file in config_files:
            config_path = self.project_root / config_file
            if config_path.exists():
                try:
                    content = config_path.read_text(encoding="utf-8")
                    config = json.loads(content)

                    # Get compilerOptions.paths
                    paths = config.get("compilerOptions", {}).get("paths", {})
                    if paths:
                        # Resolve path aliases
                        base_url = config.get("compilerOptions", {}).get("baseUrl", ".")
                        base_dir = self.project_root / base_url

                        for alias, targets in paths.items():
                            # Remove trailing /* from alias
                            alias_key = alias.rstrip("/*")
                            if targets:
                                # Use first target
                                target = targets[0].rstrip("/*")
                                self._path_aliases[alias_key] = str(base_dir / target)
                except (OSError, json.JSONDecodeError):
                    pass
                break

    def _resolve_path_alias(self, module_path: str) -> str:
        """
        Resolve a module path through path aliases.

        Args:
            module_path: The module path to resolve.

        Returns:
            Resolved module path, or original if no alias matches.
        """
        # Check for exact alias match
        if module_path in self._path_aliases:
            return self._path_aliases[module_path]

        # Check for prefix match (e.g., @/components -> src/components)
        for alias, target in self._path_aliases.items():
            if module_path.startswith(alias + "/"):
                return module_path.replace(alias, target, 1)

        return module_path

    def parse_file(self, file_path: Path) -> dict[str, Any]:
        """
        Parse a JS/TS file and extract all imports and exports.

        Args:
            file_path: Path to the JS/TS file.

        Returns:
            Dictionary with 'imports' and 'exports' lists.
        """
        try:
            content = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return {"imports": [], "exports": []}

        imports: list[JSImportInfo] = []
        exports: list[JSExportInfo] = []

        # Parse ES6 imports
        es6_imports = self._parse_es6_imports(content)
        imports.extend(es6_imports)

        # Parse CommonJS imports
        commonjs_imports = self._parse_commonjs_imports(content)
        imports.extend(commonjs_imports)

        # Parse dynamic imports
        dynamic_imports = self._parse_dynamic_imports(content)
        imports.extend(dynamic_imports)

        # Parse ES6 exports
        es6_exports = self._parse_es6_exports(content)
        exports.extend(es6_exports)

        # Parse CommonJS exports
        commonjs_exports = self._parse_commonjs_exports(content)
        exports.extend(commonjs_exports)

        return {"imports": [imp.to_dict() for imp in imports], "exports": [exp.to_dict() for exp in exports]}

    def _parse_es6_imports(self, content: str) -> list[JSImportInfo]:
        """
        Parse ES6 import statements.

        Supports:
        - import default from 'module'
        - import { named } from 'module'
        - import { named as alias } from 'module'
        - import * as namespace from 'module'
        - import default, { named } from 'module'
        """
        imports: list[JSImportInfo] = []

        # ES6 import patterns
        patterns = [
            # Default import: import React from 'react'
            r"import\s+([\w$]+)\s+from\s+['\"]([^'\"]+)['\"]",
            # Named imports: import { Button } from 'module'
            r"import\s+\{\s*([^}]+)\s*\}\s+from\s+['\"]([^'\"]+)['\"]",
            # Namespace import: import * as utils from 'module'
            r"import\s+\*\s+as\s+([\w$]+)\s+from\s+['\"]([^'\"]+)['\"]",
            # Combined: import React, { useState } from 'react'
            r"import\s+([\w$]+),\s*\{\s*([^}]+)\s*\}\s+from\s+['\"]([^'\"]+)['\"]",
            # Side-effect: import 'module'
            r"^import\s+['\"]([^'\"]+)['\"]",
        ]

        for line_num, line in enumerate(content.split("\n"), 1):
            line = line.strip()

            # Skip comments
            if line.startswith("//") or line.startswith("/*"):
                continue

            for pattern in patterns:
                match = re.search(pattern, line)
                if match:
                    module = match.group(2) if len(match.groups()) > 1 else match.group(1)
                    specifiers = []

                    # Extract specifiers
                    if "import {" in line or "import {" in line:
                        specifier_text = match.group(1) if len(match.groups()) > 1 else ""
                        if specifier_text:
                            specifiers = self._parse_specifiers(specifier_text)

                    imports.append(
                        JSImportInfo(
                            module=module,
                            import_type="es6",
                            is_dynamic=False,
                            specifiers=specifiers,
                            line_number=line_num,
                        )
                    )
                    break

        return imports

    def _parse_specifiers(self, specifier_text: str) -> list[dict[str, str]]:
        """
        Parse import/export specifiers.

        Args:
            specifier_text: Text between { and } in import/export.

        Returns:
            List of specifier dicts with 'name' and 'alias' keys.
        """
        specifiers = []

        # Split by comma and clean up
        for spec in specifier_text.split(","):
            spec = spec.strip()

            # Check for alias: import { name as alias }
            if " as " in spec:
                name, alias = spec.split(" as ", 1)
                specifiers.append({"name": name.strip(), "alias": alias.strip()})
            elif spec:
                specifiers.append({"name": spec, "alias": spec})

        return specifiers

    def _parse_commonjs_imports(self, content: str) -> list[JSImportInfo]:
        """
        Parse CommonJS require() statements.

        Supports:
        - const module = require('module')
        - const { named } = require('module')
        - require('module')
        """
        imports: list[JSImportInfo] = []

        # CommonJS require patterns
        patterns = [
            # Destructured: const { Button } = require('module')
            r"const\s+\{\s*([^}]+)\s*\}\s*=\s*require\(['\"]([^'\"]+)['\"]\)",
            # Variable: const module = require('module')
            r"const\s+([\w$]+)\s*=\s*require\(['\"]([^'\"]+)['\"]\)",
            # Bare require: require('module')
            r"require\(['\"]([^'\"]+)['\"]\)",
        ]

        for line_num, line in enumerate(content.split("\n"), 1):
            line = line.strip()

            # Skip comments
            if line.startswith("//") or line.startswith("/*"):
                continue

            for pattern in patterns:
                match = re.search(pattern, line)
                if match:
                    # Module is always the last group
                    module = match.group(len(match.groups()))

                    specifiers = []
                    # Check for destructured import
                    if "const {" in line:
                        specifier_text = match.group(1)
                        specifiers = self._parse_specifiers(specifier_text)

                    imports.append(
                        JSImportInfo(
                            module=module,
                            import_type="commonjs",
                            is_dynamic=False,
                            specifiers=specifiers,
                            line_number=line_num,
                        )
                    )
                    break

        return imports

    def _parse_dynamic_imports(self, content: str) -> list[JSImportInfo]:
        """
        Parse dynamic import() statements.

        Supports:
        - import('module')
        - import('module').then(...)
        - const module = await import('module')
        """
        imports: list[JSImportInfo] = []

        # Dynamic import pattern
        pattern = r"import\(['\"]([^'\"]+)['\"]*\)"

        for line_num, line in enumerate(content.split("\n"), 1):
            matches = re.findall(pattern, line)
            for module in matches:
                imports.append(
                    JSImportInfo(
                        module=module,
                        import_type="dynamic",
                        is_dynamic=True,
                        specifiers=[],
                        line_number=line_num,
                    )
                )

        return imports

    def _parse_es6_exports(self, content: str) -> list[JSExportInfo]:
        """
        Parse ES6 export statements.

        Supports:
        - export default expression
        - export const name = value
        - export { name }
        - export { name as alias }
        - export * from 'module'
        - export * as name from 'module'
        """
        exports: list[JSExportInfo] = []

        # ES6 export patterns
        patterns = [
            # Named export: export const name = value
            r"export\s+(const|let|var|function|class)\s+([\w$]+)",
            # Default export: export default expression
            r"export\s+default\s+(?:class|function|const|let|var\s+)?([\w$]+)?",
            # Export from: export { name1, name2 } from 'module'
            r"export\s+\{\s*([^}]+)\s*\}\s+from\s+['\"]([^'\"]+)['\"]",
            # Export list: export { name1, name2 }
            r"export\s+\{\s*([^}]+)\s*\}",
            # Export wildcard: export * from 'module'
            r"export\s+\*\s+from\s+['\"]([^'\"]+)['\"]",
            # Export wildcard as: export * as name from 'module'
            r"export\s+\*\s+as\s+([\w$]+)\s+from\s+['\"]([^'\"]+)['\"]",
        ]

        for line_num, line in enumerate(content.split("\n"), 1):
            line = line.strip()

            # Skip comments
            if line.startswith("//") or line.startswith("/*"):
                continue

            if not line.startswith("export "):
                continue

            for pattern in patterns:
                match = re.search(pattern, line)
                if match:
                    # Default export
                    if "export default" in line:
                        name = match.group(1) if match.group(1) else "default"
                        exports.append(
                            JSExportInfo(
                                name=name,
                                export_type="default",
                                is_default=True,
                                line_number=line_num,
                            )
                        )
                    # Named exports
                    elif "export {" in line or "export {" in line:
                        specifier_text = match.group(1)
                        for spec in self._parse_specifiers(specifier_text):
                            exports.append(
                                JSExportInfo(
                                    name=spec["name"],
                                    export_type="named",
                                    is_default=False,
                                    line_number=line_num,
                                )
                            )
                    # export const/let/var/function/class
                    elif match.group(1) in ["const", "let", "var", "function", "class"]:
                        name = match.group(2)
                        exports.append(
                            JSExportInfo(
                                name=name,
                                export_type="named",
                                is_default=False,
                                line_number=line_num,
                            )
                        )
                    # Export wildcard
                    elif "export *" in line:
                        if " as " in line:
                            name = match.group(1)
                            exports.append(
                                JSExportInfo(
                                    name=name,
                                    export_type="wildcard",
                                    is_default=False,
                                    line_number=line_num,
                                )
                            )
                        else:
                            exports.append(
                                JSExportInfo(
                                    name="*",
                                    export_type="wildcard",
                                    is_default=False,
                                    line_number=line_num,
                                )
                            )
                    break

        return exports

    def _parse_commonjs_exports(self, content: str) -> list[JSExportInfo]:
        """
        Parse CommonJS module.exports statements.

        Supports:
        - module.exports = expression
        - module.exports.name = value
        - exports.name = value
        """
        exports: list[JSExportInfo] = []

        # CommonJS export patterns
        patterns = [
            # Named export: exports.name = value
            r"exports\.([\w$]+)\s*=",
            # Module export: module.exports.name = value
            r"module\.exports\.([\w$]+)\s*=",
            # Default export: module.exports = expression
            r"module\.exports\s*=",
        ]

        for line_num, line in enumerate(content.split("\n"), 1):
            line = line.strip()

            # Skip comments
            if line.startswith("//") or line.startswith("/*"):
                continue

            for pattern in patterns:
                match = re.search(pattern, line)
                if match:
                    if "module.exports =" in line and "module.exports." not in line:
                        # Default export
                        exports.append(
                            JSExportInfo(
                                name="default",
                                export_type="default",
                                is_default=True,
                                line_number=line_num,
                            )
                        )
                    else:
                        # Named export
                        name = match.group(1)
                        exports.append(
                            JSExportInfo(
                                name=name,
                                export_type="named",
                                is_default=False,
                                line_number=line_num,
                            )
                        )
                    break

        return exports

    def categorize_import(
        self,
        import_info: JSImportInfo,
        source_file: Path,
        local_modules: set[str] | None = None,
    ) -> str:
        """
        Categorize an import as node_modules, local, or stdlib.

        Args:
            import_info: The import to categorize.
            source_file: The file containing the import.
            local_modules: Set of known local module names.

        Returns:
            One of: "node_modules", "local", "stdlib"
        """
        module = import_info["module"]

        # Resolve path aliases
        resolved_module = self._resolve_path_alias(module)

        # Node modules (starts with @scope/ or non-relative path without ./ or ../)
        if module.startswith("@") or (
            not module.startswith(".") and not module.startswith("/")
        ):
            # Check if it's a known local module
            if local_modules:
                root_module = module.split("/")[0]
                if root_module in local_modules:
                    return "local"
            return "node_modules"

        # Relative import (./ or ../)
        if module.startswith("./") or module.startswith("../"):
            return "local"

        # Absolute path
        if module.startswith("/"):
            return "local"

        # Default to node_modules
        return "node_modules"

    def build_dependency_graph(
        self,
        files: list[Path],
        local_modules: set[str] | None = None,
    ) -> dict[str, dict[str, Any]]:
        """
        Build a dependency graph for multiple JS/TS files.

        Args:
            files: List of JS/TS files to analyze.
            local_modules: Set of known local module names.

        Returns:
            Dictionary mapping file paths to their imports and exports.
        """
        dependency_graph: dict[str, dict[str, Any]] = {}

        for file_path in files:
            result = self.parse_file(file_path)

            # Categorize imports
            categorized_imports = []
            for imp in result["imports"]:
                imp["category"] = self.categorize_import(
                    imp,
                    file_path,
                    local_modules,
                )
                categorized_imports.append(imp)

            dependency_graph[str(file_path)] = {
                "imports": categorized_imports,
                "exports": result["exports"],
            }

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

        # Look for package.json to identify workspace packages
        for pkg_json in project_root.rglob("package.json"):
            try:
                content = pkg_json.read_text(encoding="utf-8")
                pkg_data = json.loads(content)
                name = pkg_data.get("name")
                if name:
                    local_modules.add(name)
            except (OSError, json.JSONDecodeError):
                pass

        return local_modules

    def resolve_import_path(
        self,
        import_info: JSImportInfo,
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

        module = import_info["module"]

        # Resolve path aliases
        resolved_module = self._resolve_path_alias(module)

        # Handle relative imports
        if module.startswith("./") or module.startswith("../"):
            source_dir = source_file.parent
            resolved_path = (source_dir / resolved_module).resolve()

            # Try common extensions
            for ext in [".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"]:
                if (resolved_path.with_suffix(ext)).exists():
                    return resolved_path.with_suffix(ext)

            # Check for index files
            for ext in [".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"]:
                index_file = resolved_path / f"index{ext}"
                if index_file.exists():
                    return index_file

            # Check if it's a directory
            if resolved_path.is_dir():
                return resolved_path

            return None

        # Handle absolute paths (after alias resolution)
        if resolved_module.startswith("/"):
            resolved_path = Path(resolved_module).resolve()

            for ext in [".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"]:
                if (resolved_path.with_suffix(ext)).exists():
                    return resolved_path.with_suffix(ext)

            return None

        # Handle node_modules (check in project)
        if not module.startswith("."):
            # Try to resolve from node_modules
            node_modules_path = self.project_root / "node_modules" / module
            if node_modules_path.exists():
                # Look for package.json
                pkg_json = node_modules_path / "package.json"
                if pkg_json.exists():
                    try:
                        content = pkg_json.read_text(encoding="utf-8")
                        pkg_data = json.loads(content)
                        main_file = pkg_data.get("main", "index.js")
                        return node_modules_path / main_file
                    except (OSError, json.JSONDecodeError):
                        pass

                # Try index.js
                index_file = node_modules_path / "index.js"
                if index_file.exists():
                    return index_file

        return None

    def analyze_dependencies(
        self,
        file_path: Path,
        local_modules: set[str] | None = None,
    ) -> dict[str, Any]:
        """
        Perform a comprehensive dependency analysis of a single file.

        Args:
            file_path: Path to the JS/TS file.
            local_modules: Set of known local module names.

        Returns:
            Dictionary containing analysis results.
        """
        result = self.parse_file(file_path)

        node_modules_imports = []
        local_imports = []

        for imp in result["imports"]:
            category = self.categorize_import(imp, file_path, local_modules)
            imp["category"] = category

            if category == "local":
                local_imports.append(imp)
            else:
                node_modules_imports.append(imp)

        return {
            "file": str(file_path),
            "total_imports": len(result["imports"]),
            "total_exports": len(result["exports"]),
            "node_modules": node_modules_imports,
            "local": local_imports,
            "imports": result["imports"],
            "exports": result["exports"],
        }
