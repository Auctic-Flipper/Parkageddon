import os
from flask import Blueprint, render_template
from sqlalchemy import func
from dotenv import load_dotenv

from models.schemas import db, Garage, Floor, FloorStatus

# Load environment variables
load_dotenv()

# Create the Blueprint (instead of a full Flask app)
bp = Blueprint('garage_a', __name__, url_prefix='/garage-a')

@bp.route("/")
def garage_a_dashboard():
    garage = Garage.query.filter_by(name="Fields Parking").first()

    # Totals
    totals = (
        db.session.query(FloorStatus.vehicle_type, func.sum(FloorStatus.free_spots))
        .join(Floor)
        .filter(Floor.garage_id == garage.garage_id)
        .group_by(FloorStatus.vehicle_type)
        .all()
    )
    totals_dict = {t[0]: t[1] for t in totals}

    # Per-floor
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

    context = {
        "total_cars": totals_dict.get("car", 0),
        "total_motorcycles": totals_dict.get("motorcycle", 0),

        "floor1_cars_faculty": floor_data.get(1, {}).get("car", 0) // 2,
        "floor1_cars_student": floor_data.get(1, {}).get("car", 0) - (floor_data.get(1, {}).get("car", 0) // 2),
        "floor1_motorcycles": floor_data.get(1, {}).get("motorcycle", 0),

        "floor2_cars": floor_data.get(2, {}).get("car", 0),
        "floor2_motorcycles": floor_data.get(2, {}).get("motorcycle", 0),

        "floor3_cars": floor_data.get(3, {}).get("car", 0),
        "floor3_motorcycles": floor_data.get(3, {}).get("motorcycle", 0),
    }

    return render_template("garage-a.html", **context)
