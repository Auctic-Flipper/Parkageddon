#!/usr/bin/env python3
import os
from datetime import datetime
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

# Import the project's database object and blueprints (app_jordan structure)
from models.schemas import db, get_all_current_counts
from models import garage_a, garage_b, garage_c
from models import index as home
from models import About, Feedback

# Load .env into environment
load_dotenv()


def create_app():
    """
    Create and configure the Flask application.

    This file merges the routes and behavior from the original app.py
    (vehicle_count API, history, stats, health check) into the
    working app_jordan.py structure and configuration style.
    No database username/password are hard-coded here — the app uses
    DATABASE_URL from the environment (loaded from your .env).
    """
    # App and static/template configuration (same as app_jordan.py)
    app = Flask(
        __name__,
        template_folder="../dashboard",
        static_folder="../dashboard",
        static_url_path="/",
    )

    # Core config loaded from environment (.env)
    db_uri = os.getenv("DATABASE_URL")
    if not db_uri:
        raise RuntimeError("DATABASE_URL environment variable must be set (in .env for local dev)")

    app.config["SQLALCHEMY_DATABASE_URI"] = db_uri
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    secret = os.getenv("SECRET_KEY")
    if not secret or secret.lower() in {"dev", "changeme", "default", "secret"}:
        raise RuntimeError("SECRET_KEY must be set to a strong, random value")
    app.config["SECRET_KEY"] = secret

    # Secure session cookie defaults (adjust SAMESITE as needed)
    app.config.update(
        SESSION_COOKIE_SECURE=True,       # requires HTTPS in production
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        PREFERRED_URL_SCHEME="https",
    )

    # Initialize db (bind SQLAlchemy to Flask app)
    db.init_app(app)

    # Register blueprints (same as app_jordan.py)
    app.register_blueprint(home.bp)       # /
    app.register_blueprint(About.bp)      # /about
    app.register_blueprint(Feedback.bp)   # /feedback
    app.register_blueprint(garage_a.bp)   # /garage-a
    app.register_blueprint(garage_b.bp)   # /garage-b
    app.register_blueprint(garage_c.bp)   # /garage-c

    # -------------------------
    # API Routes (merged)
    # -------------------------

    @app.route("/api/current_counts", methods=["GET"])
    def api_current_counts():
        # Keep compatibility with earlier app_jordan endpoint
        counts = get_all_current_counts()
        return jsonify([c.to_dict() for c in counts])

    @app.route("/vehicle_count", methods=["POST"])
    def receive_count():
        """
        Receive vehicle count updates from edge devices
        Expected JSON (same as original app.py):
        {
            "location_id": "entrance_1",
            "camera_name": "Camera 1 (107)",
            "count": 42,
            "change_type": "increase",
            "track_id": 12345,
            "iso_timestamp": "2025-01-21T14:30:45Z"
        }
        """
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "No data provided"}), 400

        location_id = data.get("location_id")
        camera_name = data.get("camera_name")
        count = data.get("count")
        change_type = data.get("change_type")
        track_id = data.get("track_id")
        iso_timestamp = data.get("iso_timestamp")
        client_ip = request.remote_addr

        if not location_id or count is None or not change_type:
            return jsonify({
                "status": "error",
                "message": "Missing required fields: location_id, count, change_type"
            }), 400

        # Use SQLAlchemy engine/session for DB operations (no hard-coded credentials)
        try:
            # Insert into vehicle_events (log every change)
            insert_event_sql = text("""
                INSERT INTO vehicle_events
                    (location_id, camera_name, count, change_type, track_id, timestamp, received_at)
                VALUES
                    (:location_id, :camera_name, :count, :change_type, :track_id, :timestamp, now())
            """)

            params = {
                "location_id": location_id,
                "camera_name": camera_name,
                "count": count,
                "change_type": change_type,
                "track_id": track_id,
                "timestamp": iso_timestamp
            }

            db.session.execute(insert_event_sql, params)

            # Upsert into current_counts
            upsert_sql = text("""
                INSERT INTO current_counts
                    (location_id, camera_name, count, last_change_type, last_update)
                VALUES
                    (:location_id, :camera_name, :count, :change_type, :timestamp)
                ON CONFLICT (location_id) DO UPDATE SET
                    camera_name = EXCLUDED.camera_name,
                    count = EXCLUDED.count,
                    last_change_type = EXCLUDED.last_change_type,
                    last_update = EXCLUDED.last_update
            """)
            db.session.execute(upsert_sql, params)

            db.session.commit()

            direction = "🔼" if change_type == "increase" else "🔽"
            app.logger.info(f"{direction} {location_id}: count={count} ({change_type}) | track={track_id} | {client_ip}")

            return jsonify({
                "status": "success",
                "message": "Count received and saved",
                "data": {"location_id": location_id, "count": count, "change_type": change_type}
            }), 200

        except SQLAlchemyError as e:
            db.session.rollback()
            app.logger.exception("Database error while saving vehicle_count")
            return jsonify({"status": "error", "message": f"Database error: {str(e)}"}), 500

        except Exception as e:
            db.session.rollback()
            app.logger.exception("Unexpected server error in /vehicle_count")
            return jsonify({"status": "error", "message": f"Server error: {str(e)}"}), 500

    @app.route("/api/current", methods=["GET"])
    def get_current_all():
        """Get current counts for all locations"""
        try:
            q = text("""
                SELECT location_id, camera_name, count, last_change_type, last_update
                FROM current_counts
                ORDER BY location_id
            """)
            result = db.session.execute(q)
            rows = result.mappings().all()

            locations = []
            for row in rows:
                last_update = row["last_update"]
                locations.append({
                    "location_id": row["location_id"],
                    "camera_name": row["camera_name"],
                    "count": row["count"],
                    "last_change_type": row["last_change_type"],
                    "last_update": last_update.isoformat() if last_update else None
                })

            return jsonify({"status": "success", "count": len(locations), "locations": locations}), 200

        except Exception as e:
            app.logger.exception("Error fetching current counts")
            return jsonify({"status": "error", "message": str(e)}), 500

    @app.route("/api/current/<location_id>", methods=["GET"])
    def get_current_location(location_id):
        """Get current count for specific location"""
        try:
            q = text("""
                SELECT location_id, camera_name, count, last_change_type, last_update
                FROM current_counts
                WHERE location_id = :location_id
            """)
            result = db.session.execute(q, {"location_id": location_id})
            row = result.mappings().first()

            if not row:
                return jsonify({"status": "error", "message": f"Location '{location_id}' not found"}), 404

            last_update = row["last_update"]
            return jsonify({
                "status": "success",
                "location_id": row["location_id"],
                "camera_name": row["camera_name"],
                "count": row["count"],
                "last_change_type": row["last_change_type"],
                "last_update": last_update.isoformat() if last_update else None
            }), 200

        except Exception as e:
            app.logger.exception("Error fetching current location")
            return jsonify({"status": "error", "message": str(e)}), 500

    @app.route("/api/history", methods=["GET"])
    def get_history():
        """
        Get event history
        Query params:
            - location_id: filter by location (optional)
            - limit: number of records (default 50, max 500)
        """
        try:
            location_id = request.args.get("location_id")
            try:
                limit = min(int(request.args.get("limit", 50)), 500)
            except ValueError:
                limit = 50

            if location_id:
                q = text("""
                    SELECT event_id, location_id, camera_name, count, change_type,
                           track_id, timestamp, received_at
                    FROM vehicle_events
                    WHERE location_id = :location_id
                    ORDER BY timestamp DESC
                    LIMIT :limit
                """)
                params = {"location_id": location_id, "limit": limit}
            else:
                q = text("""
                    SELECT event_id, location_id, camera_name, count, change_type,
                           track_id, timestamp, received_at
                    FROM vehicle_events
                    ORDER BY timestamp DESC
                    LIMIT :limit
                """)
                params = {"limit": limit}

            result = db.session.execute(q, params)
            rows = result.mappings().all()

            events = []
            for row in rows:
                events.append({
                    "event_id": row["event_id"],
                    "location_id": row["location_id"],
                    "camera_name": row["camera_name"],
                    "count": row["count"],
                    "change_type": row["change_type"],
                    "track_id": row["track_id"],
                    "timestamp": row["timestamp"].isoformat() if row["timestamp"] else None,
                    "received_at": row["received_at"].isoformat() if row["received_at"] else None
                })

            return jsonify({"status": "success", "count": len(events), "events": events}), 200

        except Exception as e:
            app.logger.exception("Error fetching history")
            return jsonify({"status": "error", "message": str(e)}), 500

    @app.route("/api/stats", methods=["GET"])
    def get_stats():
        """Get today's statistics (entries/exits per location)"""
        try:
            q = text("""
                SELECT
                    location_id,
                    COUNT(*) as total_events,
                    SUM(CASE WHEN change_type = 'increase' THEN 1 ELSE 0 END) as entries,
                    SUM(CASE WHEN change_type = 'decrease' THEN 1 ELSE 0 END) as exits,
                    MIN(timestamp) as first_event,
                    MAX(timestamp) as last_event
                FROM vehicle_events
                WHERE timestamp >= CURRENT_DATE
                GROUP BY location_id
                ORDER BY location_id
            """)
            result = db.session.execute(q)
            rows = result.mappings().all()

            stats = []
            for row in rows:
                stats.append({
                    "location_id": row["location_id"],
                    "total_events": int(row["total_events"]),
                    "entries": int(row["entries"]),
                    "exits": int(row["exits"]),
                    "first_event": row["first_event"].isoformat() if row["first_event"] else None,
                    "last_event": row["last_event"].isoformat() if row["last_event"] else None
                })

            return jsonify({"status": "success", "date": datetime.now().date().isoformat(), "locations": stats}), 200

        except Exception as e:
            app.logger.exception("Error fetching stats")
            return jsonify({"status": "error", "message": str(e)}), 500

    @app.route("/health", methods=["GET"])
    def health_check():
        """Check server and database health"""
        try:
            # simple query to validate DB connectivity
            db.session.execute(text("SELECT 1"))
            return jsonify({
                "status": "healthy",
                "server": "ok",
                "database": "ok",
                "timestamp": datetime.now().isoformat()
            }), 200
        except Exception as e:
            app.logger.exception("Health check failed")
            return jsonify({
                "status": "unhealthy",
                "server": "ok",
                "database": f"error: {str(e)}"
            }), 503

    return app


if __name__ == "__main__":
    # Local dev: create and run app. In production, use a WSGI server.
    application = create_app()

    # Show non-sensitive startup info (do NOT print DB password)
    print("\n" + "=" * 70)
    print("PARKING COUNTER SERVER STARTING")
    print("=" * 70)
    print("Server listening on all interfaces (0.0.0.0) port 5000 (dev run)")
    print("Database configured via DATABASE_URL environment variable")
    print("Endpoints:")
    print("  POST   /vehicle_count           - Receive count updates")
    print("  GET    /api/current             - All current counts")
    print("  GET    /api/current/<location>  - Specific location count")
    print("  GET    /api/history             - Event history")
    print("  GET    /api/stats               - Today's statistics")
    print("  GET    /health                  - Health check")
    print("  GET    /                        - API documentation (dashboard)")
    print("=" * 70 + "\n")

    # Quick DB smoke test before starting the dev server
    try:
        with application.app_context():
            db.session.execute(text("SELECT 1"))
        print("✓ Database connection successful (via DATABASE_URL)")
    except Exception as e:
        print(f"✗ Database connection failed: {e}")
        raise

    application.run(host="0.0.0.0", port=5000, debug=True)