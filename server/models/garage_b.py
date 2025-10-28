import os
from flask import Blueprint, render_template
from dotenv import load_dotenv
from sqlalchemy import func

from models.schemas import db, CurrentCount

load_dotenv()

bp = Blueprint("garage_b", __name__, url_prefix="/garage-b")

def _parse_list_env(name):
    val = os.getenv(name, "")
    return [v.strip() for v in val.split(",") if v.strip()]

def _sum_locations(location_ids):
    if not location_ids:
        return 0
    rows = db.session.query(CurrentCount).filter(CurrentCount.location_id.in_(location_ids)).all()
    return sum((r.count or 0) for r in rows)

@bp.route("/")
def garage_b_dashboard():
    """
    Garage B reads per-floor totals from CurrentCount rows.
    Optional env vars:
      GARAGE_B_FLOOR1_LOCATIONS, GARAGE_B_FLOOR2_LOCATIONS, GARAGE_B_FLOOR3_LOCATIONS, GARAGE_B_FLOOR4_LOCATIONS
      GARAGE_B_TOTAL_LOCATIONS (optional)
    """
    floor1_ids = _parse_list_env("GARAGE_B_FLOOR1_LOCATIONS")
    floor2_ids = _parse_list_env("GARAGE_B_FLOOR2_LOCATIONS")
    floor3_ids = _parse_list_env("GARAGE_B_FLOOR3_LOCATIONS")
    floor4_ids = _parse_list_env("GARAGE_B_FLOOR4_LOCATIONS")
    total_ids = _parse_list_env("GARAGE_B_TOTAL_LOCATIONS")

    floor1_total = _sum_locations(floor1_ids)
    floor2_total = _sum_locations(floor2_ids)
    floor3_total = _sum_locations(floor3_ids)
    floor4_total = _sum_locations(floor4_ids)

    if total_ids:
        total_cars = _sum_locations(total_ids)
    else:
        if any([floor1_ids, floor2_ids, floor3_ids, floor4_ids]):
            total_cars = floor1_total + floor2_total + floor3_total + floor4_total
        else:
            total_cars = db.session.query(func.coalesce(func.sum(CurrentCount.count), 0)).scalar() or 0

    context = {
        "total_cars": total_cars,
        "total_motorcycles": 0,

        "floor1_cars": floor1_total,
        "floor1_motorcycles": 0,

        "floor2_cars": floor2_total,
        "floor2_motorcycles": 0,

        "floor3_cars": floor3_total,
        "floor3_motorcycles": 0,

        "floor4_cars": floor4_total,
        "floor4_motorcycles": 0,
    }

    return render_template("garage-b.html", **context)