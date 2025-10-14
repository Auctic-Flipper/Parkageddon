# app.py
import os
from flask import Flask
from dotenv import load_dotenv

from models.schemas import db
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
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")

    # Initialize db
    db.init_app(app)

    # Register routes
    app.register_blueprint(home.bp)       # /
    app.register_blueprint(About.bp)      # /about
    app.register_blueprint(Feedback.bp)   # /feedback

    app.register_blueprint(garage_a.bp)   # /garage-a
    app.register_blueprint(garage_b.bp)   # /garage-b
    app.register_blueprint(garage_c.bp)   # /garage-c

    return app

if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        db.create_all()  # ensure tables exist
    app.run(debug=True)

