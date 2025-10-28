# app.py
import os
from flask import Flask, jsonify
from dotenv import load_dotenv

from models.schemas import db, get_all_current_counts
from models import garage_a, garage_b, garage_c
from models import index as home
from models import About, Feedback

# Load environment variables from .env
load_dotenv()

def create_app():
    # Use the dashboard folder for templates and static files
    app = Flask(
        __name__,
        template_folder="../dashboard",
        static_folder="../dashboard",
        static_url_path="/",
    )

    # Core config
    db_uri = os.getenv("DATABASE_URL")
    if not db_uri:
        raise RuntimeError("DATABASE_URL environment variable must be set")
    app.config["SQLALCHEMY_DATABASE_URI"] = db_uri
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    secret = os.getenv("SECRET_KEY")
    if not secret or secret.lower() in {"dev", "changeme", "default", "secret"}:
        raise RuntimeError("SECRET_KEY must be set to a strong, random value")
    app.config["SECRET_KEY"] = secret

    # Secure session cookie defaults (adjust SAMESITE as needed)
    app.config.update(
        SESSION_COOKIE_SECURE=True,       # requires HTTPS in production
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        PREFERRED_URL_SCHEME="https",
    )

    # Initialize db (bind SQLAlchemy to Flask app) - do NOT create tables here.
    db.init_app(app)

    # Register routes
    app.register_blueprint(home.bp)       # /
    app.register_blueprint(About.bp)      # /about
    app.register_blueprint(Feedback.bp)   # /feedback
    app.register_blueprint(garage_a.bp)   # /garage-a
    app.register_blueprint(garage_b.bp)   # /garage-b
    app.register_blueprint(garage_c.bp)   # /garage-c

    # Simple read-only JSON API for current counts (for polling or SSE clients)
    @app.route("/api/current_counts", methods=["GET"])
    def api_current_counts():
        counts = get_all_current_counts()
        return jsonify([c.to_dict() for c in counts])

    return app

if __name__ == "__main__":
    # For local dev only; rely on a WSGI server (e.g., waitress) in production.
    app = create_app()
    app.run()
