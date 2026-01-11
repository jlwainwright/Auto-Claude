"""Helper utilities."""
from typing import Any, Dict


def format_response(data: Any, status: str = "success") -> Dict[str, Any]:
    """Format API response."""
    return {"status": status, "data": data}


def validate_email(email: str) -> bool:
    """Validate email address."""
    return "@" in email and "." in email
