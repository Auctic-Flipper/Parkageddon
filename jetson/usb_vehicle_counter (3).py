import cv2
import numpy as np
from ultralytics import YOLO
from collections import defaultdict
import torch

# Check GPU availability
print("="*70)
print("GPU DETECTION")
print("="*70)
if torch.cuda.is_available():
    print(f"✓ CUDA Available: YES")
    print(f"✓ GPU Device: {torch.cuda.get_device_name(0)}")
    print(f"✓ CUDA Version: {torch.version.cuda}")
    print(f"✓ GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.2f} GB")
    device = 'cuda:0'
else:
    print("✗ CUDA Available: NO - Running on CPU")
    print("Install CUDA and PyTorch with GPU support:")
    print("  pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118")
    device = 'cpu'
print("="*70 + "\n")

# Load YOLOv8 model on GPU
print("Loading YOLOv8 model...")
model = YOLO("yolov8n.pt")
model.to(device)
print(f"✓ Model loaded on: {device}\n")

# Processing settings
PROCESS_EVERY_N_FRAMES = 1
MAX_TRACK_AGE = 500

# Screen resolution presets
RESOLUTION_PRESETS = {
    '1': (640, 480, '480p (VGA)'),
    '2': (800, 600, '600p (SVGA)'),
    '3': (1024, 768, '768p (XGA)'),
    '4': (1280, 720, '720p (HD)'),
    '5': (1920, 1080, '1080p (Full HD)'),
    '6': (2560, 1440, '1440p (2K)'),
    '7': (3840, 2160, '2160p (4K)'),
    '8': (1366, 768, '768p (Laptop)'),
    '9': (1600, 900, '900p (HD+)'),
    '0': (0, 0, 'Custom')
}

# Global variables for trackbars
pending_resolution_change = None
apply_resolution_flag = False
trackbar_width = 1280
trackbar_height = 720

def select_resolution():
    """Let user select screen resolution"""
    print("\n=== RESOLUTION SELECTION ===")
    for key, (width, height, name) in RESOLUTION_PRESETS.items():
        if key == '0':
            print(f"  {key}: {name} - Enter your own dimensions")
        else:
            print(f"  {key}: {name} - {width}x{height}")

    while True:
        choice = input("\nSelect resolution (1-9, 0 for custom, Enter for 720p): ").strip()

        if not choice:
            return 1280, 720

        if choice in RESOLUTION_PRESETS:
            width, height, name = RESOLUTION_PRESETS[choice]
            if choice == '0':
                try:
                    width = int(input("Enter width (pixels): "))
                    height = int(input("Enter height (pixels): "))
                    print(f"Selected custom resolution: {width}x{height}")
                    return width, height
                except ValueError:
                    print("Invalid input, using 720p default")
                    return 1280, 720
            else:
                print(f"Selected: {name}")
                return width, height
        else:
            print("Invalid choice, please try again")


# Get user's preferred resolution
screen_width, screen_height = select_resolution()
trackbar_width = screen_width
trackbar_height = screen_height

# Select USB camera
print("\n=== USB CAMERA SELECTION ===")
print("Detecting available cameras...")

available_cameras = []
for i in range(10):
    test_cap = cv2.VideoCapture(i)
    if test_cap.isOpened():
        ret, _ = test_cap.read()
        if ret:
            available_cameras.append(i)
            print(f"  Camera {i}: Available")
        test_cap.release()

if not available_cameras:
    print("ERROR: No USB cameras detected!")
    print("Please check that your camera is connected and drivers are installed.")
    exit(1)

print(f"\nFound {len(available_cameras)} camera(s): {available_cameras}")

if len(available_cameras) == 1:
    camera_index = available_cameras[0]
    print(f"Using camera {camera_index}")
else:
    while True:
        try:
            camera_index = int(input(f"Select camera index {available_cameras}: "))
            if camera_index in available_cameras:
                break
            else:
                print("Invalid camera index, please try again")
        except ValueError:
            print("Invalid input, please enter a number")

# Initialize camera
print(f"\nInitializing camera {camera_index}...")
cap = cv2.VideoCapture(camera_index)

if not cap.isOpened():
    print("ERROR: Could not open camera!")
    exit(1)

# Set camera resolution
cap.set(cv2.CAP_PROP_FRAME_WIDTH, screen_width)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, screen_height)

# Get actual resolution
ret, test_frame = cap.read()
if ret:
    frame_height, frame_width = test_frame.shape[:2]
    actual_resolution = f"{frame_width}x{frame_height}"
    requested_resolution = f"{screen_width}x{screen_height}"

    if frame_width != screen_width or frame_height != screen_height:
        print(f"Note: Requested {requested_resolution}, camera provides {actual_resolution}")
    else:
        print(f"Resolution set to: {actual_resolution}")
else:
    print("ERROR: Could not read frame from camera!")
    cap.release()
    exit(1)

# Initialize line positions
line_spacing = 80
center_y = frame_height // 2

line1_y = center_y - line_spacing
line2_y = center_y
line3_y = center_y + line_spacing

line1_start, line1_end = (0, line1_y), (frame_width, line1_y)
line2_start, line2_end = (0, line2_y), (frame_width, line2_y)
line3_start, line3_end = (0, line3_y), (frame_width, line3_y)

print("\n=== DIRECTIONAL VEHICLE COUNTER SETUP ===")
initial_count = input("Enter initial count (press Enter for 0): ").strip()
try:
    car_count = int(initial_count) if initial_count else 0
except ValueError:
    car_count = 0
    print("Invalid input, starting with count 0")

print(f"Starting count: {car_count}")

track_states = {}
count_increases = 0
count_decreases = 0
counted_vehicles = set()

line_tolerance = 25

left_limit = 200
right_limit = frame_width - 200
limit_step = 10

fullscreen_mode = False
window_name = "Directional Vehicle Counter [GPU ACCELERATED]"
controls_window = "Control Panel"


def is_vehicle_class(class_id):
    """Check if detected class is a vehicle type"""
    parking_vehicles = [2, 3, 5, 7]  # car, motorcycle, bus, truck
    return class_id in parking_vehicles


def get_vehicle_name(class_id):
    """Get human readable vehicle name"""
    vehicle_names = {
        2: "car", 3: "motorcycle",
        5: "bus", 7: "truck"
    }
    return vehicle_names.get(class_id, f"vehicle_{class_id}")


def update_lines_realtime():
    """Update line positions in real-time based on current variables"""
    global line1_y, line2_y, line3_y, line1_start, line1_end, line2_start, line2_end, line3_start, line3_end
    global center_y, line_spacing, frame_width

    line1_y = center_y - line_spacing
    line2_y = center_y
    line3_y = center_y + line_spacing

    line1_start, line1_end = (0, line1_y), (frame_width, line1_y)
    line2_start, line2_end = (0, line2_y), (frame_width, line2_y)
    line3_start, line3_end = (0, line3_y), (frame_width, line3_y)


def update_line_crossing(track_id, current_x, current_y, tolerance):
    """Track which lines a vehicle has crossed and determine direction"""
    global car_count, count_increases, count_decreases

    if current_x < left_limit or current_x > right_limit:
        return None

    if track_id not in track_states:
        track_states[track_id] = {
            'line1_crossed': False,
            'line2_crossed': False,
            'line3_crossed': False,
            'direction': None,
            'counted': False,
            'last_seen': frame_count
        }
    else:
        track_states[track_id]['last_seen'] = frame_count

    state = track_states[track_id]

    near_line1 = abs(current_y - line1_y) <= tolerance
    near_line2 = abs(current_y - line2_y) <= tolerance
    near_line3 = abs(current_y - line3_y) <= tolerance

    if near_line1:
        state['line1_crossed'] = True
    if near_line2:
        state['line2_crossed'] = True
    if near_line3:
        state['line3_crossed'] = True

    if not state['counted']:
        if (state['line1_crossed'] and state['line2_crossed'] and state['line3_crossed'] and
                current_y > line3_y + tolerance):

            car_count += 1
            count_increases += 1
            state['counted'] = True
            state['direction'] = 'down'
            print(f"VEHICLE ENTERING: ID {track_id} - Count: {car_count} (+{count_increases}/-{count_decreases})")
            return 'increase'

        elif (state['line3_crossed'] and state['line2_crossed'] and state['line1_crossed'] and
              current_y < line1_y - tolerance):

            car_count -= 1
            count_decreases += 1
            state['counted'] = True
            state['direction'] = 'up'
            print(f"VEHICLE EXITING: ID {track_id} - Count: {car_count} (+{count_increases}/-{count_decreases})")
            return 'decrease'

    return None


def get_line_status(track_id):
    """Get visual status of which lines a vehicle has crossed"""
    if track_id not in track_states:
        return "---"

    state = track_states[track_id]
    status = ""
    status += "1" if state['line1_crossed'] else "-"
    status += "2" if state['line2_crossed'] else "-"
    status += "3" if state['line3_crossed'] else "-"
    return status


def resize_camera(width, height):
    """Resize camera resolution and update all related elements"""
    global frame_width, frame_height, center_y, line1_y, line2_y, line3_y
    global line1_start, line1_end, line2_start, line2_end, line3_start, line3_end
    global left_limit, right_limit, line_spacing, window_name, trackbar_width, trackbar_height
    global cap, camera_index
    
    import time
    
    # Release current camera
    cap.release()
    time.sleep(0.5)  # Give camera time to release
    
    # Reinitialize camera with new resolution
    cap = cv2.VideoCapture(camera_index)
    
    if not cap.isOpened():
        print("ERROR: Could not reopen camera!")
        return False
    
    # Set new resolution
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    
    # Wait a moment for camera to adjust
    time.sleep(0.3)
    
    # Try to read a test frame
    for attempt in range(5):
        ret, test_frame = cap.read()
        if ret and test_frame is not None:
            break
        time.sleep(0.1)
    
    if not ret or test_frame is None:
        print(f"Failed to read frame with new resolution {width}x{height}")
        return False
    
    # Update all dimensions
    frame_height, frame_width = test_frame.shape[:2]
    print(f"Camera resolution changed to: {frame_width}x{frame_height}")

    center_y = frame_height // 2
    line1_y = center_y - line_spacing
    line2_y = center_y
    line3_y = center_y + line_spacing

    line1_start, line1_end = (0, line1_y), (frame_width, line1_y)
    line2_start, line2_end = (0, line2_y), (frame_width, line2_y)
    line3_start, line3_end = (0, line3_y), (frame_width, line3_y)

    left_limit = min(left_limit, frame_width // 4)
    right_limit = max(right_limit, frame_width * 3 // 4)
    
    # Update trackbar limits
    trackbar_width = frame_width
    trackbar_height = frame_height
    cv2.setTrackbarMax("Center Y", controls_window, frame_height)
    cv2.setTrackbarMax("Left Limit", controls_window, frame_width)
    cv2.setTrackbarMax("Right Limit", controls_window, frame_width)
    
    # Update trackbar positions
    cv2.setTrackbarPos("Center Y", controls_window, center_y)
    cv2.setTrackbarPos("Left Limit", controls_window, left_limit)
    cv2.setTrackbarPos("Right Limit", controls_window, right_limit)

    return True


def save_screenshot(frame):
    """Save current frame as screenshot"""
    import time
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    filename = f"vehicle_count_screenshot_{timestamp}.jpg"
    cv2.imwrite(filename, frame)
    print(f"Screenshot saved as: {filename}")


# Trackbar callback functions
def on_width_change(val):
    global pending_resolution_change, trackbar_width
    trackbar_width = max(320, val)
    pending_resolution_change = (trackbar_width, trackbar_height)

def on_height_change(val):
    global pending_resolution_change, trackbar_height
    trackbar_height = max(240, val)
    pending_resolution_change = (trackbar_width, trackbar_height)

def on_line_spacing_change(val):
    global line_spacing
    line_spacing = max(20, val)
    update_lines_realtime()

def on_center_y_change(val):
    global center_y
    center_y = max(line_spacing + 20, min(frame_height - line_spacing - 20, val))
    update_lines_realtime()

def on_left_limit_change(val):
    global left_limit
    left_limit = max(0, min(frame_width - 100, val))

def on_right_limit_change(val):
    global right_limit
    right_limit = max(left_limit + 100, min(frame_width, val))

def on_counter_change(val):
    global car_count
    car_count = val

def on_apply_resolution(val):
    global apply_resolution_flag
    if val == 1:
        apply_resolution_flag = True


print("\n=== DIRECTIONAL VEHICLE COUNTER ===")
print("Three-line system for accurate directional counting")
print("Line 1 (red) -> Line 2 (green) -> Line 3 (red) = COUNT UP")
print("Line 3 (red) -> Line 2 (green) -> Line 1 (red) = COUNT DOWN")
print("All vehicle types are counted")
print("\nCONTROLS:")
print("  TRACKBARS: Use Control Panel window for all adjustments")
print("  q = quit | f = toggle fullscreen | x = save screenshot")
print("  RESOLUTION: Adjust width/height, then toggle 'Apply Resolution' ON")
print("=" * 70)

frame_count = 0

# Create windows
cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
cv2.namedWindow(controls_window, cv2.WINDOW_NORMAL)
cv2.resizeWindow(controls_window, 500, 400)

# Create trackbars
cv2.createTrackbar("Resolution Width", controls_window, trackbar_width, 3840, on_width_change)
cv2.createTrackbar("Resolution Height", controls_window, trackbar_height, 2160, on_height_change)
cv2.createTrackbar("Apply Resolution", controls_window, 0, 1, on_apply_resolution)
cv2.createTrackbar("Line Spacing", controls_window, line_spacing, 300, on_line_spacing_change)
cv2.createTrackbar("Center Y", controls_window, center_y, frame_height, on_center_y_change)
cv2.createTrackbar("Left Limit", controls_window, left_limit, frame_width, on_left_limit_change)
cv2.createTrackbar("Right Limit", controls_window, right_limit, frame_width, on_right_limit_change)
cv2.createTrackbar("Counter Value", controls_window, car_count, 9999, on_counter_change)

print("\nStarting video stream...")
print(f"GPU Acceleration: {'ENABLED' if device == 'cuda:0' else 'DISABLED (using CPU)'}")
print("Control Panel window opened - use trackbars for adjustments")
print("="*70)

last_frame_time = 0

while True:
    ret, frame = cap.read()
    
    if not ret:
        print("Warning: Failed to read frame from camera")
        break

    frame_count += 1
    
    import time
    current_time = time.time()
    
    # Check if Apply Resolution toggle is ON (read trackbar value directly)
    apply_toggle = cv2.getTrackbarPos("Apply Resolution", controls_window)
    
    # Handle pending resolution change
    if pending_resolution_change and apply_toggle == 1:
        width, height = pending_resolution_change
        if resize_camera(width, height):
            print(f"✓ Resolution applied: {width}x{height}")
        else:
            print(f"✗ Failed to apply resolution: {width}x{height}")
        pending_resolution_change = None
        cv2.setTrackbarPos("Apply Resolution", controls_window, 0)
        apply_resolution_flag = False
    
    process_this_frame = (frame_count % PROCESS_EVERY_N_FRAMES == 0)
    
    # Run YOLO on GPU with proper memory management
    if process_this_frame:
        with torch.no_grad():
            results = model.track(frame, persist=True, conf=0.4, iou=0.5, 
                                tracker="bytetrack.yaml", device=device, verbose=False)
        
        # Clear GPU cache periodically
        if frame_count % 150 == 0 and device == 'cuda:0':
            torch.cuda.empty_cache()

    # Draw counting lines
    cv2.line(frame, line1_start, line1_end, (0, 0, 255), 3)
    cv2.putText(frame, "LINE 1", (10, line1_y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

    cv2.line(frame, line2_start, line2_end, (0, 255, 0), 4)
    cv2.putText(frame, "COUNTING LINE 2", (10, line2_y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

    cv2.line(frame, line3_start, line3_end, (0, 0, 255), 3)
    cv2.putText(frame, "LINE 3", (10, line3_y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

    cv2.line(frame, (left_limit, 0), (left_limit, frame_height), (0, 255, 255), 3)
    cv2.line(frame, (right_limit, 0), (right_limit, frame_height), (0, 255, 255), 3)

    cv2.putText(frame, "LEFT LIMIT", (left_limit + 5, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
    cv2.putText(frame, "RIGHT LIMIT", (right_limit - 120, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

    active_vehicles = 0
    if process_this_frame and results[0].boxes is not None and results[0].boxes.id is not None:
        boxes = results[0].boxes.xywh.cpu()
        track_ids = results[0].boxes.id.int().cpu().tolist()
        classes = results[0].boxes.cls.int().cpu().tolist()
        confidences = results[0].boxes.conf.cpu().tolist()
        
        # Cleanup old tracks
        current_track_ids = set(track_ids)
        stale_tracks = [tid for tid in track_states.keys() if tid not in current_track_ids]
        for tid in stale_tracks:
            if frame_count - track_states.get(tid, {}).get('last_seen', frame_count) > MAX_TRACK_AGE:
                del track_states[tid]

        for box, track_id, cls, conf in zip(boxes, track_ids, classes, confidences):
            if not is_vehicle_class(cls):
                continue
            
            x_center, y_center, width, height = box
            current_x = int(x_center)
            
            if current_x < left_limit or current_x > right_limit:
                continue
            
            current_y = int(y_center)
            active_vehicles += 1

            x1 = int(x_center - width / 2)
            y1 = int(y_center - height / 2)
            x2 = int(x_center + width / 2)
            y2 = int(y_center + height / 2)

            center_point = (int(x_center), int(y_center))

            crossing_result = update_line_crossing(track_id, current_x, current_y, line_tolerance)

            if track_id in track_states and track_states[track_id]['counted']:
                if track_states[track_id]['direction'] == 'down':
                    color = (0, 255, 0)
                else:
                    color = (255, 0, 255)
            else:
                color = (255, 255, 0)

            if crossing_result:
                cv2.circle(frame, center_point, 60, (0, 0, 255), 8)

            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 3)
            cv2.circle(frame, center_point, 8, color, -1)

            vehicle_name = get_vehicle_name(cls)
            line_status = get_line_status(track_id)

            cv2.putText(frame, f"ID:{track_id} {vehicle_name}", (x1, y1 - 35),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
            cv2.putText(frame, f"Lines: {line_status}", (x1, y1 - 15),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
            cv2.putText(frame, f"Y:{current_y}", (x1, y2 + 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

    # Display count and stats
    cv2.putText(frame, f"NET COUNT: {car_count}", (10, 80),
                cv2.FONT_HERSHEY_SIMPLEX, 2, (255, 255, 255), 4)
    cv2.putText(frame, f"NET COUNT: {car_count}", (10, 80),
                cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 255, 255), 3)

    cv2.putText(frame, f"IN: +{count_increases} | OUT: -{count_decreases}", (10, 130),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

    cv2.putText(frame, f"Active Vehicles: {active_vehicles}", (10, 170),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    
    fps = int(1.0 / (current_time - last_frame_time + 0.001))
    cv2.putText(frame, f"FPS: {fps}", (10, 200),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    
    # GPU status indicator
    gpu_status = "GPU" if device == 'cuda:0' else "CPU"
    gpu_color = (0, 255, 0) if device == 'cuda:0' else (0, 165, 255)
    cv2.putText(frame, f"Device: {gpu_status}", (10, 230),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, gpu_color, 2)

    # Resolution change indicator
    if pending_resolution_change:
        res_text = f"Pending: {pending_resolution_change[0]}x{pending_resolution_change[1]} - Toggle 'Apply Resolution' ON"
        cv2.putText(frame, res_text, (10, 260),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 165, 255), 2)

    cv2.putText(frame, "1->2->3 = COUNT UP", (frame_width - 300, 50),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    cv2.putText(frame, "3->2->1 = COUNT DOWN", (frame_width - 300, 80),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 255), 2)

    cv2.putText(frame, "Yellow=Tracking | Green=Counted Up | Magenta=Counted Down",
                (10, frame_height - 50), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)

    cv2.putText(frame, "Use Control Panel for adjustments | q=quit | f=fullscreen | x=screenshot",
                (10, frame_height - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

    cv2.imshow(window_name, frame)
    
    last_frame_time = current_time

    key = cv2.waitKey(1) & 0xFF

    if key == ord('q'):
        break
    elif key == ord('f'):
        fullscreen_mode = not fullscreen_mode
        if fullscreen_mode:
            cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
            print("Switched to fullscreen")
        else:
            cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_NORMAL)
            print("Switched to windowed mode")
    elif key == ord('x'):
        save_screenshot(frame)
        print("Screenshot saved!")

cap.release()
cv2.destroyAllWindows()
print(f"\nFinal Results:")
print(f"Net Count: {car_count}")
print(f"Vehicles In: {count_increases}")
print(f"Vehicles Out: {count_decreases}")

# Display GPU usage stats if available
if device == 'cuda:0':
    print(f"\nGPU Stats:")
    print(f"Memory Allocated: {torch.cuda.memory_allocated(0) / 1024**2:.2f} MB")
    print(f"Memory Reserved: {torch.cuda.memory_reserved(0) / 1024**2:.2f} MB")