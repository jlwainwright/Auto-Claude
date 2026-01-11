"""
Architecture Analysis Module
============================

Detects software architecture patterns such as MVC, microservices,
monorepo, and layered architecture from project structure.
"""

from .pattern_detector import ArchitecturePatternDetector

__all__ = ["ArchitecturePatternDetector"]
