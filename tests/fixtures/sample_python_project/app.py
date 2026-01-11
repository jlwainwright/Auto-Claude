"""Main Flask application."""
from flask import Flask
from models.user import User
from services.auth_service import AuthService

app = Flask(__name__)
auth_service = AuthService()


@app.route("/")
def index():
    """Home page."""
    return "Hello World"


@app.route("/login", methods=["POST"])
def login():
    """Login route."""
    return auth_service.login()


if __name__ == "__main__":
    app.run(debug=True)
