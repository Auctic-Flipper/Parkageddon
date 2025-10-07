# app.py
import os
from flask import Flask
from dotenv import load_dotenv

from models.schemas import db
from models import garage_a

# Load environment variables from .env
load_dotenv()

def create_app():
    # Use the dashboard folder for both templates and static files
    # - template_folder: lets render_template("garage-a.html") find dashboard/garage-a.html
    # - static_folder + static_url_path="/": serves /Images/... from dashboard/Images/...
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

    # Register routes from garage_a (and others if you add them)
    app.register_blueprint(garage_a.bp)

    return app

if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        db.create_all()  # ensure tables exist
    app.run(debug=True)
