"""
Codebase Graph Models
======================

Data models for representing codebase graphs, file nodes, dependency edges,
architecture patterns, and service boundaries.
"""

from .analysis_result import EnhancedAnalysisResult
from .architecture_models import (
    ArchitectureAnalysis,
    ArchitecturePatternDetection,
    ExposedAPI,
    LayerType,
    PatternIndicator,
    ServiceBoundary,
)
from .graph_models import (
    ArchitecturePattern,
    CodebaseGraph,
    DependencyEdge,
    DependencyType,
    FileNode,
    GraphMetrics,
)

__all__ = [
    # Graph models
    "FileNode",
    "DependencyEdge",
    "CodebaseGraph",
    "GraphMetrics",
    "DependencyType",
    "ArchitecturePattern",
    # Architecture models
    "ArchitectureAnalysis",
    "ArchitecturePatternDetection",
    "ServiceBoundary",
    "ExposedAPI",
    "PatternIndicator",
    "LayerType",
    # Analysis result
    "EnhancedAnalysisResult",
]
