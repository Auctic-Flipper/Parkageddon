import cv2
import numpy as np
from ultralytics import YOLO
from collections import defaultdict
import torch
import threading
from queue import Queue
import time
import os
import psycopg2
from psycopg2 import pool

# CRITICAL: Force discrete NVIDIA GPU (not integrated graphics)
os.environ['CUDA_VISIBLE_DEVICES'] = '0'  # Change to '1' if your 4070 is the second GPU
os.environ['CUDA_LAUNCH_BLOCKING'] = '1'

# ============================================================================
# DATABASE CONFIGURATION - UPDATE THESE VALUES
# ============================================================================
DB_HOST = 'localhost'
DB_NAME = 'Parkageddon'
DB_USER = 'postgres'
DB_PASSWORD = 'Blue-Gold-Dress2025!'
DB_PORT = 5432
# ============================================================================

# Camera configurations
CAMERAS = [
    {
        'name': 'Camera 1 (107)',
        'ip': '192.168.1.107',
        'username': 'admin',
        'password': 'Golddoor99!',
        'port': 554,
        'location_id': 'entrance_1'  # Unique ID for this camera's location
    },
    {
        'name': 'Camera 2 (108)',
        'ip': '192.168.1.108',
        'username': 'admin',
        'password': 'Golddoor99!',
        'port': 554,
        'location_id': 'entrance_2'  # Unique ID for this camera's location
    }
]

# Check GPU availability and select NVIDIA 4070
print("="*70)
print("GPU DETECTION & SELECTION")
print("="*70)
print(f"PyTorch version: {torch.__version__}")
print(f"CUDA available: {torch.cuda.is_available()}")

if torch.cuda.is_available():
    print(f"\n✓ CUDA Available: YES")
    print(f"✓ GPU Count: {torch.cuda.device_count()}")
    
    # List all available GPUs
    print("\nAvailable GPUs:")
    for i in range(torch.cuda.device_count()):
        gpu_name = torch.cuda.get_device_name(i)
        gpu_memory = torch.cuda.get_device_properties(i).total_memory / 1024**3
        print(f"  GPU {i}: {gpu_name} ({gpu_memory:.2f} GB)")
        
        # Automatically select the RTX 4070
        if '4070' in gpu_name:
            print(f"\n>>> FOUND RTX 4070 at GPU index {i} <<<")
            os.environ['CUDA_VISIBLE_DEVICES'] = str(i)
            torch.cuda.set_device(i)
            selected_gpu = i
            break
    else:
        # If 4070 not found, use first available GPU
        selected_gpu = 0
        torch.cuda.set_device(0)
        print(f"\n>>> RTX 4070 not detected, using GPU 0: {torch.cuda.get_device_name(0)} <<<")
    
    print(f"\n✓ Selected GPU: {torch.cuda.get_device_name(selected_gpu)}")
    print(f"✓ CUDA Version: {torch.version.cuda}")
    print(f"✓ GPU Memory: {torch.cuda.get_device_properties(selected_gpu).total_memory / 1024**3:.2f} GB")
    print(f"✓ Compute Capability: {torch.cuda.get_device_properties(selected_gpu).major}.{torch.cuda.get_device_properties(selected_gpu).minor}")
    
    device_id = selected_gpu
    device = f'cuda:{selected_gpu}'
else:
    print("\n✗ CUDA Available: NO - Running on CPU")
    print("\nTo enable GPU:")
    print("1. Check if you have an NVIDIA GPU: nvidia-smi")
    print("2. Install CUDA toolkit from NVIDIA")
    print("3. Install PyTorch with CUDA support:")
    print("   pip uninstall torch torchvision")
    print("   pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121")
    device = 'cpu'
    device_id = 'cpu'
    
print("="*70 + "\n")

# Configuration
PROCESS_EVERY_N_FRAMES = 1
MAX_TRACK_AGE = 500


class DatabaseWriter:
    """Handles database writes with error handling and retry queue"""
    
    def __init__(self, camera_name, location_id):
        self.camera_name = camera_name
        self.location_id = location_id
        
        # Create connection pool
        try:
            self.db_pool = psycopg2.pool.SimpleConnectionPool(
                1,  # Min connections
                5,  # Max connections
                host=DB_HOST,
                database=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD,
                port=DB_PORT
            )
            print(f"[{camera_name}] ✓ Database connection pool created")
        except Exception as e:
            print(f"[{camera_name}] ✗ Database connection failed: {e}")
            self.db_pool = None
        
        # Queue for failed writes (retry later)
        self.retry_queue = Queue()
        self.retry_thread = threading.Thread(target=self._retry_worker, daemon=True)
        self.retry_thread.start()
        
        # Stats
        self.successful_writes = 0
        self.failed_writes = 0
        self.queued_retries = 0
        
    def _retry_worker(self):
        """Background worker that retries failed database writes"""
        while True:
            try:
                time.sleep(10)  # Retry every 10 seconds
                
                if self.retry_queue.empty():
                    continue
                
                # Try to write all queued items
                retry_count = self.retry_queue.qsize()
                print(f"[{self.camera_name}] Retrying {retry_count} queued database writes...")
                
                for _ in range(retry_count):
                    try:
                        payload = self.retry_queue.get_nowait()
                        if self._write_to_database(payload):
                            self.queued_retries -= 1
                            print(f"[{self.camera_name}] ✓ Retry successful")
                        else:
                            # Put back in queue if still failing
                            self.retry_queue.put(payload)
                    except:
                        break
                        
            except Exception as e:
                print(f"[{self.camera_name}] Retry worker error: {e}")
                time.sleep(5)
    
    def _write_to_database(self, payload):
        """Actual database write operation"""
        if not self.db_pool:
            return False
        
        conn = None
        cursor = None
        
        try:
            conn = self.db_pool.getconn()
            cursor = conn.cursor()
            
            # Insert into vehicle_events (log every change)
            cursor.execute('''
                INSERT INTO vehicle_events 
                (location_id, camera_name, count, change_type, track_id, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s)
            ''', (
                payload['location_id'],
                payload['camera_name'],
                payload['count'],
                payload['change_type'],
                payload['track_id'],
                payload['timestamp']
            ))
            
            # Update current_counts (upsert)
            cursor.execute('''
                INSERT INTO current_counts 
                (location_id, camera_name, count, last_change_type, last_update)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (location_id) DO UPDATE SET
                    camera_name = EXCLUDED.camera_name,
                    count = EXCLUDED.count,
                    last_change_type = EXCLUDED.last_change_type,
                    last_update = EXCLUDED.last_update
            ''', (
                payload['location_id'],
                payload['camera_name'],
                payload['count'],
                payload['change_type'],
                payload['timestamp']
            ))
            
            conn.commit()
            self.successful_writes += 1
            return True
            
        except Exception as e:
            if conn:
                conn.rollback()
            print(f"[{self.camera_name}] ✗ Database write error: {e}")
            return False
            
        finally:
            if cursor:
                cursor.close()
            if conn:
                self.db_pool.putconn(conn)
    
    def write_count_change(self, count, change_type, track_id):
        """Write count change to database (with retry on failure)"""
        payload = {
            'location_id': self.location_id,
            'camera_name': self.camera_name,
            'count': count,
            'change_type': change_type,
            'track_id': track_id,
            'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        }
        
        # Try to write immediately
        if self._write_to_database(payload):
            # Success
            direction = "🔼" if change_type == 'increase' else "🔽"
            print(f"[{self.camera_name}] {direction} Database updated: {count} vehicles")
        else:
            # Failed - add to retry queue
            self.failed_writes += 1
            self.retry_queue.put(payload)
            self.queued_retries += 1
            print(f"[{self.camera_name}] ⚠ Database write failed - queued for retry ({self.queued_retries} pending)")
    
    def get_stats(self):
        """Get database write statistics"""
        return {
            'successful': self.successful_writes,
            'failed': self.failed_writes,
            'pending': self.queued_retries
        }
    
    def shutdown(self):
        """Gracefully shutdown"""
        if self.db_pool:
            self.db_pool.closeall()


class CameraProcessor:
    """Process a single camera stream"""
    
    def __init__(self, camera_config, camera_index):
        self.config = camera_config
        self.index = camera_index
        self.name = camera_config['name']
        
        # Initialize database writer
        self.db_writer = DatabaseWriter(
            camera_name=self.name,
            location_id=camera_config.get('location_id', f'camera_{camera_index}')
        )
        
        # Get global device setting
        global device_id, device
        
        # CRITICAL: Verify CUDA is available before proceeding
        if not torch.cuda.is_available():
            print(f"[{self.name}] ERROR: CUDA not available! Will run on CPU.")
            self.device = 'cpu'
            self.device_id = 'cpu'
        else:
            # Use the globally selected GPU (RTX 4070)
            self.device = device
            self.device_id = device_id
            print(f"[{self.name}] Initializing on {torch.cuda.get_device_name(device_id)} (GPU {device_id})")
        
        # Load dedicated YOLO model for this camera
        print(f"[{self.name}] Loading YOLOv8 model...")
        self.model = YOLO("yolov8n.pt")
        
        # CRITICAL: Explicitly move model to the RTX 4070
        if torch.cuda.is_available():
            print(f"[{self.name}] Moving model to {self.device}...")
            
            # Method 1: Move entire model
            self.model.to(self.device)
            
            # Method 2: Move underlying PyTorch model explicitly
            if hasattr(self.model, 'model'):
                self.model.model = self.model.model.to(self.device)
            
            # Method 3: Move predictor if it exists
            if hasattr(self.model, 'predictor') and self.model.predictor is not None:
                if hasattr(self.model.predictor, 'model'):
                    self.model.predictor.model = self.model.predictor.model.to(self.device)
            
            # Verify GPU placement
            try:
                test_param = next(self.model.model.parameters())
                if test_param.is_cuda:
                    actual_device = test_param.device
                    print(f"[{self.name}] ✓✓✓ Model CONFIRMED on GPU: {actual_device}")
                    print(f"[{self.name}] ✓✓✓ Running on: {torch.cuda.get_device_name(actual_device.index)}")
                else:
                    print(f"[{self.name}] ✗✗✗ WARNING: Model on {test_param.device}, NOT GPU!")
            except Exception as e:
                print(f"[{self.name}] Could not verify GPU placement: {e}")
        else:
            print(f"[{self.name}] ✗ Model loaded on CPU")
        
        # Stream variables
        self.cap = None
        self.working_url = None
        self.frame_count = 0
        self.failed_frame_count = 0
        self.max_failed_frames = 30
        
        # Counting variables
        self.car_count = 0
        self.count_increases = 0
        self.count_decreases = 0
        self.track_states = {}
        self.counted_vehicles = set()
        
        # UI variables
        self.frame_width = 1920
        self.frame_height = 1080
        self.center_y = self.frame_height // 2
        self.line_spacing = 80
        self.left_limit = 200
        self.right_limit = self.frame_width - 200
        self.line_tolerance = 25
        self.limit_step = 10
        
        # Window settings
        self.window_name = f"{self.name} - Vehicle Counter"
        self.running = True
        
        # Initialize lines
        self.update_lines()
        
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
        """Create video capture with optimal settings"""
        import os
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;udp|max_delay;500000|reorder_queue_size;0|fflags;nobuffer|flags;low_delay"
        
        temp_cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
        temp_cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        temp_cap.set(cv2.CAP_PROP_FPS, 30)
        temp_cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'H264'))
        
        return temp_cap
    
    def connect_camera(self):
        """Connect to camera RTSP stream"""
        rtsp_urls = [
            f"rtsp://{self.config['username']}:{self.config['password']}@{self.config['ip']}:{self.config['port']}/11",
            f"rtsp://{self.config['username']}:{self.config['password']}@{self.config['ip']}:{self.config['port']}/12",
            f"rtsp://{self.config['username']}:{self.config['password']}@{self.config['ip']}:{self.config['port']}/Streaming/Channels/101",
            f"rtsp://{self.config['username']}:{self.config['password']}@{self.config['ip']}:{self.config['port']}/Streaming/Channels/102",
        ]
        
        print(f"\n[{self.name}] Connecting to camera...")
        
        for rtsp_url in rtsp_urls:
            print(f"[{self.name}] Trying: {rtsp_url.replace(self.config['password'], '****')}")
            test_cap = self.create_capture(rtsp_url)
            ret, test_frame = test_cap.read()
            
            if ret:
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
        
        print(f"[{self.name}] ✗ Failed to connect")
        return False
    
    def reconnect_stream(self):
        """Attempt to reconnect to the RTSP stream"""
        print(f"\n[{self.name}] CONNECTION LOST - Reconnecting...")
        
        if self.cap:
            self.cap.release()
        
        for attempt in range(1, 6):
            print(f"[{self.name}] Attempt {attempt}/5...")
            time.sleep(2)
            
            self.cap = self.create_capture(self.working_url)
            ret, test_frame = self.cap.read()
            
            if ret:
                print(f"[{self.name}] Reconnected!")
                self.failed_frame_count = 0
                return True
            else:
                self.cap.release()
        
        print(f"[{self.name}] Failed to reconnect")
        return False
    
    def is_vehicle_class(self, class_id):
        """Check if detected class is a vehicle"""
        return class_id in [2, 3, 5, 7]  # car, motorcycle, bus, truck
    
    def get_vehicle_name(self, class_id):
        """Get human readable vehicle name"""
        names = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}
        return names.get(class_id, f"vehicle_{class_id}")
    
    def update_line_crossing(self, track_id, current_x, current_y):
        """Track line crossings and count vehicles"""
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
        
        # Check line proximity
        if abs(current_y - self.line1_y) <= self.line_tolerance:
            state['line1_crossed'] = True
        if abs(current_y - self.line2_y) <= self.line_tolerance:
            state['line2_crossed'] = True
        if abs(current_y - self.line3_y) <= self.line_tolerance:
            state['line3_crossed'] = True
        
        # Count if all lines crossed
        if not state['counted']:
            # Downward (entering)
            if (state['line1_crossed'] and state['line2_crossed'] and 
                state['line3_crossed'] and current_y > self.line3_y + self.line_tolerance):
                self.car_count += 1
                self.count_increases += 1
                state['counted'] = True
                state['direction'] = 'down'
                print(f"[{self.name}] ENTERING: ID {track_id} - Count: {self.car_count}")
                
                # Write to database
                self.db_writer.write_count_change(
                    count=self.car_count,
                    change_type='increase',
                    track_id=track_id
                )
                
                return 'increase'
            
            # Upward (exiting)
            elif (state['line3_crossed'] and state['line2_crossed'] and 
                  state['line1_crossed'] and current_y < self.line1_y - self.line_tolerance):
                self.car_count -= 1
                self.count_decreases += 1
                state['counted'] = True
                state['direction'] = 'up'
                print(f"[{self.name}] EXITING: ID {track_id} - Count: {self.car_count}")
                
                # Write to database
                self.db_writer.write_count_change(
                    count=self.car_count,
                    change_type='decrease',
                    track_id=track_id
                )
                
                return 'decrease'
        
        return None
    
    def get_line_status(self, track_id):
        """Get visual status of line crossings"""
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
        self.car_count = 0
        self.count_increases = 0
        self.count_decreases = 0
        self.track_states.clear()
        self.counted_vehicles.clear()
        print(f"[{self.name}] Counter reset to 0")
    
    def process_frame(self, frame):
        """Process a single frame"""
        self.frame_count += 1
        process_this_frame = (self.frame_count % PROCESS_EVERY_N_FRAMES == 0)
        
        # Run YOLO detection on RTX 4070
        if process_this_frame:
            with torch.no_grad():
                # CRITICAL: Explicitly specify device for inference
                if self.device_id != 'cpu':  # GPU
                    results = self.model.track(
                        frame, 
                        persist=True, 
                        conf=0.4, 
                        iou=0.5,
                        tracker="bytetrack.yaml", 
                        device=self.device_id,  # Use RTX 4070
                        verbose=False,
                        half=False  # Use FP32 for stability
                    )
                else:  # CPU fallback
                    results = self.model.track(
                        frame, 
                        persist=True, 
                        conf=0.4, 
                        iou=0.5,
                        tracker="bytetrack.yaml", 
                        device='cpu',
                        verbose=False
                    )
            
            # Clear GPU cache periodically per camera
            if self.frame_count % 200 == 0 and torch.cuda.is_available() and self.device_id != 'cpu':
                torch.cuda.empty_cache()
                if self.frame_count % 600 == 0:
                    allocated = torch.cuda.memory_allocated(self.device_id) / 1024**2
                    reserved = torch.cuda.memory_reserved(self.device_id) / 1024**2
                    print(f"[{self.name}] RTX 4070 Memory - Allocated: {allocated:.1f}MB | Reserved: {reserved:.1f}MB")
        
        # Draw lines
        cv2.line(frame, self.line1_start, self.line1_end, (0, 0, 255), 3)
        cv2.putText(frame, "LINE 1", (10, self.line1_y - 10), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        
        cv2.line(frame, self.line2_start, self.line2_end, (0, 255, 0), 4)
        cv2.putText(frame, "COUNTING LINE 2", (10, self.line2_y - 10),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        
        cv2.line(frame, self.line3_start, self.line3_end, (0, 0, 255), 3)
        cv2.putText(frame, "LINE 3", (10, self.line3_y - 10),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        
        # Draw limits
        cv2.line(frame, (self.left_limit, 0), (self.left_limit, self.frame_height), 
                (0, 255, 255), 3)
        cv2.line(frame, (self.right_limit, 0), (self.right_limit, self.frame_height),
                (0, 255, 255), 3)
        
        cv2.putText(frame, "LEFT LIMIT", (self.left_limit + 5, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        cv2.putText(frame, "RIGHT LIMIT", (self.right_limit - 120, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        
        # Process detections
        active_vehicles = 0
        if process_this_frame and results[0].boxes is not None and results[0].boxes.id is not None:
            boxes = results[0].boxes.xywh.cpu()
            track_ids = results[0].boxes.id.int().cpu().tolist()
            classes = results[0].boxes.cls.int().cpu().tolist()
            
            # Cleanup old tracks
            current_track_ids = set(track_ids)
            stale_tracks = [tid for tid in self.track_states.keys() 
                          if tid not in current_track_ids]
            for tid in stale_tracks:
                if self.frame_count - self.track_states.get(tid, {}).get('last_seen', 
                                                                         self.frame_count) > MAX_TRACK_AGE:
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
                
                # Color coding
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
        cv2.putText(frame, f"NET COUNT: {self.car_count}", (10, 80),
                   cv2.FONT_HERSHEY_SIMPLEX, 2, (255, 255, 255), 4)
        cv2.putText(frame, f"NET COUNT: {self.car_count}", (10, 80),
                   cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 255, 255), 3)
        
        cv2.putText(frame, f"IN: +{self.count_increases} | OUT: -{self.count_decreases}", 
                   (10, 130), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        
        cv2.putText(frame, f"Active: {active_vehicles}", (10, 170),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        
        # Connection status
        status = "Connected" if self.failed_frame_count == 0 else f"Issues ({self.failed_frame_count})"
        color = (0, 255, 0) if self.failed_frame_count == 0 else (0, 165, 255)
        cv2.putText(frame, f"Stream: {status}", (10, 200),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        
        # GPU status
        if hasattr(self, 'device_id') and self.device_id != 'cpu':
            gpu_status = f"RTX 4070 (GPU {self.device_id})"
            gpu_color = (0, 255, 0)
        else:
            gpu_status = "CPU"
            gpu_color = (0, 165, 255)
        cv2.putText(frame, f"Device: {gpu_status}", (10, 230),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, gpu_color, 2)
        
        # Database stats (replaces HTTP stats)
        db_stats = self.db_writer.get_stats()
        db_status = f"DB: ✓{db_stats['successful']} ✗{db_stats['failed']} ⏳{db_stats['pending']}"
        db_color = (0, 255, 0) if db_stats['failed'] == 0 and db_stats['pending'] == 0 else (0, 165, 255)
        cv2.putText(frame, db_status, (10, 260),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, db_color, 2)
        
        cv2.putText(frame, f"Left: {self.left_limit}px | Right: {self.right_limit}px",
                   (10, self.frame_height - 50), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        
        # Controls
        cv2.putText(frame, "q/ESC=quit | r=reset | a/d j/l=limits | t/b w/s=lines | +/- e/c=spacing",
                   (10, self.frame_height - 20), cv2.FONT_HERSHEY_SIMPLEX, 
                   0.5, (255, 255, 255), 1)
        
        return frame
    
    def handle_key(self, key):
        """Handle keyboard input for this camera"""
        if key == ord('r'):
            self.reset_counter()
        elif key == ord('a'):
            self.left_limit = max(0, self.left_limit - self.limit_step)
            print(f"[{self.name}] Left limit: {self.left_limit}")
        elif key == ord('d'):
            self.left_limit = min(self.frame_width - 100, self.left_limit + self.limit_step)
            print(f"[{self.name}] Left limit: {self.left_limit}")
        elif key == ord('j'):
            self.right_limit = max(self.left_limit + 100, self.right_limit - self.limit_step)
            print(f"[{self.name}] Right limit: {self.right_limit}")
        elif key == ord('l'):
            self.right_limit = min(self.frame_width, self.right_limit + self.limit_step)
            print(f"[{self.name}] Right limit: {self.right_limit}")
        elif key == ord('t'):
            self.center_y = max(self.line_spacing + 20, self.center_y - 5)
            self.update_lines()
            print(f"[{self.name}] Lines moved up")
        elif key == ord('b'):
            self.center_y = min(self.frame_height - self.line_spacing - 20, self.center_y + 5)
            self.update_lines()
            print(f"[{self.name}] Lines moved down")
        elif key == ord('w'):
            self.center_y = max(self.line_spacing + 20, self.center_y - 2)
            self.update_lines()
        elif key == ord('s'):
            self.center_y = min(self.frame_height - self.line_spacing - 20, self.center_y + 2)
            self.update_lines()
        elif key == ord('=') or key == ord('+'):
            self.line_spacing = min(self.frame_height // 3, self.line_spacing + 5)
            self.update_lines()
            print(f"[{self.name}] Line spacing increased: {self.line_spacing}")
        elif key == ord('-'):
            self.line_spacing = max(20, self.line_spacing - 5)
            self.update_lines()
            print(f"[{self.name}] Line spacing decreased: {self.line_spacing}")
        elif key == ord('e'):
            self.line_spacing = min(self.frame_height // 3, self.line_spacing + 2)
            self.update_lines()
        elif key == ord('c'):
            self.line_spacing = max(20, self.line_spacing - 2)
            self.update_lines()
    
    def run(self):
        """Main processing loop for this camera"""
        if not self.connect_camera():
            print(f"[{self.name}] Failed to connect. Exiting thread.")
            return
        
        cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(self.window_name, 1200, 800)
        
        # NEW: Read initial count from database AFTER camera connects
        try:
            conn = self.db_writer.db_pool.getconn()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT count FROM current_counts WHERE location_id = %s
            ''', (self.config['location_id'],))
            result = cursor.fetchone()
            if result and result[0] > 0:
                self.car_count = result[0]
                print(f"[{self.name}] ✓ Loaded initial count from database: {self.car_count}")
            else:
                print(f"[{self.name}] Starting count at 0")
            cursor.close()
            self.db_writer.db_pool.putconn(conn)
        except Exception as e:
            print(f"[{self.name}] ⚠ Could not load initial count from database: {e}")
            print(f"[{self.name}] Starting count at 0")

        # Position windows side by side
        cv2.moveWindow(self.window_name, self.index * 1220, 0)
        
        print(f"[{self.name}] Starting processing loop...")
        if torch.cuda.is_available() and self.device_id != 'cpu':
            print(f"[{self.name}] ✓ GPU acceleration ACTIVE on {torch.cuda.get_device_name(self.device_id)}")
        else:
            print(f"[{self.name}] Running on CPU")
        
        # Show database status
        print(f"[{self.name}] ✓ Database writer initialized for {DB_HOST}:{DB_PORT}/{DB_NAME}")
        
        last_time = time.time()
        
        while self.running:
            # Buffer flush for low latency
            for _ in range(1):
                self.cap.grab()
            
            ret, frame = self.cap.read()
            
            if not ret:
                self.failed_frame_count += 1
                
                if self.failed_frame_count >= self.max_failed_frames:
                    if not self.reconnect_stream():
                        print(f"[{self.name}] Unable to reconnect. Stopping.")
                        break
                    continue
                else:
                    time.sleep(0.1)
                    continue
            
            if self.failed_frame_count > 0:
                print(f"[{self.name}] Connection restored")
            self.failed_frame_count = 0
            
            # Process frame
            processed_frame = self.process_frame(frame)
            
            # Calculate and display FPS
            current_time = time.time()
            fps = int(1.0 / (current_time - last_time + 0.001))
            last_time = current_time
            cv2.putText(processed_frame, f"FPS: {fps}", (10, 290),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            
            # Display
            cv2.imshow(self.window_name, processed_frame)
            
            # Handle keys
            key = cv2.waitKey(1) & 0xFF
            
            if key == ord('q') or key == 27:  # q or ESC
                self.running = False
                # Signal all cameras to stop
                global global_running
                global_running = False
                break
            elif key != 255:  # Any other key
                self.handle_key(key)
        
        # Cleanup
        if self.cap:
            self.cap.release()
        cv2.destroyWindow(self.window_name)
        
        # Shutdown database writer
        print(f"[{self.name}] Shutting down database writer...")
        self.db_writer.shutdown()
        
        print(f"\n[{self.name}] Final Results:")
        print(f"  Net Count: {self.car_count}")
        print(f"  Vehicles In: {self.count_increases}")
        print(f"  Vehicles Out: {self.count_decreases}")
        db_stats = self.db_writer.get_stats()
        print(f"  Database Writes: ✓{db_stats['successful']} ✗{db_stats['failed']} ⏳{db_stats['pending']}")


# Global flag to stop all cameras
global_running = True

def run_camera(camera_config, camera_index):
    """Thread function to run a camera with dedicated GPU model"""
    processor = CameraProcessor(camera_config, camera_index)
    processor.run()

# Main execution
if __name__ == "__main__":
    import argparse
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Vehicle Counter with Database')
    parser.add_argument('--initial-count', type=int, default=0, 
                       help='Initial vehicle count (default: 0)')
    parser.add_argument('--location', type=str, default='entrance_1',
                       help='Location ID to set initial count for')
    args = parser.parse_args()
    
    # If initial count specified, update database before starting
    if args.initial_count > 0:
        print(f"\nSetting initial count for {args.location} to {args.initial_count}...")
        try:
            conn = psycopg2.connect(
                host=DB_HOST, database=DB_NAME,
                user=DB_USER, password=DB_PASSWORD, port=DB_PORT
            )
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE current_counts 
                SET count = %s, last_update = NOW()
                WHERE location_id = %s
            ''', (args.initial_count, args.location))
            conn.commit()
            cursor.close()
            conn.close()
            print(f"✓ Initial count set to {args.initial_count} in database\n")
        except Exception as e:
            print(f"✗ Error setting initial count: {e}\n")
    
    print("\n" + "="*70)
    print("MULTI-CAMERA VEHICLE COUNTER WITH DATABASE INTEGRATION")
    print("="*70)
    print(f"Number of cameras: {len(CAMERAS)}")
    for i, cam in enumerate(CAMERAS):
        print(f"  Camera {i+1}: {cam['name']} ({cam['ip']}) -> {cam.get('location_id', 'N/A')}")
    print(f"\nDatabase: {DB_HOST}:{DB_PORT}/{DB_NAME}")
    print(f"Database User: {DB_USER}")
    print("="*70 + "\n")
    
    # Test database connection before starting cameras
    print("Testing database connection...")
    try:
        test_conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            port=DB_PORT
        )
        test_conn.close()
        print("✓ Database connection successful\n")
    except Exception as e:
        print(f"✗ Database connection failed: {e}")
        print("Please check your database configuration and ensure PostgreSQL is running.")
        print("Update DB_HOST, DB_NAME, DB_USER, DB_PASSWORD at the top of this file.")
        exit(1)
    
    # Create threads for each camera
    threads = []
    
    for i, camera_config in enumerate(CAMERAS):
        thread = threading.Thread(
            target=run_camera,
            args=(camera_config, i),
            daemon=True
        )
        thread.start()
        threads.append(thread)
        print(f"Started thread for {camera_config['name']}")
        time.sleep(1)  # Small delay between camera starts
    
    # Wait for all threads
    print("\n" + "="*70)
    print("ALL CAMERAS RUNNING")
    if torch.cuda.is_available():
        print("GPU acceleration: ENABLED")
    print(f"Database: {DB_HOST}:{DB_PORT}/{DB_NAME}")
    print("Database writes: ENABLED with automatic retry on failure")
    print("Press 'q' or 'ESC' in any window to quit all cameras")
    print("="*70 + "\n")
    
    try:
        for thread in threads:
            thread.join()
    except KeyboardInterrupt:
        print("\n\nKeyboard interrupt detected. Shutting down...")
        global_running = False
        for thread in threads:
            thread.join(timeout=2)
    
    print("\n" + "="*70)
    print("All cameras stopped. Exiting.")
    if torch.cuda.is_available() and device_id != 'cpu':
        print(f"\nFinal GPU Memory Stats for {torch.cuda.get_device_name(device_id)}:")
        print(f"  Allocated: {torch.cuda.memory_allocated(device_id) / 1024**2:.2f} MB")
        print(f"  Reserved: {torch.cuda.memory_reserved(device_id) / 1024**2:.2f} MB")
        print(f"  Max Allocated: {torch.cuda.max_memory_allocated(device_id) / 1024**2:.2f} MB")
    print("="*70)
