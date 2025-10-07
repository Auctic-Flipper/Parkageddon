# app.py
import os
from flask import Flask
from dotenv import load_dotenv

from models.schemas import db
from models import garage_a
from models import garage_b
from models import garage_c  # NEW

# Load environment variables from .env
load_dotenv()

def create_app():
    # Use the dashboard folder for templates and static files
    # Serves /Images/... etc. from the same folder so existing paths work
    app = Flask(
        __name__,
        template_folder="../dashboard",
        static_folder="../dashboard",
        static_url_path="/",
    )

    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Initialize db
    db.init_app(app)

    # Register routes
    app.register_blueprint(garage_a.bp)
    app.register_blueprint(garage_b.bp)
    app.register_blueprint(garage_c.bp)  # NEW

    return app

if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        db.create_all()  # ensure tables exist
    app.run(debug=True)
