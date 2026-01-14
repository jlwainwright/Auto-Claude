"""User model."""
from datetime import datetime
from typing import Optional


class User:
    """User model."""

    def __init__(self, username: str, email: str):
        """Initialize user."""
        self.username = username
        self.email = email
        self.created_at = datetime.now()

    def save(self):
        """Save user to database."""
        # Database logic here
        pass

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "username": self.username,
            "email": self.email,
            "created_at": self.created_at.isoformat(),
        }
