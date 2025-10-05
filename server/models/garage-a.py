# garage_a.py
from flask import Flask, render_template
import psycopg2
import psycopg2.extras

app = Flask(__name__)

# Adjust with your actual database credentials
DB_CONFIG = {
    "dbname": "parkageddon",
    "user": "postgres",
    "password": "yourpassword",
    "host": "localhost",
    "port": 5432,
}

def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)

@app.route("/garage-a")
def garage_a_dashboard():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # Query total free cars and motorcycles for Fields Parking
    cur.execute("""
        SELECT fs.vehicle_type, SUM(fs.free_spots) AS free
        FROM floor_status fs
        JOIN floors f ON fs.floor_id = f.floor_id
        JOIN garages g ON f.garage_id = g.garage_id
        WHERE g.name = 'Fields Parking'
        GROUP BY fs.vehicle_type;
    """)
    totals = {row["vehicle_type"]: row["free"] for row in cur.fetchall()}

    # Query per-floor breakdown
    cur.execute("""
        SELECT f.floor_number, fs.vehicle_type, fs.free_spots
        FROM floor_status fs
        JOIN floors f ON fs.floor_id = f.floor_id
        JOIN garages g ON f.garage_id = g.garage_id
        WHERE g.name = 'Fields Parking'
        ORDER BY f.floor_number;
    """)
    floor_data = {}
    for row in cur.fetchall():
        floor = row["floor_number"]
        if floor not in floor_data:
            floor_data[floor] = {"car": 0, "motorcycle": 0}
        floor_data[floor][row["vehicle_type"]] = row["free_spots"]

    cur.close()
    conn.close()

    # Map values into template variables
    context = {
        "total_cars": totals.get("car", 0),
        "total_motorcycles": totals.get("motorcycle", 0),

        # Floor 1: example splitting into faculty/student
        # For now, assume half faculty / half student until you add more logic
        "floor1_cars_faculty": floor_data.get(1, {}).get("car", 0) // 2,
        "floor1_cars_student": floor_data.get(1, {}).get("car", 0) - (floor_data.get(1, {}).get("car", 0) // 2),
        "floor1_motorcycles": floor_data.get(1, {}).get("motorcycle", 0),

        "floor2_cars": floor_data.get(2, {}).get("car", 0),
        "floor2_motorcycles": floor_data.get(2, {}).get("motorcycle", 0),

        "floor3_cars": floor_data.get(3, {}).get("car", 0),
        "floor3_motorcycles": floor_data.get(3, {}).get("motorcycle", 0),
    }

    return render_template("garage-a.html", **context)

if __name__ == "__main__":
    app.run(debug=True)
