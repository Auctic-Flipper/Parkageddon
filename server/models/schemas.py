from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, Index

db = SQLAlchemy()

class CurrentCount(db.Model):
    __tablename__ = "current_counts"

    location_id = db.Column(db.String(100), primary_key=True)
    camera_name = db.Column(db.String(200), nullable=False)
    count = db.Column(db.Integer, nullable=False, default=0)
    last_change_type = db.Column(db.String(20))
    last_update = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    def to_dict(self):
        return {
            "location_id": self.location_id,
            "camera_name": self.camera_name,
            "count": self.count,
            "last_change_type": self.last_change_type,
            "last_update": self.last_update.isoformat() if self.last_update else None,
        }

# Optional: We can keep vehicle_events model out if we don't need history in the website.

# ---- Simple read helpers ----

def get_current_count(location_id: str):
    """Return a CurrentCount instance or None."""
    return db.session.get(CurrentCount, location_id)

def get_all_current_counts():
    """Return all CurrentCount rows as a list."""
    return db.session.query(CurrentCount).all()
