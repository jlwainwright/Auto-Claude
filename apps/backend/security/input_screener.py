#!/usr/bin/env python3
"""
Input Harmlessness Screener
===========================

Screens user input (task descriptions, specs) for prompt injection attacks
and potentially malicious instructions before processing.

This provides a critical security layer at the input pipeline to prevent
prompt injection through task descriptions, which is a known vulnerability
in AI coding assistants.

Usage:
    from security import InputScreener, ScreeningResult, screen_input

    screener = InputScreener(level="normal")
    result = screener.screen_input("Add user authentication")

    if not result.is_safe:
        print(f"Input rejected: {result.reason}")

    # Or use convenience function
    result = screen_input("Create a login form")
"""

import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import ClassVar

from .constants import (
    DEFAULT_SCREENING_ALLOWLIST,
    DEFAULT_SCREENING_LEVEL,
    MAX_SCREENING_INPUT_LENGTH,
    SCREENING_ALLOWLIST_FILENAME,
    SCREENING_LEVEL_ENV_VAR,
    SCREENING_THRESHOLDS,
)

logger = logging.getLogger(__name__)

# Security logger for dedicated security event logging
security_logger = logging.getLogger("security.input_screener")


# =============================================================================
# MODELS AND TYPES
# =============================================================================


class ScreeningVerdict(Enum):
    """Possible screening verdicts."""

    SAFE = "safe"
    """Input passes all checks and can be processed."""

    SUSPICIOUS = "suspicious"
    """Input shows concerning patterns but may be legitimate."""

    REJECTED = "rejected"
    """Input is clearly malicious and must be rejected."""


class ScreeningLevel(Enum):
    """Screening strictness levels."""

    PERMISSIVE = "permissive"
    """Only block critical threats. Higher false positive rate but maximum flexibility."""

    NORMAL = "normal"
    """Balance security and usability. Default recommended level."""

    STRICT = "strict"
    """Block anything suspicious. Lowest false positive rate but may reject valid input."""


@dataclass
class DetectedPattern:
    """A pattern detected during screening."""

    name: str
    """Human-readable pattern name."""

    category: str
    """Pattern category (e.g., 'instruction_override', 'role_hijacking')."""

    severity: str
    """Severity level: 'low', 'medium', 'high', 'critical'."""

    matched_text: str
    """The actual text that matched the pattern."""

    confidence: float
    """Confidence score 0.0-1.0."""


@dataclass
class ScreeningResult:
    """Result of screening user input."""

    verdict: ScreeningVerdict
    """Final verdict on the input."""

    is_safe: bool
    """True if input can be processed, False if rejected."""

    confidence: float
    """Overall confidence score 0.0-1.0."""

    detected_patterns: list[DetectedPattern] = field(default_factory=list)
    """List of patterns that were detected."""

    reason: str = ""
    """Human-readable explanation of the verdict."""

    screening_time_ms: float = 0.0
    """Time taken to screen the input in milliseconds."""

    def to_dict(self) -> dict:
        """Convert result to dictionary for serialization."""
        return {
            "verdict": self.verdict.value,
            "is_safe": self.is_safe,
            "confidence": self.confidence,
            "detected_patterns": [
                {
                    "name": p.name,
                    "category": p.category,
                    "severity": p.severity,
                    "matched_text": p.matched_text[:100] if len(p.matched_text) > 100 else p.matched_text,
                    "confidence": p.confidence,
                }
                for p in self.detected_patterns
            ],
            "reason": self.reason,
            "screening_time_ms": self.screening_time_ms,
        }


# =============================================================================
# SCREENING CONFIGURATION
# =============================================================================


# Helper function to get screening level from environment or default
def _get_screening_level() -> str:
    """
    Get screening level from environment variable or use default.

    Reads from AUTO_CLAUDE_SCREENING_LEVEL environment variable.
    Valid values: 'permissive', 'normal', 'strict'

    Returns:
        Screening level string (default: 'normal')
    """
    level = os.getenv(SCREENING_LEVEL_ENV_VAR, DEFAULT_SCREENING_LEVEL).lower()
    if level not in SCREENING_THRESHOLDS:
        logger.warning(
            f"Invalid screening level '{level}', using default '{DEFAULT_SCREENING_LEVEL}'"
        )
        return DEFAULT_SCREENING_LEVEL
    return level


def _setup_security_logger(project_dir: str | None = None) -> None:
    """
    Set up the security logger with file handler for persistent logging.

    Creates a dedicated security log file for screening events that can be
    used for security monitoring and false positive analysis.

    Args:
        project_dir: Optional project directory for log file location.
                    If None, logs to current directory.
    """
    # Avoid adding duplicate handlers
    if security_logger.handlers:
        return

    # Determine log directory
    if project_dir:
        log_dir = Path(project_dir) / ".auto-claude" / "logs"
    else:
        log_dir = Path(".auto-claude") / "logs"

    log_dir.mkdir(parents=True, exist_ok=True)

    # Security log file with date stamp
    log_file = log_dir / f"screening_{datetime.now(timezone.utc):%Y%m%d}.log"

    # Create file handler with detailed format
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.INFO)

    # Detailed format for security monitoring
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(formatter)

    security_logger.addHandler(file_handler)
    security_logger.setLevel(logging.INFO)

    # Prevent propagation to avoid duplicate logs
    security_logger.propagate = False

    logger.info(f"Security logging initialized: {log_file}")


def _log_security_event(
    event_type: str,
    data: dict,
    level: str = "info"
) -> None:
    """
    Log a structured security event.

    Args:
        event_type: Type of security event (e.g., 'screening_complete', 'pattern_detected')
        data: Event data as dictionary
        level: Log level ('info', 'warning', 'error')
    """
    # Create structured log entry
    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "data": data
    }

    # Log as JSON for structured parsing
    log_message = json.dumps(log_entry, separators=(",", ":"))

    # Route to appropriate log level
    if level == "error":
        security_logger.error(log_message)
    elif level == "warning":
        security_logger.warning(log_message)
    else:
        security_logger.info(log_message)


# =============================================================================
# PATTERN DEFINITIONS
# =============================================================================


# Pattern definitions for prompt injection detection
# Each pattern has: regex, severity, category, name
PATTERNS = [
    # Instruction Override Patterns
    {
        "name": "Ignore Instructions",
        "category": "instruction_override",
        "severity": "critical",
        "regex": re.compile(
            r"(?i)(ignore\s+(all\s+)?(?:previous|above|earlier|prior)?\s*(?:instructions?|commands?|directives?|prompts?|text))"
        ),
        "confidence": 0.95,
    },
    {
        "name": "Override Instructions",
        "category": "instruction_override",
        "severity": "critical",
        "regex": re.compile(
            r"(?i)(override|disregard|forget|discard)\s+(all\s+)?((previous|above|earlier|prior)\s+)?(instructions?|commands?|directives?|prompts?|text)((\s+(previous|above|earlier|prior))?)?(?!\s+(?:css|styles?|styling|configuration|settings|defaults?|headers?|http|response|method))"
        ),
        "confidence": 0.95,
    },
    {
        "name": "New Instructions",
        "category": "instruction_override",
        "severity": "high",
        "regex": re.compile(
            r"(?i)^(new\s+)?(instructions?|commands?|directives?)(?::|\.|\s|$)"
        ),
        "confidence": 0.70,
    },
    {
        "name": "System Prompt Override",
        "category": "instruction_override",
        "severity": "critical",
        "regex": re.compile(
            r"(?i)(replace|change|modify|override)\s+(the\s+)?(system\s+)?prompt"
        ),
        "confidence": 0.90,
    },

    # Role Hijacking Patterns
    {
        "name": "Act As Role",
        "category": "role_hijacking",
        "severity": "high",
        "regex": re.compile(
            r"(?i)(act|behave?|role-play?|roleplay|pretend)\s+(as\s+?(a|an|the)\s+)?(developer?|administrator?|root?|superuser|supervisor|god|admin|owner|master)"
        ),
        "confidence": 0.85,
    },
    {
        "name": "You Are Now",
        "category": "role_hijacking",
        "severity": "critical",
        "regex": re.compile(
            r"(?i)you\s+(are\s+)?now\s+(a\s+)?(developer?|administrator?|root?|superuser|supervisor|god|admin|owner|master)"
        ),
        "confidence": 0.90,
    },
    {
        "name": "Switch Mode",
        "category": "role_hijacking",
        "severity": "medium",
        "regex": re.compile(
            r"(?i)(switch|change|enter)\s+(to\s+)?(developer?|admin?|root?|god|unsafe|unrestricted|debug)\s+mode"
        ),
        "confidence": 0.70,
    },
    {
        "name": "Persona Adoption",
        "category": "role_hijacking",
        "severity": "medium",
        "regex": re.compile(
            r"(?i)(adopt|take\s+on|assume)\s+(the\s+)?(persona|role|identity)\s+of"
        ),
        "confidence": 0.65,
    },

    # Context Manipulation Patterns
    {
        "name": "System Label",
        "category": "context_manipulation",
        "severity": "high",
        "regex": re.compile(
            r"(?i)\[?(SYSTEM|ADMIN|ROOT|SUPERUSER|DEVELOPER|OWNER)\]?\s*:"
        ),
        "confidence": 0.75,
    },
    {
        "name": "Context Separator",
        "category": "context_manipulation",
        "severity": "medium",
        "regex": re.compile(
            r"(?i)(^|\n|\r\n)(---+|===+|\*\*\*+|###+)"
        ),
        "confidence": 0.60,
    },
    {
        "name": "Prompt Injection Marker",
        "category": "context_manipulation",
        "severity": "high",
        "regex": re.compile(
            r"(?i)(injection|jailbreak|exploit|bypass)(\s+(the\s+)?(prompt|system|security|restrictions?|filters?|controls?))?"
        ),
        "confidence": 0.90,
    },

    # Delimiter Attacks
    {
        "name": "Triple Delimiter",
        "category": "delimiter_attack",
        "severity": "medium",
        "regex": re.compile(
            r"(---+|===+|\*\*\*+|###+)"
        ),
        "confidence": 0.60,
    },
    {
        "name": "Code Block Injection",
        "category": "delimiter_attack",
        "severity": "medium",
        "regex": re.compile(
            r"```[a-z]*\s*$"
        ),
        "confidence": 0.55,
    },
    {
        "name": "XML Tag Injection",
        "category": "delimiter_attack",
        "severity": "medium",
        "regex": re.compile(
            r"<(system|instruction|prompt|command|override)>"
        ),
        "confidence": 0.70,
    },

    # Encoding Attacks
    {
        "name": "Base64 Encoded",
        "category": "encoding_attack",
        "severity": "high",
        "regex": re.compile(
            r"(?i)(base64|b64)\s*(encode|decode)"
        ),
        "confidence": 0.80,
    },
    {
        "name": "URL Encoded",
        "category": "encoding_attack",
        "severity": "medium",
        "regex": re.compile(
            r"(?i)(url|percent)\s*(encode|decode)"
        ),
        "confidence": 0.75,
    },
    {
        "name": "Rot13 Attempt",
        "category": "encoding_attack",
        "severity": "low",
        "regex": re.compile(
            r"(?i)(rot13|rotate\s+13)\s+(encode|decode)"
        ),
        "confidence": 0.50,
    },
    {
        "name": "Hex Encoded",
        "category": "encoding_attack",
        "severity": "medium",
        "regex": re.compile(
            r"(?i)(hex|xex)\s*(encode|decode)[:\s]+([0-9A-Fa-f]{2}){10,}"
        ),
        "confidence": 0.70,
    },

    # Shell Injection Patterns
    {
        "name": "Shell Command Injection",
        "category": "shell_injection",
        "severity": "critical",
        "regex": re.compile(
            r";\s*(rm|delete|format|curl|wget|nc|netcat|chmod|chown)\s+"
        ),
        "confidence": 0.95,
    },
    {
        "name": "Command Substitution",
        "category": "shell_injection",
        "severity": "high",
        "regex": re.compile(
            r"\$\([^)]*\)|`[^`]*`"
        ),
        "confidence": 0.85,
    },
    {
        "name": "Pipe to Shell",
        "category": "shell_injection",
        "severity": "high",
        "regex": re.compile(
            r"\|\s*(sh|bash|zsh|fish|pwsh|python|perl|ruby|node)\s*$"
        ),
        "confidence": 0.80,
    },
    {
        "name": "File Destruction",
        "category": "shell_injection",
        "severity": "critical",
        "regex": re.compile(
            r"(?i)(rm\s+-rf|del\s+/s|format\s+c:| shred)"
        ),
        "confidence": 0.95,
    },
    {
        "name": "Path Traversal",
        "category": "shell_injection",
        "severity": "high",
        "regex": re.compile(
            r"(?i)(\.\./)+|(\.\.\\)+"
        ),
        "confidence": 0.75,
    },
]

# Keyword-based detection for suspicious terms
# These are checked separately from regex patterns for additional coverage
SUSPICIOUS_KEYWORDS = {
    "jailbreak": "critical",
    "prompt injection": "critical",
    "bypass security": "high",
    "override restrictions": "high",
    "disable safety": "high",
    "ignore rules": "high",
    "forget instructions": "high",
    "developer mode": "medium",
    "admin mode": "medium",
    "root access": "medium",
    "superuser": "medium",
    "unrestricted": "medium",
    "without limits": "medium",
    "no restrictions": "medium",
    "full access": "medium",
    "elevated privileges": "medium",
    "execute arbitrary": "high",
    "run any command": "high",
    "arbitrary code": "high",
    "remote code execution": "high",
}


# =============================================================================
# MAIN SCREENING CLASS
# =============================================================================


class InputScreener:
    """
    Screens user input for prompt injection and malicious patterns.

    The screener uses multiple detection strategies:
    1. Pattern matching - Known prompt injection patterns
    2. Heuristic analysis - Content characteristics
    3. Semantic analysis - Contextual understanding (future)

    Attributes:
        level: Screening strictness level
        config: Thresholds and settings for this level
        allowlist: Set of allowed patterns (if allowlist file exists)
    """

    # Pattern categories
    PATTERN_CATEGORIES: ClassVar[list[str]] = [
        "instruction_override",
        "role_hijacking",
        "context_manipulation",
        "delimiter_attack",
        "encoding_attack",
        "shell_injection",
    ]

    def __init__(
        self,
        level: ScreeningLevel | str | None = None,
        project_dir: str | None = None,
    ):
        """
        Initialize the screener.

        Args:
            level: Screening strictness level (enum or string).
                   If None, reads from AUTO_CLAUDE_SCREENING_LEVEL env var.
            project_dir: Project directory for allowlist file. If None, uses current directory.
        """
        # Determine screening level (parameter > env var > default)
        if level is None:
            level = _get_screening_level()

        if isinstance(level, str):
            level = ScreeningLevel(level.lower())

        self.level = level
        self.config = SCREENING_THRESHOLDS[level.value]

        # Store project directory for logging
        self.project_dir = project_dir

        # Initialize security logger for persistent logging
        _setup_security_logger(project_dir)

        # Load allowlist if project_dir is provided
        self.allowlist: set[str] = set()
        # Always include default allowlist for safe technical phrases
        self.allowlist.update(DEFAULT_SCREENING_ALLOWLIST)
        self._load_allowlist(project_dir)

        logger.debug(f"Initialized InputScreener with level: {level.value}")

        # Log initialization event
        _log_security_event("screener_initialized", {
            "level": level.value,
            "project_dir": str(project_dir) if project_dir else None,
            "allowlist_size": len(self.allowlist)
        })

    def _load_allowlist(self, project_dir: str | None) -> None:
        """
        Load allowlist patterns from project directory.

        The allowlist file should contain one pattern per line.
        Patterns are case-insensitive and can be:
        - Exact phrases to ignore
        - Regular expressions (prefixed with 'regex:')

        Args:
            project_dir: Project directory containing allowlist file
        """
        if project_dir is None:
            return

        allowlist_path = Path(project_dir) / SCREENING_ALLOWLIST_FILENAME

        if not allowlist_path.exists():
            logger.debug(f"No allowlist file found at {allowlist_path}")
            return

        try:
            with open(allowlist_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    # Skip empty lines and comments
                    if not line or line.startswith("#"):
                        continue
                    self.allowlist.add(line.lower())

            logger.info(
                f"Loaded {len(self.allowlist)} patterns from allowlist: {allowlist_path}"
            )
        except Exception as e:
            logger.warning(f"Failed to load allowlist from {allowlist_path}: {e}")

    def _is_allowed(self, user_input: str) -> bool:
        """
        Check if input matches any allowlist pattern.

        Args:
            user_input: The input to check

        Returns:
            True if input matches an allowlist pattern, False otherwise
        """
        if not self.allowlist:
            return False

        input_lower = user_input.lower()

        for pattern in self.allowlist:
            # Check if it's a regex pattern
            if pattern.startswith("regex:"):
                try:
                    regex_pattern = pattern[6:]  # Remove 'regex:' prefix
                    if re.search(regex_pattern, input_lower, re.IGNORECASE):
                        logger.debug(f"Input matched allowlist regex: {regex_pattern}")
                        return True
                except re.error as e:
                    logger.warning(f"Invalid allowlist regex '{pattern}': {e}")
            else:
                # Exact phrase match
                if pattern in input_lower:
                    logger.debug(f"Input matched allowlist pattern: {pattern}")
                    return True

        return False

    def screen_input(self, user_input: str) -> ScreeningResult:
        """
        Screen user input for potential threats.

        Args:
            user_input: The task description or spec content to screen

        Returns:
            ScreeningResult with verdict, detected patterns, and metadata

        Raises:
            ValueError: If input exceeds maximum length
        """
        import time

        start_time = time.time()
        input_length = len(user_input)

        # Log screening start
        _log_security_event("screening_started", {
            "input_length": input_length,
            "screening_level": self.level.value
        })

        # Check allowlist first
        if self._is_allowed(user_input):
            logger.debug("Input matched allowlist pattern, skipping screening")

            result = ScreeningResult(
                verdict=ScreeningVerdict.SAFE,
                is_safe=True,
                confidence=1.0,
                detected_patterns=[],
                reason="Input matched allowlist pattern.",
                screening_time_ms=(time.time() - start_time) * 1000,
            )

            # Log allowlist match for false positive analysis
            _log_security_event("allowlist_match", {
                "input_length": input_length,
                "screening_time_ms": result.screening_time_ms,
                "allowlist_size": len(self.allowlist)
            })

            return result

        # Validate input length
        if input_length > MAX_SCREENING_INPUT_LENGTH:
            _log_security_event("input_rejected", {
                "reason": "input_too_long",
                "input_length": input_length,
                "max_length": MAX_SCREENING_INPUT_LENGTH
            }, level="warning")

            raise ValueError(
                f"Input exceeds maximum length of {MAX_SCREENING_INPUT_LENGTH:,} characters"
            )

        logger.debug(f"Screening input ({input_length:,} chars)")

        # Initialize result
        detected_patterns: list[DetectedPattern] = []

        # Run pattern detection
        detected_patterns.extend(self._detect_regex_patterns(user_input))
        detected_patterns.extend(self._detect_keyword_patterns(user_input))
        detected_patterns.extend(self._detect_heuristics(user_input))

        # Calculate overall confidence
        confidence = self._calculate_confidence(detected_patterns)

        # Determine verdict
        verdict = self._determine_verdict(confidence, detected_patterns)
        is_safe = verdict == ScreeningVerdict.SAFE

        # Build reason message
        reason = self._build_reason(verdict, detected_patterns)

        # Calculate screening time
        screening_time_ms = (time.time() - start_time) * 1000

        result = ScreeningResult(
            verdict=verdict,
            is_safe=is_safe,
            confidence=confidence,
            detected_patterns=detected_patterns,
            reason=reason,
            screening_time_ms=screening_time_ms,
        )

        # Log result with input length
        self._log_screening_result(result, input_length)

        return result

    def _calculate_confidence(self, patterns: list[DetectedPattern]) -> float:
        """
        Calculate overall threat confidence from detected patterns.

        Args:
            patterns: List of detected patterns

        Returns:
            Confidence score 0.0-1.0
        """
        if not patterns:
            return 0.0

        # Weight by severity
        severity_weights = {
            "low": 0.25,
            "medium": 0.5,
            "high": 0.75,
            "critical": 1.0,
        }

        # Calculate weighted average
        total_weight = 0.0
        weighted_sum = 0.0

        for pattern in patterns:
            weight = severity_weights.get(pattern.severity, 0.5)
            weighted_sum += pattern.confidence * weight
            total_weight += weight

        if total_weight == 0:
            return 0.0

        return min(weighted_sum / total_weight, 1.0)

    def _determine_verdict(
        self, confidence: float, patterns: list[DetectedPattern]
    ) -> ScreeningVerdict:
        """
        Determine final verdict based on confidence and patterns.

        Args:
            confidence: Overall threat confidence
            patterns: Detected patterns

        Returns:
            Screening verdict
        """
        # Check for critical severity patterns
        has_critical = any(p.severity == "critical" for p in patterns)

        if has_critical or confidence >= self.config["reject_threshold"]:
            return ScreeningVerdict.REJECTED

        if confidence >= self.config["suspicious_threshold"]:
            return ScreeningVerdict.SUSPICIOUS

        return ScreeningVerdict.SAFE

    def _build_reason(
        self, verdict: ScreeningVerdict, patterns: list[DetectedPattern]
    ) -> str:
        """
        Build human-readable reason for the verdict.

        Args:
            verdict: The screening verdict
            patterns: Detected patterns

        Returns:
            Human-readable explanation
        """
        if verdict == ScreeningVerdict.SAFE:
            return "Input passed all security checks."

        if verdict == ScreeningVerdict.REJECTED:
            if not patterns:
                return "Input rejected due to security concerns."
            # Group by category for clearer message
            categories = set(p.category for p in patterns)
            if len(categories) == 1:
                category = next(iter(categories))
                return f"Input contains potentially malicious content ({category})."
            return f"Input contains potentially malicious content ({len(categories)} threat categories detected)."

        if verdict == ScreeningVerdict.SUSPICIOUS:
            return "Input contains suspicious patterns. Please review and rephrase."

        return "Security screening completed."

    def _log_screening_result(self, result: ScreeningResult, input_length: int) -> None:
        """
        Log screening result for security monitoring.

        Args:
            result: The screening result
            input_length: Length of the screened input
        """
        # Standard logging
        if result.is_safe:
            logger.debug(
                f"Input screening: SAFE (confidence: {result.confidence:.2f}, "
                f"time: {result.screening_time_ms:.1f}ms)"
            )
        else:
            # Don't log full input content for security
            logger.warning(
                f"Input screening: {result.verdict.value.upper()} "
                f"(confidence: {result.confidence:.2f}, "
                f"patterns: {len(result.detected_patterns)}, "
                f"time: {result.screening_time_ms:.1f}ms)"
            )

            # Log detected patterns (without full matched text)
            for pattern in result.detected_patterns:
                logger.debug(
                    f"  - {pattern.name} [{pattern.severity}] "
                    f"(confidence: {pattern.confidence:.2f})"
                )

        # Structured security event logging
        security_data = {
            "verdict": result.verdict.value,
            "is_safe": result.is_safe,
            "confidence": round(result.confidence, 3),
            "input_length": input_length,
            "screening_level": self.level.value,
            "screening_time_ms": round(result.screening_time_ms, 2),
            "pattern_count": len(result.detected_patterns),
            "patterns": [
                {
                    "name": p.name,
                    "category": p.category,
                    "severity": p.severity,
                    "confidence": round(p.confidence, 3),
                    "matched_text_length": len(p.matched_text)
                }
                for p in result.detected_patterns
            ],
            "reason": result.reason
        }

        # Determine log level based on verdict
        log_level = "info"
        if result.verdict == ScreeningVerdict.REJECTED:
            log_level = "warning"
        elif result.verdict == ScreeningVerdict.SUSPICIOUS:
            log_level = "info"

        _log_security_event("screening_complete", security_data, level=log_level)

    def _detect_regex_patterns(self, user_input: str) -> list[DetectedPattern]:
        """
        Detect malicious patterns using regex matching.

        Args:
            user_input: The input to screen

        Returns:
            List of detected patterns
        """
        detected = []

        for pattern_def in PATTERNS:
            try:
                matches = pattern_def["regex"].findall(user_input)
                if matches:
                    # Get the first match for the matched text
                    match_text = str(matches[0]) if matches else ""

                    # Create detected pattern
                    detected.append(
                        DetectedPattern(
                            name=pattern_def["name"],
                            category=pattern_def["category"],
                            severity=pattern_def["severity"],
                            matched_text=match_text,
                            confidence=pattern_def["confidence"],
                        )
                    )

                    logger.debug(
                        f"Pattern detected: {pattern_def['name']} "
                        f"[{pattern_def['severity']}] "
                        f"(confidence: {pattern_def['confidence']:.2f})"
                    )

                    # Log individual pattern detection for security monitoring
                    _log_security_event("pattern_detected", {
                        "pattern_name": pattern_def["name"],
                        "category": pattern_def["category"],
                        "severity": pattern_def["severity"],
                        "confidence": round(pattern_def["confidence"], 3),
                        "matched_text_length": len(match_text),
                        "match_count": len(matches)
                    })
            except re.error as e:
                logger.error(f"Regex error in pattern {pattern_def['name']}: {e}")
                _log_security_event("pattern_error", {
                    "pattern_name": pattern_def["name"],
                    "error": str(e),
                    "error_type": "regex_error"
                }, level="error")
            except Exception as e:
                logger.error(f"Error checking pattern {pattern_def['name']}: {e}")
                _log_security_event("pattern_error", {
                    "pattern_name": pattern_def["name"],
                    "error": str(e),
                    "error_type": "exception"
                }, level="error")

        return detected

    def _detect_keyword_patterns(self, user_input: str) -> list[DetectedPattern]:
        """
        Detect malicious patterns using keyword matching.

        Args:
            user_input: The input to screen

        Returns:
            List of detected patterns
        """
        detected = []
        input_lower = user_input.lower()

        for keyword, severity in SUSPICIOUS_KEYWORDS.items():
            if keyword in input_lower:
                # Find the context around the keyword (up to 100 chars)
                keyword_pos = input_lower.find(keyword)
                start = max(0, keyword_pos - 50)
                end = min(len(user_input), keyword_pos + len(keyword) + 50)
                context = user_input[start:end]

                # Map severity to confidence
                severity_confidence = {
                    "critical": 0.90,
                    "high": 0.75,
                    "medium": 0.60,
                    "low": 0.45,
                }
                confidence = severity_confidence.get(severity, 0.50)

                detected.append(
                    DetectedPattern(
                        name=f"Keyword: {keyword}",
                        category="keyword_match",
                        severity=severity,
                        matched_text=context,
                        confidence=confidence,
                    )
                )

                logger.debug(
                    f"Keyword detected: {keyword} [{severity}] "
                    f"(confidence: {confidence:.2f})"
                )

                # Log keyword detection for security monitoring
                _log_security_event("keyword_detected", {
                    "keyword": keyword,
                    "severity": severity,
                    "confidence": round(confidence, 3),
                    "context_length": len(context),
                    "position": keyword_pos
                })

        return detected

    def _detect_heuristics(self, user_input: str) -> list[DetectedPattern]:
        """
        Detect malicious patterns using heuristic analysis.

        This method analyzes content characteristics that may indicate malicious
        intent even without exact pattern matches. It checks for:
        - Unusual formatting (excessive special chars, mixed case, leetspeak)
        - Suspicious character distributions
        - Contextual anomalies
        - Encoding attempt patterns

        Args:
            user_input: The input to screen

        Returns:
            List of detected patterns
        """
        detected = []

        # Analyze formatting characteristics
        formatting_anomalies = self._check_unusual_formatting(user_input)
        distribution_anomalies = self._check_character_distribution(user_input)
        contextual_anomalies = self._check_contextual_anomalies(user_input)
        encoding_anomalies = self._check_encoding_attempts(user_input)

        detected.extend(formatting_anomalies)
        detected.extend(distribution_anomalies)
        detected.extend(contextual_anomalies)
        detected.extend(encoding_anomalies)

        # Log heuristic detection summary for security monitoring
        if detected:
            _log_security_event("heuristic_anomalies_detected", {
                "formatting_count": len(formatting_anomalies),
                "distribution_count": len(distribution_anomalies),
                "contextual_count": len(contextual_anomalies),
                "encoding_count": len(encoding_anomalies),
                "total_anomalies": len(detected)
            })

        return detected

    def _check_unusual_formatting(self, user_input: str) -> list[DetectedPattern]:
        """
        Check for unusual formatting patterns that suggest obfuscation attempts.

        Args:
            user_input: The input to analyze

        Returns:
            List of detected patterns
        """
        detected = []

        # Check for excessive mixed case (common in obfuscation)
        mixed_case_ratio = self._calculate_mixed_case_ratio(user_input)
        if mixed_case_ratio > 0.4:  # 40% or more characters are alternating case
            detected.append(
                DetectedPattern(
                    name="Excessive Mixed Case",
                    category="formatting_anomaly",
                    severity="medium",
                    matched_text=user_input[:100],
                    confidence=0.65,
                )
            )
            logger.debug(
                f"Heuristic detected: Excessive mixed case "
                f"(ratio: {mixed_case_ratio:.2f})"
            )

        # Check for leetspeak patterns (numbers/symbols replacing letters)
        # Look for letter-number or number-letter transitions
        # This catches patterns like "3x3cut3", "h4ck", "pr1v"
        leetspeak_matches = re.findall(r"[0-9][a-zA-Z]|[a-zA-Z][0-9]", user_input)
        # Threshold: need at least 5 transitions to flag (avoids false positives from version numbers, etc)
        if len(leetspeak_matches) >= 5:
            detected.append(
                DetectedPattern(
                    name="Leetspeak Patterns",
                    category="formatting_anomaly",
                    severity="medium",
                    matched_text=f"Found {len(leetspeak_matches)} leetspeak substitutions",
                    confidence=0.70,
                )
            )
            logger.debug(f"Heuristic detected: Leetspeak patterns ({len(leetspeak_matches)} matches)")

        # Check for excessive delimiter repetition
        delimiter_repeats = re.findall(r"([\-_=*#]{10,})", user_input)
        if delimiter_repeats:
            detected.append(
                DetectedPattern(
                    name="Excessive Delimiter Repetition",
                    category="formatting_anomaly",
                    severity="low",
                    matched_text=delimiter_repeats[0],
                    confidence=0.55,
                )
            )
            logger.debug(
                f"Heuristic detected: Excessive delimiter repetition "
                f"({len(delimiter_repeats)} occurrences)"
            )

        # Check for unusual whitespace patterns
        unusual_whitespace = re.findall(r"[ \t]{5,}|\r\n\r\n\r\n+|\n\n\n+", user_input)
        if len(unusual_whitespace) >= 3:
            detected.append(
                DetectedPattern(
                    name="Unusual Whitespace Patterns",
                    category="formatting_anomaly",
                    severity="low",
                    matched_text=f"Found {len(unusual_whitespace)} unusual whitespace sequences",
                    confidence=0.50,
                )
            )
            logger.debug(
                f"Heuristic detected: Unusual whitespace patterns "
                f"({len(unusual_whitespace)} occurrences)"
            )

        return detected

    def _check_character_distribution(self, user_input: str) -> list[DetectedPattern]:
        """
        Check for suspicious character distributions.

        Args:
            user_input: The input to analyze

        Returns:
            List of detected patterns
        """
        detected = []

        if not user_input:
            return detected

        # Calculate special character ratio
        total_chars = len(user_input)
        alphanumeric = sum(1 for c in user_input if c.isalnum())
        special_chars = total_chars - alphanumeric

        # High special character ratio is suspicious
        if total_chars > 20:  # Only check for longer inputs
            special_ratio = special_chars / total_chars
            if special_ratio > 0.5:  # More than 50% special characters
                detected.append(
                    DetectedPattern(
                        name="High Special Character Ratio",
                        category="distribution_anomaly",
                        severity="medium",
                        matched_text=f"Special chars: {special_ratio:.1%}",
                        confidence=min(special_ratio * 1.2, 0.90),
                    )
                )
                logger.debug(
                    f"Heuristic detected: High special character ratio "
                    f"({special_ratio:.1%})"
                )

        # Check for unbalanced quotes or brackets
        brackets = {"(": ")", "[": "]", "{": "}", '"': '"', "'": "'"}
        for open_bracket, close_bracket in brackets.items():
            open_count = user_input.count(open_bracket)
            close_count = user_input.count(close_bracket)
            if open_count != close_count:
                detected.append(
                    DetectedPattern(
                        name=f"Unbalanced {open_bracket}{close_bracket}",
                        category="distribution_anomaly",
                        severity="low",
                        matched_text=f"{open_bracket}: {open_count}, {close_bracket}: {close_count}",
                        confidence=0.50,
                    )
                )
                logger.debug(
                    f"Heuristic detected: Unbalanced brackets "
                    f"({open_bracket}: {open_count}, {close_bracket}: {close_count})"
                )

        return detected

    def _check_contextual_anomalies(self, user_input: str) -> list[DetectedPattern]:
        """
        Check for contextual anomalies that suggest malicious intent.

        Args:
            user_input: The input to analyze

        Returns:
            List of detected patterns
        """
        detected = []
        input_lower = user_input.lower()

        # Suspicious keyword combinations
        command_keywords = ["execute", "run", "eval", "system", "shell", "bash"]
        privilege_keywords = ["root", "admin", "sudo", "privilege", "elevated"]
        override_keywords = ["ignore", "override", "bypass", "disable", "restrictions"]

        # Check for command + privilege combinations
        for cmd in command_keywords:
            for priv in privilege_keywords:
                if cmd in input_lower and priv in input_lower:
                    detected.append(
                        DetectedPattern(
                            name="Command + Privilege Combination",
                            category="contextual_anomaly",
                            severity="high",
                            matched_text=f"Found '{cmd}' + '{priv}'",
                            confidence=0.75,
                        )
                    )
                    logger.debug(
                        f"Heuristic detected: Command + privilege combo "
                        f"({cmd} + {priv})"
                    )

        # Check for override + security combinations
        for override in override_keywords:
            if override in input_lower:
                security_terms = ["security", "safety", "filter", "check", "restriction"]
                for sec_term in security_terms:
                    if sec_term in input_lower:
                        detected.append(
                            DetectedPattern(
                                name="Override + Security Combination",
                                category="contextual_anomaly",
                                severity="high",
                                matched_text=f"Found '{override}' + '{sec_term}'",
                                confidence=0.80,
                            )
                        )
                        logger.debug(
                            f"Heuristic detected: Override + security combo "
                            f"({override} + {sec_term})"
                        )

        # Check for suspicious imperative verbs at start of input
        imperative_patterns = [
            "pretend", "imagine", "assume", "suppose", "just act", "simply act",
            "you must", "you shall", "you will", "from now on"
        ]
        for pattern in imperative_patterns:
            if input_lower.startswith(pattern) or input_lower.startswith(f"to {pattern}"):
                detected.append(
                    DetectedPattern(
                        name="Suspicious Imperative",
                        category="contextual_anomaly",
                        severity="medium",
                        matched_text=pattern,
                        confidence=0.65,
                    )
                )
                logger.debug(f"Heuristic detected: Suspicious imperative ('{pattern}')")

        return detected

    def _check_encoding_attempts(self, user_input: str) -> list[DetectedPattern]:
        """
        Check for multiple encoding or obfuscation attempts.

        Args:
            user_input: The input to analyze

        Returns:
            List of detected patterns
        """
        detected = []

        # Count different encoding indicators
        encoding_indicators = []

        # Check for base64-like strings
        if re.search(r"[A-Za-z0-9+/]{20,}={0,2}", user_input):
            encoding_indicators.append("base64")

        # Check for hex encoding
        if re.search(r"(\\x[0-9A-Fa-f]{2}){5,}|(%[0-9A-Fa-f]{2}){5,}", user_input):
            encoding_indicators.append("hex")

        # Check for unicode escapes
        if re.search(r"(\\u[0-9A-Fa-f]{4}){3,}|(\\U[0-9A-Fa-f]{8}){3,}", user_input):
            encoding_indicators.append("unicode")

        # Check for URL encoding
        if re.search(r"(%20|%5B|%5D|%3B|%7B|%7D|%3A){3,}", user_input):
            encoding_indicators.append("url")

        # Multiple encoding types is highly suspicious
        if len(encoding_indicators) >= 2:
            detected.append(
                DetectedPattern(
                    name="Multiple Encoding Types",
                    category="encoding_anomaly",
                    severity="high",
                    matched_text=f"Found: {', '.join(encoding_indicators)}",
                    confidence=0.85,
                )
            )
            logger.debug(
                f"Heuristic detected: Multiple encoding types "
                f"({', '.join(encoding_indicators)})"
            )

        # Check for repeated character substitution patterns
        # (e.g., @ instead of a, 0 instead of o)
        substitutions = {
            "@": "a", "4": "a", "3": "e", "1": "l", "0": "o",
            "5": "s", "$": "s", "7": "t", "9": "g"
        }
        sub_count = sum(user_input.count(old) for old in substitutions.keys())
        if sub_count >= 5:
            detected.append(
                DetectedPattern(
                    name="Character Substitution Patterns",
                    category="encoding_anomaly",
                    severity="medium",
                    matched_text=f"Found {sub_count} substitutions",
                    confidence=0.65,
                )
            )
            logger.debug(
                f"Heuristic detected: Character substitution patterns "
                f"({sub_count} occurrences)"
            )

        return detected

    def _calculate_mixed_case_ratio(self, text: str) -> float:
        """
        Calculate the ratio of mixed-case patterns in text.

        Args:
            text: The text to analyze

        Returns:
            Ratio 0.0-1.0 representing mixed case intensity
        """
        if len(text) < 10:
            return 0.0

        # Count case transitions
        case_transitions = 0
        for i in range(1, len(text)):
            if text[i].isalpha() and text[i-1].isalpha():
                if text[i].islower() != text[i-1].islower():
                    case_transitions += 1

        # Calculate ratio
        max_transitions = len(text) - 1
        if max_transitions == 0:
            return 0.0

        return case_transitions / max_transitions


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


def screen_input(
    user_input: str,
    level: ScreeningLevel | str | None = None,
    project_dir: str | None = None,
) -> ScreeningResult:
    """
    Convenience function to screen user input.

    Args:
        user_input: The content to screen
        level: Screening strictness level (enum or string).
                If None, reads from AUTO_CLAUDE_SCREENING_LEVEL env var.
        project_dir: Project directory for allowlist file (optional)

    Returns:
        ScreeningResult with verdict and details

    Example:
        >>> result = screen_input("Add user authentication")
        >>> if result.is_safe:
        ...     process_input(user_input)
        ...     else:
        ...         print(f"Rejected: {result.reason}")
    """
    screener = InputScreener(level=level, project_dir=project_dir)
    return screener.screen_input(user_input)


def is_input_safe(
    user_input: str,
    level: ScreeningLevel | str | None = None,
    project_dir: str | None = None,
) -> bool:
    """
    Quick check if input is safe.

    Args:
        user_input: The content to screen
        level: Screening strictness level (enum or string).
                If None, reads from AUTO_CLAUDE_SCREENING_LEVEL env var.
        project_dir: Project directory for allowlist file (optional)

    Returns:
        True if input passes screening, False otherwise

    Example:
        >>> if is_input_safe(task_description):
        ...     create_spec(task_description)
    """
    result = screen_input(user_input, level=level, project_dir=project_dir)
    return result.is_safe
