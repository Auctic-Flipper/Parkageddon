# app.py
import os
from flask import Flask
from dotenv import load_dotenv

from models.schemas import db  # your models live here
import garage_a         # this imports your garage_a routes

# Load environment variables from .env
load_dotenv()

def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

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

