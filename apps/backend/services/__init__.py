"""
Services Module
===============

Background services and orchestration for Auto Claude.
"""

from .context import ServiceContext
from .orchestrator import ServiceOrchestrator
from .recovery import RecoveryManager
from .spec_service import (
    SpecErrorCode,
    SpecInfo,
    SpecService,
    SpecCreationError,
    ValidationError,
    ValidationResult,
    create_validated_spec,
    validate_spec_input,
)

__all__ = [
    "ServiceContext",
    "ServiceOrchestrator",
    "RecoveryManager",
    # Spec service exports
    "SpecErrorCode",
    "SpecInfo",
    "SpecService",
    "SpecCreationError",
    "ValidationError",
    "ValidationResult",
    "create_validated_spec",
    "validate_spec_input",
]
