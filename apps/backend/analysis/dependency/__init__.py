"""
Dependency Analysis Module
==========================

Parses and analyzes cross-file dependencies in Python projects.
Extracts imports, builds dependency graphs, and categorizes imports.
"""

from __future__ import annotations

from .python_parser import PythonDependencyParser

__all__ = ["PythonDependencyParser"]
