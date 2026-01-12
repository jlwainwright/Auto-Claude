"""
Architecture Analysis Module
============================

Detects software architecture patterns such as MVC, microservices,
monorepo, and layered architecture from project structure.
"""

from .pattern_detector import ArchitecturePatternDetector
from .service_boundary_detector import ServiceBoundaryDetector

__all__ = ["ArchitecturePatternDetector", "ServiceBoundaryDetector"]
