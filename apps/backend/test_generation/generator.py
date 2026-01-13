"""
Test Generator
==============

Base class for generating unit tests from code analysis.
"""

import ast
import logging
from pathlib import Path
from typing import Any

from analysis.test_discovery import TestDiscovery, TestDiscoveryResult

from .models import FunctionInfo, TestGenerationConfig, TestGenerationResult

logger = logging.getLogger(__name__)


class TestGenerator:
    """
    Base class for generating unit tests.
    
    Analyzes code to extract function signatures and generates test code
    using framework-specific templates.
    
    Example:
        generator = TestGenerator(project_dir)
        result = generator.generate_tests(
            Path("src/utils.py"),
            functions=["calculate_total"],
            config=TestGenerationConfig(coverage_target=80.0)
        )
    """
    
    __test__ = False  # Prevent pytest from collecting this as a test class
    
    def __init__(self, project_dir: Path):
        """
        Initialize the test generator.
        
        Args:
            project_dir: Path to the project root directory
        """
        self.project_dir = Path(project_dir).resolve()
        self.test_discovery = TestDiscovery()
        self._discovery_result: TestDiscoveryResult | None = None
    
    def discover_framework(self) -> TestDiscoveryResult:
        """
        Discover the test framework used in the project.
        
        Returns:
            TestDiscoveryResult with detected frameworks
        """
        if self._discovery_result is None:
            self._discovery_result = self.test_discovery.discover(self.project_dir)
        return self._discovery_result
    
    def parse_file(self, file_path: Path) -> list[FunctionInfo]:
        """
        Parse a file and extract function/method information.
        
        Args:
            file_path: Path to the file to parse
            
        Returns:
            List of FunctionInfo objects for each function/method found
        """
        file_path = Path(file_path)
        if not file_path.is_absolute():
            file_path = self.project_dir / file_path
        
        if not file_path.exists():
            logger.warning(f"File not found: {file_path}")
            return []
        
        # Determine file type and parse accordingly
        suffix = file_path.suffix.lower()
        
        if suffix == ".py":
            return self._parse_python_file(file_path)
        elif suffix in (".ts", ".tsx", ".js", ".jsx"):
            return self._parse_javascript_file(file_path)
        else:
            logger.warning(f"Unsupported file type: {suffix}")
            return []
    
    def _parse_python_file(self, file_path: Path) -> list[FunctionInfo]:
        """
        Parse a Python file using AST.
        
        Args:
            file_path: Path to the Python file
            
        Returns:
            List of FunctionInfo objects
        """
        try:
            content = file_path.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(file_path))
            
            functions: list[FunctionInfo] = []
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    func_info = self._extract_python_function(node, file_path, content)
                    if func_info:
                        functions.append(func_info)
            
            return functions
        
        except SyntaxError as e:
            logger.error(f"Syntax error parsing {file_path}: {e}")
            return []
        except Exception as e:
            logger.error(f"Error parsing {file_path}: {e}")
            return []
    
    def _extract_python_function(
        self, node: ast.FunctionDef, file_path: Path, content: str
    ) -> FunctionInfo | None:
        """
        Extract function information from a Python AST node.
        
        Args:
            node: AST function definition node
            file_path: Path to the source file
            content: Full file content for line number calculation
            
        Returns:
            FunctionInfo object or None if extraction fails
        """
        # Get line numbers (end_lineno available in Python 3.8+)
        line_start = node.lineno
        line_end = getattr(node, "end_lineno", line_start)
        
        # Fallback: calculate end line from last child node
        if line_end == line_start and hasattr(node, "body") and node.body:
            last_node = node.body[-1]
            if hasattr(last_node, "end_lineno"):
                line_end = last_node.end_lineno
            elif hasattr(last_node, "lineno"):
                line_end = last_node.lineno
        
        # Extract parameters
        parameters: list[str] = []
        parameter_types: dict[str, str] = {}
        
        for arg in node.args.args:
            param_name = arg.arg
            parameters.append(param_name)
            
            # Extract type hint if present
            if arg.annotation:
                try:
                    # ast.unparse available in Python 3.9+
                    if hasattr(ast, "unparse"):
                        type_str = ast.unparse(arg.annotation)
                    else:
                        # Fallback for older Python versions
                        type_str = self._ast_to_string(arg.annotation)
                    parameter_types[param_name] = type_str
                except Exception:
                    pass
        
        # Extract return type
        return_type: str | None = None
        if node.returns:
            try:
                # ast.unparse available in Python 3.9+
                if hasattr(ast, "unparse"):
                    return_type = ast.unparse(node.returns)
                else:
                    # Fallback for older Python versions
                    return_type = self._ast_to_string(node.returns)
            except Exception:
                pass
        
        # Extract docstring
        docstring: str | None = None
        if (
            node.body
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)
        ):
            docstring = node.body[0].value.value
        
        # Check if it's a method (has 'self' or 'cls' as first parameter)
        is_method = bool(parameters and parameters[0] in ("self", "cls"))
        
        # Find class name if it's a method
        class_name: str | None = None
        if is_method:
            # Parse the file and find the parent class
            try:
                tree = ast.parse(content, filename=str(file_path))
                for ast_node in ast.walk(tree):
                    if isinstance(ast_node, ast.ClassDef):
                        for item in ast_node.body:
                            if isinstance(item, ast.FunctionDef) and item.name == node.name:
                                # Check if it's the same function by comparing line numbers
                                if item.lineno == node.lineno:
                                    class_name = ast_node.name
                                    break
                        if class_name:
                            break
                    if class_name:
                        break
            except Exception:
                pass
        
        # Extract decorators
        decorators: list[str] = []
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Name):
                decorators.append(decorator.id)
            elif isinstance(decorator, ast.Attribute):
                if hasattr(ast, "unparse"):
                    decorators.append(ast.unparse(decorator))
                else:
                    decorators.append(self._ast_to_string(decorator))
        
        return FunctionInfo(
            name=node.name,
            file_path=file_path,
            line_start=line_start,
            line_end=line_end,
            parameters=parameters,
            parameter_types=parameter_types,
            return_type=return_type,
            docstring=docstring,
            is_method=is_method,
            class_name=class_name,
            is_async=isinstance(node, ast.AsyncFunctionDef),
            decorators=decorators,
        )
    
    def _ast_to_string(self, node: ast.AST) -> str:
        """
        Convert an AST node to a string representation.
        
        Fallback for Python versions without ast.unparse.
        
        Args:
            node: AST node to convert
            
        Returns:
            String representation of the node
        """
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._ast_to_string(node.value)}.{node.attr}"
        elif isinstance(node, ast.Constant):
            return repr(node.value)
        elif isinstance(node, ast.Subscript):
            return f"{self._ast_to_string(node.value)}[{self._ast_to_string(node.slice)}]"
        else:
            # Generic fallback
            return str(node)
    
    def _parse_javascript_file(self, file_path: Path) -> list[FunctionInfo]:
        """
        Parse a JavaScript/TypeScript file.
        
        Note: This is a basic implementation. For production use,
        consider using tree-sitter or a proper JS/TS parser.
        
        Args:
            file_path: Path to the JavaScript/TypeScript file
            
        Returns:
            List of FunctionInfo objects
        """
        # TODO: Implement proper JS/TS parsing using tree-sitter or similar
        # For now, return empty list - this will be enhanced in framework-specific implementations
        logger.warning(f"JavaScript/TypeScript parsing not yet implemented for {file_path}")
        return []
    
    def identify_functions_needing_tests(
        self, file_path: Path, existing_tests: list[Path] | None = None
    ) -> list[FunctionInfo]:
        """
        Identify functions in a file that need tests.
        
        Args:
            file_path: Path to the source file
            existing_tests: Optional list of existing test file paths
            
        Returns:
            List of FunctionInfo for functions that need tests
        """
        all_functions = self.parse_file(file_path)
        
        # Filter out functions that already have tests
        # This is a simplified check - in production, you'd want to
        # actually check test coverage or parse test files
        if existing_tests:
            # TODO: Parse test files to see which functions are already tested
            pass
        
        # Filter out private functions (starting with _) unless they're magic methods
        # Filter out test functions themselves
        functions_needing_tests = []
        for f in all_functions:
            # Skip test functions
            if f.name.startswith("test_") or (f.name.startswith("test") and len(f.name) > 4):
                continue
            
            # Include public functions (not starting with _)
            if not f.name.startswith("_"):
                functions_needing_tests.append(f)
            # Include magic methods (__name__)
            elif f.name.startswith("__") and f.name.endswith("__"):
                functions_needing_tests.append(f)
        
        return functions_needing_tests
    
    def generate_tests(
        self,
        file_path: Path,
        functions: list[str] | None = None,
        config: TestGenerationConfig | None = None,
    ) -> TestGenerationResult:
        """
        Generate tests for functions in a file.
        
        Args:
            file_path: Path to the source file
            functions: Optional list of specific function names to test
            config: Test generation configuration
            
        Returns:
            TestGenerationResult with generated test code
        """
        if config is None:
            config = TestGenerationConfig()
        
        # Discover framework if not specified
        if config.framework is None:
            discovery = self.discover_framework()
            if discovery.frameworks:
                config.framework = discovery.frameworks[0].name
            else:
                return TestGenerationResult(
                    success=False,
                    errors=["No test framework detected in project"],
                )
        
        # Parse file to get function information
        all_functions = self.parse_file(file_path)
        
        if not all_functions:
            return TestGenerationResult(
                success=False,
                errors=[f"No functions found in {file_path}"],
            )
        
        # Filter to requested functions
        if functions:
            functions_to_test = [f for f in all_functions if f.name in functions]
        else:
            functions_to_test = self.identify_functions_needing_tests(file_path)
        
        if not functions_to_test:
            return TestGenerationResult(
                success=False,
                errors=["No functions selected for testing"],
            )
        
        # Generate test code using framework-specific template
        # This will be implemented by framework-specific subclasses
        # For now, return a placeholder result
        return TestGenerationResult(
            success=True,
            test_code="# Test generation not yet implemented for this framework",
            functions_tested=[f.name for f in functions_to_test],
            warnings=["Test generation templates not yet implemented"],
        )
