"""Authentication service."""
from typing import Optional
from models.user import User


class AuthService:
    """Authentication service."""

    def __init__(self):
        """Initialize auth service."""
        self.users: dict[str, User] = {}

    def login(self) -> dict:
        """Login user."""
        return {"status": "ok", "message": "Logged in"}

    def register(self, username: str, email: str) -> User:
        """Register new user."""
        user = User(username, email)
        self.users[email] = user
        return user

    def get_user(self, email: str) -> Optional[User]:
        """Get user by email."""
        return self.users.get(email)
