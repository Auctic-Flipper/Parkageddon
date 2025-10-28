import os
from flask import Blueprint, render_template
from dotenv import load_dotenv
from sqlalchemy import func

from models.schemas import db, CurrentCount

# Load environment variables
load_dotenv()

# Create the Blueprint (instead of a full Flask app)
bp = Blueprint('garage_a', __name__, url_prefix='/garage-a')

def _parse_list_env(name):
    """Return list of non-empty trimmed values from a comma-separated env var, or [] if not set."""
    val = os.getenv(name, "")
    return [v.strip() for v in val.split(",") if v.strip()]

def _sum_locations(location_ids):
    if not location_ids:
        return 0
    rows = db.session.query(CurrentCount).filter(CurrentCount.location_id.in_(location_ids)).all()
    return sum((r.count or 0) for r in rows)

@bp.route("/")
def garage_a_dashboard():
    """
    Compute totals from CurrentCount rows.
    Configure environment variables to map location_id values to each floor:

    - GARAGE_A_FLOOR1_LOCATIONS=loc1,loc2
    - GARAGE_A_FLOOR2_LOCATIONS=loc3
    - GARAGE_A_FLOOR3_LOCATIONS=loc4,loc5
    - (optional) GARAGE_A_TOTAL_LOCATIONS=loc1,loc2,loc3,loc4,loc5

    If mappings are missing we try a graceful fallback: sum all counts as total and set floors to zero.
    """
    # Read mappings from environment (comma-separated location_ids)
    floor1_ids = _parse_list_env("GARAGE_A_FLOOR1_LOCATIONS")
    floor2_ids = _parse_list_env("GARAGE_A_FLOOR2_LOCATIONS")
    floor3_ids = _parse_list_env("GARAGE_A_FLOOR3_LOCATIONS")
    total_ids = _parse_list_env("GARAGE_A_TOTAL_LOCATIONS")

    # Compute per-floor sums
    floor1_total = _sum_locations(floor1_ids) 
    floor2_total = _sum_locations(floor2_ids) 
    floor3_total = _sum_locations(floor3_ids) 

    # Compute grand total
    if total_ids:
        total_cars = _sum_locations(total_ids)
    else:
        # if no explicit total mapping, sum whatever we have, or sum all rows as fallback
        if any([floor1_ids, floor2_ids, floor3_ids]):
            total_cars = floor1_total + floor2_total + floor3_total
        else:
            # fallback: sum all current_counts
            total_cars = db.session.query(func.coalesce(func.sum(CurrentCount.count), 0)).scalar() or 0

    # NOTE: current_counts schema does not include vehicle type separation (car vs motorcycle).
    # If our data doesn't separate motorcycles by location_id, set motorcycles to 0 (or change mapping).
    # Provide the same faculty/student split for floor1 as previous templates expected.
    floor1_cars_faculty = floor1_total // 2
    floor1_cars_student = floor1_total - floor1_cars_faculty

    context = {
        "total_cars": total_cars,
        "total_motorcycles": 0,  # update if we have separate motorcycle location rows

        "floor1_cars_faculty": floor1_cars_faculty,
        "floor1_cars_student": floor1_cars_student,
        "floor1_motorcycles": 0,

        "floor2_cars": floor2_total,
        "floor2_motorcycles": 0,

        "floor3_cars": floor3_total,
        "floor3_motorcycles": 0,
    }

    return render_template("garage-a.html", **context)
