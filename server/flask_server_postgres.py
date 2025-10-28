from flask import Flask, request, jsonify
from datetime import datetime
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
import sys

app = Flask(__name__)

# =========================
# Database Configuration
# =========================
DB_CONFIG = {
    'host': 'localhost',
    'database': 'parking_db',
    'user': 'parking_user',
    'password': 'YourSecurePassword123',  # CHANGE THIS!
    'port': 5432
}

# Create connection pool for efficient database connections
try:
    db_pool = psycopg2.pool.SimpleConnectionPool(
        1,  # Min connections
        20,  # Max connections
        **DB_CONFIG
    )
    if db_pool:
        print("✓ Database connection pool created successfully")
except Exception as e:
    print(f"✗ Error creating database connection pool: {e}")
    sys.exit(1)


def get_db_connection():
    """Get a connection from the pool"""
    try:
        return db_pool.getconn()
    except Exception as e:
        print(f"Error getting database connection: {e}")
        return None


def release_db_connection(conn):
    """Return connection to the pool"""
    if conn:
        db_pool.putconn(conn)


# =========================
# Routes
# =========================

@app.route('/')
def home():
    """Home page - API documentation"""
    return """
    <html>
    <head>
        <title>Parking Counter API</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; }
            h1 { color: #2c3e50; }
            .endpoint { background: #ecf0f1; padding: 15px; margin: 10px 0; border-radius: 5px; }
            .method { color: #27ae60; font-weight: bold; }
            code { background: #34495e; color: #ecf0f1; padding: 2px 6px; border-radius: 3px; }
        </style>
    </head>
    <body>
        <h1>🅿️ Parking Counter API Server</h1>
        <p>Server is running on port 5000</p>
        
        <h2>Available Endpoints:</h2>
        
        <div class="endpoint">
            <span class="method">POST</span> <code>/vehicle_count</code><br>
            Receive count updates from edge devices
        </div>
        
        <div class="endpoint">
            <span class="method">GET</span> <code>/api/current</code><br>
            Get current counts for all locations
        </div>
        
        <div class="endpoint">
            <span class="method">GET</span> <code>/api/current/&lt;location_id&gt;</code><br>
            Get current count for specific location
        </div>
        
        <div class="endpoint">
            <span class="method">GET</span> <code>/api/history</code><br>
            Get recent event history (optional: ?location_id=entrance_1&limit=50)
        </div>
        
        <div class="endpoint">
            <span class="method">GET</span> <code>/api/stats</code><br>
            Get today's statistics (entries/exits per location)
        </div>
        
        <div class="endpoint">
            <span class="method">GET</span> <code>/health</code><br>
            Check server and database health
        </div>
    </body>
    </html>
    """


@app.route('/vehicle_count', methods=['POST'])
def receive_count():
    """
    Receive vehicle count updates from edge devices
    Expected JSON format:
    {
        "location_id": "entrance_1",
        "camera_name": "Camera 1 (107)",
        "count": 42,
        "change_type": "increase",
        "track_id": 12345,
        "iso_timestamp": "2025-01-21T14:30:45Z"
    }
    """
    conn = None
    cursor = None
    
    try:
        # Get JSON data from request
        data = request.get_json()
        
        if not data:
            return jsonify({
                "status": "error",
                "message": "No data provided"
            }), 400
        
        # Extract required fields
        location_id = data.get('location_id')
        camera_name = data.get('camera_name')
        count = data.get('count')
        change_type = data.get('change_type')
        track_id = data.get('track_id')
        timestamp = data.get('iso_timestamp')
        client_ip = request.remote_addr
        
        # Validate required fields
        if not location_id or count is None or not change_type:
            return jsonify({
                "status": "error",
                "message": "Missing required fields: location_id, count, change_type"
            }), 400
        
        # Get database connection
        conn = get_db_connection()
        if not conn:
            return jsonify({
                "status": "error",
                "message": "Database connection failed"
            }), 500
        
        cursor = conn.cursor()
        
        # Insert into vehicle_events (log every change)
        cursor.execute('''
            INSERT INTO vehicle_events 
            (location_id, camera_name, count, change_type, track_id, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s)
        ''', (location_id, camera_name, count, change_type, track_id, timestamp))
        
        # Update current_counts (upsert - insert or update)
        cursor.execute('''
            INSERT INTO current_counts 
            (location_id, camera_name, count, last_change_type, last_update)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (location_id) DO UPDATE SET
                camera_name = EXCLUDED.camera_name,
                count = EXCLUDED.count,
                last_change_type = EXCLUDED.last_change_type,
                last_update = EXCLUDED.last_update
        ''', (location_id, camera_name, count, change_type, timestamp))
        
        # Commit changes
        conn.commit()
        
        # Log to console
        direction = "🔼" if change_type == 'increase' else "🔽"
        print(f"{direction} {location_id}: count={count} ({change_type}) | track={track_id} | {client_ip}")
        
        # Return success
        return jsonify({
            "status": "success",
            "message": "Count received and saved",
            "data": {
                "location_id": location_id,
                "count": count,
                "change_type": change_type
            }
        }), 200
        
    except psycopg2.Error as e:
        if conn:
            conn.rollback()
        print(f"✗ Database error: {e}")
        return jsonify({
            "status": "error",
            "message": f"Database error: {str(e)}"
        }), 500
        
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"✗ Server error: {e}")
        return jsonify({
            "status": "error",
            "message": f"Server error: {str(e)}"
        }), 500
        
    finally:
        if cursor:
            cursor.close()
        if conn:
            release_db_connection(conn)


@app.route('/api/current', methods=['GET'])
def get_current_all():
    """Get current counts for all locations"""
    conn = None
    cursor = None
    
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({
                "status": "error",
                "message": "Database connection failed"
            }), 500
        
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute('''
            SELECT location_id, camera_name, count, last_change_type, last_update
            FROM current_counts
            ORDER BY location_id
        ''')
        
        results = cursor.fetchall()
        
        # Convert to list of dicts
        locations = []
        for row in results:
            locations.append({
                'location_id': row['location_id'],
                'camera_name': row['camera_name'],
                'count': row['count'],
                'last_change_type': row['last_change_type'],
                'last_update': row['last_update'].isoformat() if row['last_update'] else None
            })
        
        return jsonify({
            "status": "success",
            "count": len(locations),
            "locations": locations
        }), 200
        
    except Exception as e:
        print(f"✗ Error: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
        
    finally:
        if cursor:
            cursor.close()
        if conn:
            release_db_connection(conn)


@app.route('/api/current/<location_id>', methods=['GET'])
def get_current_location(location_id):
    """Get current count for specific location"""
    conn = None
    cursor = None
    
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({
                "status": "error",
                "message": "Database connection failed"
            }), 500
        
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute('''
            SELECT location_id, camera_name, count, last_change_type, last_update
            FROM current_counts
            WHERE location_id = %s
        ''', (location_id,))
        
        result = cursor.fetchone()
        
        if not result:
            return jsonify({
                "status": "error",
                "message": f"Location '{location_id}' not found"
            }), 404
        
        return jsonify({
            "status": "success",
            "location_id": result['location_id'],
            "camera_name": result['camera_name'],
            "count": result['count'],
            "last_change_type": result['last_change_type'],
            "last_update": result['last_update'].isoformat() if result['last_update'] else None
        }), 200
        
    except Exception as e:
        print(f"✗ Error: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
        
    finally:
        if cursor:
            cursor.close()
        if conn:
            release_db_connection(conn)


@app.route('/api/history', methods=['GET'])
def get_history():
    """
    Get event history
    Query params:
        - location_id: filter by location (optional)
        - limit: number of records (default 50, max 500)
    """
    conn = None
    cursor = None
    
    try:
        # Get query parameters
        location_id = request.args.get('location_id')
        limit = min(int(request.args.get('limit', 50)), 500)
        
        conn = get_db_connection()
        if not conn:
            return jsonify({
                "status": "error",
                "message": "Database connection failed"
            }), 500
        
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Build query based on filters
        if location_id:
            cursor.execute('''
                SELECT event_id, location_id, camera_name, count, change_type, 
                       track_id, timestamp, received_at
                FROM vehicle_events
                WHERE location_id = %s
                ORDER BY timestamp DESC
                LIMIT %s
            ''', (location_id, limit))
        else:
            cursor.execute('''
                SELECT event_id, location_id, camera_name, count, change_type, 
                       track_id, timestamp, received_at
                FROM vehicle_events
                ORDER BY timestamp DESC
                LIMIT %s
            ''', (limit,))
        
        results = cursor.fetchall()
        
        # Convert to list of dicts
        events = []
        for row in results:
            events.append({
                'event_id': row['event_id'],
                'location_id': row['location_id'],
                'camera_name': row['camera_name'],
                'count': row['count'],
                'change_type': row['change_type'],
                'track_id': row['track_id'],
                'timestamp': row['timestamp'].isoformat() if row['timestamp'] else None,
                'received_at': row['received_at'].isoformat() if row['received_at'] else None
            })
        
        return jsonify({
            "status": "success",
            "count": len(events),
            "events": events
        }), 200
        
    except Exception as e:
        print(f"✗ Error: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
        
    finally:
        if cursor:
            cursor.close()
        if conn:
            release_db_connection(conn)


@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get today's statistics (entries/exits per location)"""
    conn = None
    cursor = None
    
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({
                "status": "error",
                "message": "Database connection failed"
            }), 500
        
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute('''
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
        ''')
        
        results = cursor.fetchall()
        
        stats = []
        for row in results:
            stats.append({
                'location_id': row['location_id'],
                'total_events': row['total_events'],
                'entries': row['entries'],
                'exits': row['exits'],
                'first_event': row['first_event'].isoformat() if row['first_event'] else None,
                'last_event': row['last_event'].isoformat() if row['last_event'] else None
            })
        
        return jsonify({
            "status": "success",
            "date": datetime.now().date().isoformat(),
            "locations": stats
        }), 200
        
    except Exception as e:
        print(f"✗ Error: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
        
    finally:
        if cursor:
            cursor.close()
        if conn:
            release_db_connection(conn)


@app.route('/health', methods=['GET'])
def health_check():
    """Check server and database health"""
    conn = None
    cursor = None
    
    try:
        # Test database connection
        conn = get_db_connection()
        if not conn:
            return jsonify({
                "status": "unhealthy",
                "server": "ok",
                "database": "error"
            }), 503
        
        cursor = conn.cursor()
        cursor.execute('SELECT 1')
        cursor.fetchone()
        
        return jsonify({
            "status": "healthy",
            "server": "ok",
            "database": "ok",
            "timestamp": datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        return jsonify({
            "status": "unhealthy",
            "server": "ok",
            "database": f"error: {str(e)}"
        }), 503
        
    finally:
        if cursor:
            cursor.close()
        if conn:
            release_db_connection(conn)


# =========================
# Startup
# =========================

if __name__ == '__main__':
    print("\n" + "="*70)
    print("PARKING COUNTER SERVER STARTING")
    print("="*70)
    print(f"Server IP: 192.168.1.13 (listening on all interfaces)")
    print(f"Port: 5000")
    print(f"Database: {DB_CONFIG['database']} @ {DB_CONFIG['host']}")
    print("\nEndpoints:")
    print("  POST   /vehicle_count           - Receive count updates")
    print("  GET    /api/current             - All current counts")
    print("  GET    /api/current/<location>  - Specific location count")
    print("  GET    /api/history             - Event history")
    print("  GET    /api/stats               - Today's statistics")
    print("  GET    /health                  - Health check")
    print("  GET    /                        - API documentation")
    print("="*70 + "\n")
    
    # Test database connection on startup
    test_conn = get_db_connection()
    if test_conn:
        print("✓ Database connection successful")
        release_db_connection(test_conn)
    else:
        print("✗ Database connection failed - check DB_CONFIG")
        sys.exit(1)
    
    print("\nServer ready! Waiting for requests...\n")
    
    # Run Flask server
    app.run(
        host='0.0.0.0',  # Listen on all interfaces
        port=5000,
        debug=True       # Set to False in production
    )