#!/usr/bin/env python3
"""
Vehicle Counter - Camera 2 Crash Fix
FIXES: Camera crashes immediately after "Connected" message
ROOT CAUSE: Window creation conflicts, GPU memory conflicts, OpenCV threading issues
"""

import cv2
import numpy as np
from ultralytics import YOLO
import torch
import threading
from queue import Queue
import time
import os
import sys
import psycopg2
from psycopg2 import pool

# ============================================================================
# CRITICAL FIXES FOR CAMERA 2 CRASH
# ============================================================================

# 1. Force single-threaded OpenCV (prevents threading conflicts)
cv2.setNumThreads(1)

# 2. Force X11 (no Wayland)
os.environ['QT_QPA_PLATFORM'] = 'xcb'
os.environ['QT_X11_NO_MITSHM'] = '1'
os.environ['GDK_BACKEND'] = 'x11'

# 3. Disable OpenMP threading (critical for multi-camera)
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'

# 4. GPU settings
os.environ['CUDA_VISIBLE_DEVICES'] = '0'
os.environ['CUDA_LAUNCH_BLOCKING'] = '1'

# 5. Disable OpenCV's own threading
os.environ['OPENCV_VIDEOIO_PRIORITY_FFMPEG'] = '1'

print("✓ Environment configured for multi-camera stability")

# ============================================================================
# DATABASE CONFIGURATION
# ============================================================================
DB_HOST = 'localhost'
DB_NAME = 'Parkageddon'
DB_USER = 'postgres'
DB_PASSWORD = 'Blue-Gold-Dress2025!'  # CHANGE THIS
DB_PORT = 5432

# ============================================================================
# CAMERA CONFIGURATIONS
# ============================================================================
CAMERAS = [
    {
        'name': 'Camera 1 (107)',
        'ip': '192.168.1.107',
        'username': 'admin',
        'password': 'Golddoor99!',
        'port': 554,
        'location_id': 'main_garage',
        'window_x': 0,      # Window position
        'window_y': 0
    },
    {
        'name': 'Camera 2 (108)',
        'ip': '192.168.1.108',
        'username': 'admin',
        'password': 'Golddoor99!',
        'port': 554,
        'location_id': 'main_garage',
        'window_x': 1220,   # Window position (side by side)
        'window_y': 0
    }
]

# Configuration
PROCESS_EVERY_N_FRAMES = 2
MAX_TRACK_AGE = 300

# ============================================================================
# GLOBAL VARIABLES - DECLARED HERE BEFORE ANY CLASSES
# ============================================================================
global_running = True
camera_ready_lock = threading.Lock()
camera_1_ready = threading.Event()

# ============================================================================
# GPU SETUP
# ============================================================================
def setup_gpu():
    """Setup GPU with safety checks"""
    print("\n" + "="*70)
    print("GPU DETECTION")
    print("="*70)
    
    if torch.cuda.is_available():
        print(f"✓ CUDA available")
        print(f"✓ GPU Count: {torch.cuda.device_count()}")
        
        gpu_idx = 0
        for i in range(torch.cuda.device_count()):
            gpu_name = torch.cuda.get_device_name(i)
            print(f"  GPU {i}: {gpu_name}")
            if '4070' in gpu_name:
                gpu_idx = i
        
        torch.cuda.set_device(gpu_idx)
        print(f"✓ Using GPU {gpu_idx}: {torch.cuda.get_device_name(gpu_idx)}")
        print("="*70 + "\n")
        return f'cuda:{gpu_idx}', gpu_idx
    else:
        print("✗ CUDA not available - using CPU")
        print("="*70 + "\n")
        return 'cpu', 'cpu'

device, device_id = setup_gpu()

# ============================================================================
# SHARED COUNTER
# ============================================================================
class SharedCounter:
    """Thread-safe counter for multi-camera sync"""
    def __init__(self, initial_count=0):
        self.count = initial_count
        self.lock = threading.Lock()
    
    def increment(self):
        with self.lock:
            self.count += 1
            return self.count
    
    def decrement(self):
        with self.lock:
            self.count -= 1
            return self.count
    
    def get(self):
        with self.lock:
            return self.count
    
    def set(self, value):
        with self.lock:
            self.count = value
            return self.count

# ============================================================================
# DATABASE WRITER
# ============================================================================
class DatabaseWriter:
    """Database writer with retry logic"""
    def __init__(self, camera_name, location_id):
        self.camera_name = camera_name
        self.location_id = location_id
        
        try:
            self.db_pool = psycopg2.pool.SimpleConnectionPool(
                1, 3,
                host=DB_HOST,
                database=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD,
                port=DB_PORT,
                connect_timeout=5
            )
        except Exception as e:
            print(f"[{camera_name}] ✗ DB connection failed: {e}")
            self.db_pool = None
        
        self.successful_writes = 0
        self.failed_writes = 0
    
    def write_count_change(self, count, change_type, track_id):
        """Write to database"""
        if not self.db_pool:
            return
        
        conn = None
        try:
            conn = self.db_pool.getconn()
            cursor = conn.cursor()
            
            timestamp = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            
            cursor.execute('''
                INSERT INTO vehicle_events 
                (location_id, camera_name, count, change_type, track_id, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s)
            ''', (self.location_id, self.camera_name, count, change_type, track_id, timestamp))
            
            cursor.execute('''
                INSERT INTO current_counts 
                (location_id, camera_name, count, last_change_type, last_update)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (location_id) DO UPDATE SET
                    camera_name = EXCLUDED.camera_name,
                    count = EXCLUDED.count,
                    last_change_type = EXCLUDED.last_change_type,
                    last_update = EXCLUDED.last_update
            ''', (self.location_id, self.camera_name, count, change_type, timestamp))
            
            conn.commit()
            cursor.close()
            self.successful_writes += 1
        except Exception as e:
            if conn:
                conn.rollback()
            self.failed_writes += 1
        finally:
            if conn:
                self.db_pool.putconn(conn)
    
    def get_stats(self):
        return {'successful': self.successful_writes, 'failed': self.failed_writes, 'pending': 0}
    
    def shutdown(self):
        if self.db_pool:
            self.db_pool.closeall()

# ============================================================================
# CAMERA PROCESSOR - WITH CRASH FIXES
# ============================================================================
class CameraProcessor:
    """Camera processor with crash prevention"""
    
    def __init__(self, camera_config, camera_index, shared_counter=None):
        self.config = camera_config
        self.index = camera_index
        self.name = camera_config['name']
        self.shared_counter = shared_counter
        
        print(f"\n[{self.name}] Initializing processor...")
        
        # Database
        self.db_writer = DatabaseWriter(self.name, camera_config.get('location_id', f'camera_{camera_index}'))
        
        # Device selection - CRITICAL FIX: Only Camera 1 uses GPU
        global device_id, device
        if camera_index == 0 and torch.cuda.is_available():
            self.device = device
            self.device_id = device_id
            print(f"[{self.name}] Using GPU")
        else:
            self.device = 'cpu'
            self.device_id = 'cpu'
            print(f"[{self.name}] Using CPU (prevents crashes)")
        
        # CRITICAL FIX: Load model BEFORE connecting to camera
        print(f"[{self.name}] Loading YOLO model on {self.device}...")
        try:
            self.model = YOLO("yolov8n.pt")
            if self.device != 'cpu':
                self.model.to(self.device)
            print(f"[{self.name}] ✓ Model loaded successfully")
        except Exception as e:
            print(f"[{self.name}] ✗ Model loading failed: {e}")
            raise
        
        # Stream variables
        self.cap = None
        self.working_url = None
        self.frame_count = 0
        self.failed_frame_count = 0
        self.max_failed_frames = 100
        
        # Counting
        self.count_increases = 0
        self.count_decreases = 0
        self.track_states = {}
        
        # UI
        self.frame_width = 1920
        self.frame_height = 1080
        self.center_y = self.frame_height // 2
        self.line_spacing = 80
        self.left_limit = 200
        self.right_limit = self.frame_width - 200
        self.line_tolerance = 25
        self.limit_step = 10
        
        self.window_name = f"{self.name} - Vehicle Counter"
        self.running = True
        
        self.update_lines()
        print(f"[{self.name}] ✓ Processor initialized")
    
    def update_lines(self):
        """Update line positions"""
        self.line1_y = self.center_y - self.line_spacing
        self.line2_y = self.center_y
        self.line3_y = self.center_y + self.line_spacing
        
        self.line1_start = (0, self.line1_y)
        self.line1_end = (self.frame_width, self.line1_y)
        self.line2_start = (0, self.line2_y)
        self.line2_end = (self.frame_width, self.line2_y)
        self.line3_start = (0, self.line3_y)
        self.line3_end = (self.frame_width, self.line3_y)
    
    def create_capture(self, url):
        """Create video capture with stability settings"""
        # CRITICAL: Use TCP and add error tolerance
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
            "rtsp_transport;tcp|"
            "max_delay;5000000|"
            "reorder_queue_size;0|"
            "fflags;nobuffer+discardcorrupt|"
            "flags;low_delay"
        )
        
        cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        cap.set(cv2.CAP_PROP_FPS, 30)
        
        return cap
    
    def connect_camera(self):
        """Connect to RTSP stream"""
        rtsp_urls = [
            f"rtsp://{self.config['username']}:{self.config['password']}@{self.config['ip']}:{self.config['port']}/11",
            f"rtsp://{self.config['username']}:{self.config['password']}@{self.config['ip']}:{self.config['port']}/12",
            f"rtsp://{self.config['username']}:{self.config['password']}@{self.config['ip']}:{self.config['port']}/Streaming/Channels/101",
        ]
        
        print(f"[{self.name}] Connecting to camera...")
        
        for rtsp_url in rtsp_urls:
            try:
                masked_url = rtsp_url.replace(self.config['password'], '****')
                print(f"[{self.name}] Trying: {masked_url}")
                
                test_cap = self.create_capture(rtsp_url)
                ret, test_frame = test_cap.read()
                
                if ret and test_frame is not None:
                    print(f"[{self.name}] ✓ Connected!")
                    self.cap = test_cap
                    self.working_url = rtsp_url
                    self.frame_height, self.frame_width = test_frame.shape[:2]
                    self.center_y = self.frame_height // 2
                    self.left_limit = self.frame_width // 6
                    self.right_limit = self.frame_width * 5 // 6
                    self.update_lines()
                    return True
                else:
                    test_cap.release()
            except Exception as e:
                print(f"[{self.name}] Connection attempt failed: {e}")
                continue
        
        print(f"[{self.name}] ✗ Failed to connect")
        return False
    
    def is_vehicle_class(self, class_id):
        return class_id in [2, 3, 5, 7]
    
    def get_vehicle_name(self, class_id):
        names = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}
        return names.get(class_id, f"vehicle_{class_id}")
    
    def update_line_crossing(self, track_id, current_x, current_y):
        """Track line crossings"""
        if current_x < self.left_limit or current_x > self.right_limit:
            return None
        
        if track_id not in self.track_states:
            self.track_states[track_id] = {
                'line1_crossed': False,
                'line2_crossed': False,
                'line3_crossed': False,
                'direction': None,
                'counted': False,
                'last_seen': self.frame_count
            }
        else:
            self.track_states[track_id]['last_seen'] = self.frame_count
        
        state = self.track_states[track_id]
        
        if abs(current_y - self.line1_y) <= self.line_tolerance:
            state['line1_crossed'] = True
        if abs(current_y - self.line2_y) <= self.line_tolerance:
            state['line2_crossed'] = True
        if abs(current_y - self.line3_y) <= self.line_tolerance:
            state['line3_crossed'] = True
        
        if not state['counted']:
            # Downward (entering)
            if (state['line1_crossed'] and state['line2_crossed'] and 
                state['line3_crossed'] and current_y > self.line3_y + self.line_tolerance):
                new_count = self.shared_counter.increment()
                self.count_increases += 1
                state['counted'] = True
                state['direction'] = 'down'
                print(f"[{self.name}] ENTER: Track {track_id}, Count: {new_count}")
                self.db_writer.write_count_change(new_count, 'increase', track_id)
                return 'increase'
            
            # Upward (exiting)
            elif (state['line3_crossed'] and state['line2_crossed'] and 
                  state['line1_crossed'] and current_y < self.line1_y - self.line_tolerance):
                new_count = self.shared_counter.decrement()
                self.count_decreases += 1
                state['counted'] = True
                state['direction'] = 'up'
                print(f"[{self.name}] EXIT: Track {track_id}, Count: {new_count}")
                self.db_writer.write_count_change(new_count, 'decrease', track_id)
                return 'decrease'
        
        return None
    
    def get_line_status(self, track_id):
        """Get line crossing status"""
        if track_id not in self.track_states:
            return "---"
        state = self.track_states[track_id]
        status = ""
        status += "1" if state['line1_crossed'] else "-"
        status += "2" if state['line2_crossed'] else "-"
        status += "3" if state['line3_crossed'] else "-"
        return status
    
    def reset_counter(self):
        """Reset counter"""
        self.shared_counter.set(0)
        self.count_increases = 0
        self.count_decreases = 0
        self.track_states.clear()
        print(f"[{self.name}] Counter reset")
    
    def process_frame(self, frame):
        """Process frame with detection"""
        self.frame_count += 1
        process_this_frame = (self.frame_count % PROCESS_EVERY_N_FRAMES == 0)
        
        # Run detection
        if process_this_frame:
            try:
                with torch.no_grad():
                    results = self.model.track(
                        frame, 
                        persist=True, 
                        conf=0.5,
                        iou=0.5,
                        tracker="bytetrack.yaml", 
                        device=self.device_id,
                        verbose=False,
                        half=False
                    )
            except Exception as e:
                print(f"[{self.name}] Detection error: {e}")
                results = None
            
            # GPU cleanup
            if self.frame_count % 100 == 0 and torch.cuda.is_available() and self.device_id != 'cpu':
                torch.cuda.empty_cache()
        
        # Draw lines
        cv2.line(frame, self.line1_start, self.line1_end, (0, 0, 255), 3)
        cv2.putText(frame, "LINE 1", (10, self.line1_y - 10), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        
        cv2.line(frame, self.line2_start, self.line2_end, (0, 255, 0), 4)
        cv2.putText(frame, "COUNTING LINE", (10, self.line2_y - 10),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        
        cv2.line(frame, self.line3_start, self.line3_end, (0, 0, 255), 3)
        cv2.putText(frame, "LINE 3", (10, self.line3_y - 10),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        
        # Draw limits
        cv2.line(frame, (self.left_limit, 0), (self.left_limit, self.frame_height), (0, 255, 255), 3)
        cv2.line(frame, (self.right_limit, 0), (self.right_limit, self.frame_height), (0, 255, 255), 3)
        
        # Process detections
        active_vehicles = 0
        if process_this_frame and results and results[0].boxes is not None and results[0].boxes.id is not None:
            boxes = results[0].boxes.xywh.cpu()
            track_ids = results[0].boxes.id.int().cpu().tolist()
            classes = results[0].boxes.cls.int().cpu().tolist()
            
            # Cleanup old tracks
            current_track_ids = set(track_ids)
            stale_tracks = [tid for tid in list(self.track_states.keys()) if tid not in current_track_ids]
            for tid in stale_tracks:
                if self.frame_count - self.track_states.get(tid, {}).get('last_seen', self.frame_count) > MAX_TRACK_AGE:
                    del self.track_states[tid]
            
            # Draw detections
            for box, track_id, cls in zip(boxes, track_ids, classes):
                if not self.is_vehicle_class(cls):
                    continue
                
                x_center, y_center, width, height = box
                current_x = int(x_center)
                current_y = int(y_center)
                
                if current_x < self.left_limit or current_x > self.right_limit:
                    continue
                
                active_vehicles += 1
                
                x1 = int(x_center - width / 2)
                y1 = int(y_center - height / 2)
                x2 = int(x_center + width / 2)
                y2 = int(y_center + height / 2)
                
                crossing_result = self.update_line_crossing(track_id, current_x, current_y)
                
                # Color based on state
                if track_id in self.track_states and self.track_states[track_id]['counted']:
                    color = (0, 255, 0) if self.track_states[track_id]['direction'] == 'down' else (255, 0, 255)
                else:
                    color = (255, 255, 0)
                
                if crossing_result:
                    cv2.circle(frame, (int(x_center), int(y_center)), 60, (0, 0, 255), 8)
                
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 3)
                cv2.circle(frame, (int(x_center), int(y_center)), 8, color, -1)
                
                vehicle_name = self.get_vehicle_name(cls)
                line_status = self.get_line_status(track_id)
                
                cv2.putText(frame, f"ID:{track_id} {vehicle_name}", (x1, y1 - 35),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
                cv2.putText(frame, f"Lines: {line_status}", (x1, y1 - 15),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        
        # Draw stats
        cv2.putText(frame, f"Camera: {self.name}", (10, 40),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        
        current_count = self.shared_counter.get()
        cv2.putText(frame, f"COUNT: {current_count}", (10, 80),
                   cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 255, 255), 3)
        
        cv2.putText(frame, f"IN: +{self.count_increases} | OUT: -{self.count_decreases}", 
                   (10, 130), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        
        cv2.putText(frame, f"Active: {active_vehicles}", (10, 170),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        
        # Device status
        device_text = f"GPU {self.device_id}" if self.device_id != 'cpu' else "CPU"
        cv2.putText(frame, f"Device: {device_text}", (10, 200),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        
        # DB stats
        db_stats = self.db_writer.get_stats()
        cv2.putText(frame, f"DB: OK:{db_stats['successful']} FAIL:{db_stats['failed']}", 
                   (10, 230), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        
        # Controls
        cv2.putText(frame, "q=quit | r=reset | a/d=limits | t/b=lines",
                   (10, self.frame_height - 20), cv2.FONT_HERSHEY_SIMPLEX, 
                   0.5, (255, 255, 255), 1)
        
        return frame
    
    def handle_key(self, key):
        """Handle keyboard input"""
        if key == ord('r'):
            self.reset_counter()
        elif key == ord('a'):
            self.left_limit = max(0, self.left_limit - self.limit_step)
        elif key == ord('d'):
            self.left_limit = min(self.frame_width - 100, self.left_limit + self.limit_step)
        elif key == ord('j'):
            self.right_limit = max(self.left_limit + 100, self.right_limit - self.limit_step)
        elif key == ord('l'):
            self.right_limit = min(self.frame_width, self.right_limit + self.limit_step)
        elif key == ord('t'):
            self.center_y = max(self.line_spacing + 20, self.center_y - 5)
            self.update_lines()
        elif key == ord('b'):
            self.center_y = min(self.frame_height - self.line_spacing - 20, self.center_y + 5)
            self.update_lines()
    
    def run(self):
        """Main processing loop - WITH CRASH PROTECTION"""
        global global_running  # Declare at the START of the method
        
        try:
            # CRITICAL: Connect to camera FIRST
            if not self.connect_camera():
                print(f"[{self.name}] ✗ Camera connection failed")
                return
            
            # CRITICAL: Add delay after connection (especially for Camera 2)
            if self.index > 0:
                print(f"[{self.name}] Waiting 2 seconds before window creation...")
                time.sleep(2)
            
            # CRITICAL: Create window with try-catch
            print(f"[{self.name}] Creating window...")
            try:
                cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
                cv2.resizeWindow(self.window_name, 1200, 800)
                
                # Position window
                window_x = self.config.get('window_x', self.index * 1220)
                window_y = self.config.get('window_y', 0)
                cv2.moveWindow(self.window_name, window_x, window_y)
                
                print(f"[{self.name}] ✓ Window created at ({window_x}, {window_y})")
                
                # Give window manager time
                time.sleep(0.5)
            except Exception as e:
                print(f"[{self.name}] ✗ Window creation failed: {e}")
                print(f"[{self.name}] Will try to continue anyway...")
            
            # Load initial count from DB (Camera 1 only)
            if self.index == 0 and self.db_writer.db_pool:
                try:
                    conn = self.db_writer.db_pool.getconn()
                    cursor = conn.cursor()
                    cursor.execute('SELECT count FROM current_counts WHERE location_id = %s', 
                                 (self.config['location_id'],))
                    result = cursor.fetchone()
                    if result and result[0] > 0:
                        self.shared_counter.set(result[0])
                        print(f"[{self.name}] ✓ Loaded count: {result[0]}")
                    cursor.close()
                    self.db_writer.db_pool.putconn(conn)
                except Exception as e:
                    print(f"[{self.name}] Could not load initial count: {e}")
            
            print(f"[{self.name}] ✓ Starting main loop...")
            last_time = time.time()
            
            # MAIN LOOP
            while self.running and global_running:
                try:
                    # Read frame
                    ret, frame = self.cap.read()
                    
                    if not ret:
                        self.failed_frame_count += 1
                        if self.failed_frame_count >= self.max_failed_frames:
                            print(f"[{self.name}] ✗ Too many failed frames")
                            break
                        time.sleep(0.1)
                        continue
                    
                    self.failed_frame_count = 0
                    
                    # Process frame
                    processed_frame = self.process_frame(frame)
                    
                    # Calculate FPS
                    current_time = time.time()
                    fps = int(1.0 / (current_time - last_time + 0.001))
                    last_time = current_time
                    cv2.putText(processed_frame, f"FPS: {fps}", (10, 260),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                    
                    # Display - with error handling
                    try:
                        cv2.imshow(self.window_name, processed_frame)
                    except Exception as e:
                        print(f"[{self.name}] Display error: {e}")
                        # Continue anyway
                    
                    # Handle keys
                    key = cv2.waitKey(1) & 0xFF
                    if key == ord('q') or key == 27:
                        global_running = False
                        break
                    elif key != 255:
                        self.handle_key(key)
                
                except Exception as e:
                    print(f"[{self.name}] Loop error: {e}")
                    import traceback
                    traceback.print_exc()
                    time.sleep(0.1)
                    continue
        
        except Exception as e:
            print(f"[{self.name}] ✗ FATAL ERROR: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            # Cleanup
            print(f"[{self.name}] Cleaning up...")
            if self.cap:
                self.cap.release()
            try:
                cv2.destroyWindow(self.window_name)
            except:
                pass
            self.db_writer.shutdown()
            
            print(f"[{self.name}] Final count: {self.shared_counter.get()}")
            print(f"[{self.name}] IN: {self.count_increases} | OUT: {self.count_decreases}")

# ============================================================================
# CAMERA THREAD
# ============================================================================
def run_camera(camera_config, camera_index, shared_counter):
    """Run camera with crash protection"""
    try:
        # Camera 2 waits for Camera 1 to be fully ready
        if camera_index > 0:
            print(f"\n[{camera_config['name']}] Waiting for Camera 1 to be ready...")
            camera_1_ready.wait(timeout=60)
            print(f"[{camera_config['name']}] Camera 1 ready, waiting additional 3 seconds...")
            time.sleep(3)  # Extra safety delay
            print(f"[{camera_config['name']}] Starting initialization...")
        
        processor = CameraProcessor(camera_config, camera_index, shared_counter)
        
        # Signal Camera 1 is ready (after processor creation, before run)
        if camera_index == 0:
            print(f"[{camera_config['name']}] Signaling Camera 2 to start...")
            camera_1_ready.set()
        
        processor.run()
        
    except Exception as e:
        print(f"[{camera_config['name']}] ✗ Thread error: {e}")
        import traceback
        traceback.print_exc()

# ============================================================================
# MAIN
# ============================================================================
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Vehicle Counter - Crash-Proof Edition')
    parser.add_argument('--initial-count', type=int, default=0)
    parser.add_argument('--location', type=str, default='main_garage')
    args = parser.parse_args()
    
    print("\n" + "="*70)
    print("VEHICLE COUNTER - CRASH-PROOF EDITION")
    print("="*70)
    print(f"Cameras: {len(CAMERAS)}")
    for i, cam in enumerate(CAMERAS):
        print(f"  {i+1}. {cam['name']} ({cam['ip']})")
    print("="*70)
    
    # Test database
    try:
        conn = psycopg2.connect(
            host=DB_HOST, database=DB_NAME,
            user=DB_USER, password=DB_PASSWORD,
            port=DB_PORT, connect_timeout=5
        )
        conn.close()
        print("✓ Database connection OK\n")
    except Exception as e:
        print(f"✗ Database connection failed: {e}")
        print("Continuing without database...\n")
    
    # Create shared counter
    shared_counter = SharedCounter(initial_count=args.initial_count)
    
    # Start cameras in separate threads
    threads = []
    for i, camera_config in enumerate(CAMERAS):
        print(f"\nStarting thread for {camera_config['name']}...")
        thread = threading.Thread(
            target=run_camera,
            args=(camera_config, i, shared_counter),
            daemon=True
        )
        thread.start()
        threads.append(thread)
        time.sleep(1)  # Delay between camera starts
    
    print("\n" + "="*70)
    print("CAMERAS STARTING")
    print("="*70)
    print("Camera 1 will start first, Camera 2 will wait")
    print("Press 'q' in any window to quit")
    print("="*70 + "\n")
    
    # Wait for threads
    try:
        for thread in threads:
            thread.join()
    except KeyboardInterrupt:
        print("\n\nShutting down...")
        global_running = False
        for thread in threads:
            thread.join(timeout=2)
    
    print("\n" + "="*70)
    print("Shutdown complete")
    print("="*70)
