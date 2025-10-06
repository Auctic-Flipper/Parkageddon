from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func

db = SQLAlchemy()

class Garage(db.Model):
    __tablename__ = "garages"
    garage_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    floors = db.relationship("Floor", backref="garage", cascade="all, delete-orphan")

class Floor(db.Model):
    __tablename__ = "floors"
    floor_id = db.Column(db.Integer, primary_key=True)
    garage_id = db.Column(db.Integer, db.ForeignKey("garages.garage_id"), nullable=False)
    floor_number = db.Column(db.Integer, nullable=False)
    floor_name = db.Column(db.String(50))
    statuses = db.relationship("FloorStatus", backref="floor", cascade="all, delete-orphan")

class FloorStatus(db.Model):
    __tablename__ = "floor_status"
    floor_id = db.Column(db.Integer, db.ForeignKey("floors.floor_id"), primary_key=True)
    vehicle_type = db.Column(db.String(20), primary_key=True)
    total_spots = db.Column(db.Integer, nullable=False, default=0)
    free_spots = db.Column(db.Integer, nullable=False, default=0)
    last_updated = db.Column(db.DateTime, server_default=func.now(), onupdate=func.now())

class FloorHistory(db.Model):
    __tablename__ = "floor_history"
    history_id = db.Column(db.Integer, primary_key=True)
    floor_id = db.Column(db.Integer, db.ForeignKey("floors.floor_id"), nullable=False)
    vehicle_type = db.Column(db.String(20), nullable=False)
    total_spots = db.Column(db.Integer, nullable=False)
    free_spots = db.Column(db.Integer, nullable=False)
    recorded_at = db.Column(db.DateTime, server_default=func.now())
