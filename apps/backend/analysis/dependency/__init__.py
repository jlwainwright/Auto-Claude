"""
Dependency Analysis Module
==========================

Parses and analyzes cross-file dependencies in Python, JavaScript, and TypeScript projects.
Extracts imports, builds dependency graphs, and categorizes imports.
"""

from __future__ import annotations

from .js_parser import JSDependencyParser
from .python_parser import PythonDependencyParser

__all__ = ["PythonDependencyParser", "JSDependencyParser"]
