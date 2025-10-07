import os
from flask import Blueprint, render_template
from sqlalchemy import func
from dotenv import load_dotenv

from models.schemas import db, Garage, Floor, FloorStatus

# Load environment variables
load_dotenv()

# Configurable garage name (defaults to Hutson Marsh Griffith Parking)
GARAGE_B_NAME = os.getenv("GARAGE_B_NAME", "Hutson Marsh Griffith Parking")

# Create the Blueprint
bp = Blueprint("garage_b", __name__, url_prefix="/garage-b")

@bp.route("/")
def garage_b_dashboard():
    garage = Garage.query.filter_by(name=GARAGE_B_NAME).first()
    if not garage:
        return (
            f"Garage '{GARAGE_B_NAME}' not found. Seed the database or set GARAGE_B_NAME to an existing garage name.",
            404,
        )

    # Totals
    totals = (
        db.session.query(FloorStatus.vehicle_type, func.sum(FloorStatus.free_spots))
        .join(Floor, FloorStatus.floor_id == Floor.floor_id)
        .filter(Floor.garage_id == garage.garage_id)
        .group_by(FloorStatus.vehicle_type)
        .all()
    )
    totals_dict = {t[0]: t[1] for t in totals}

    # Per-floor snapshot
    floor_statuses = (
        db.session.query(Floor.floor_number, FloorStatus.vehicle_type, FloorStatus.free_spots)
        .join(FloorStatus, Floor.floor_id == FloorStatus.floor_id)
        .filter(Floor.garage_id == garage.garage_id)
        .order_by(Floor.floor_number)
        .all()
    )

    floor_data = {}
    for floor_number, vehicle_type, free_spots in floor_statuses:
        if floor_number not in floor_data:
            floor_data[floor_number] = {"car": 0, "motorcycle": 0}
        floor_data[floor_number][vehicle_type] = free_spots

    # Build context; include up to 4 floors for Garage B
    f = lambda n, vt: floor_data.get(n, {}).get(vt, 0)
    context = {
        "total_cars": totals_dict.get("car", 0),
        "total_motorcycles": totals_dict.get("motorcycle", 0),

        # Floor 1 (optionally keep the same faculty/student split as A)
        "floor1_cars_faculty": f(1, "car") // 2,
        "floor1_cars_student": f(1, "car") - (f(1, "car") // 2),
        "floor1_motorcycles": f(1, "motorcycle"),

        "floor2_cars": f(2, "car"),
        "floor2_motorcycles": f(2, "motorcycle"),

        "floor3_cars": f(3, "car"),
        "floor3_motorcycles": f(3, "motorcycle"),

        "floor4_cars": f(4, "car"),
        "floor4_motorcycles": f(4, "motorcycle"),
    }

    return render_template("garage-b.html", **context)
