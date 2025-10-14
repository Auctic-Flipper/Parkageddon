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
    device = 'cuda:0'  # Use first GPU
else:
    print("✗ CUDA Available: NO - Running on CPU")
    print("Install CUDA and PyTorch with GPU support:")
    print("  pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118")
    device = 'cpu'
print("="*70 + "\n")

# Load YOLOv8 model on GPU
print("Loading YOLOv8 model...")
model = YOLO("yolov8n.pt")
model.to(device)  # Move model to GPU
print(f"✓ Model loaded on: {device}\n")

# Optional: Skip frames for YOLO processing to boost FPS
PROCESS_EVERY_N_FRAMES = 1  # Process every frame for best tracking (changed back from 2)

# Add cleanup for old tracks
MAX_TRACK_AGE = 500  # Increased from 300 to keep tracks longer

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

# Standard window sizing presets (for windowed display)
WINDOW_SIZES = {
    'small': (800, 600),
    'medium': (1200, 800),
    'large': (1600, 1000),
    'xlarge': (1920, 1080)
}

# Configuration menu state
menu_visible = False
menu_height = 200
menu_selected_item = 0
mouse_x, mouse_y = 0, 0
screenshot_requested = False

MENU_ITEMS = [
    "Resolution Settings",
    "Window Size",
    "Counting Limits",
    "Reset Counter",
    "Toggle Fullscreen",
    "Save Screenshot",
    "Close Menu"
]


def mouse_callback(event, x, y, flags, param):
    """Handle mouse events"""
    global mouse_x, mouse_y, menu_visible, menu_selected_item, screenshot_requested, frame_width

    mouse_x, mouse_y = x, y

    if event == cv2.EVENT_LBUTTONDOWN:
        print(f"Mouse clicked at ({x}, {y})")

        if menu_visible:
            print("Menu is visible, checking click area")
            if y <= menu_height and x >= 10:
                y_start = 60
                item_height = 25

                for i in range(len(MENU_ITEMS)):
                    item_y_start = y_start + (i * item_height) - 12
                    item_y_end = item_y_start + item_height

                    print(f"Checking item {i} ({MENU_ITEMS[i]}): y range {item_y_start}-{item_y_end}")

                    if item_y_start <= y <= item_y_end and x >= 15 and x <= 500:
                        print(f"Clicked on menu item {i}: {MENU_ITEMS[i]}")
                        menu_selected_item = i
                        handle_menu_selection()
                        return

                if x >= frame_width - 40 and x <= frame_width - 10 and y >= 10 and y <= 35:
                    print("Clicked close button")
                    menu_visible = False
                    return
            else:
                print("Clicked outside menu, closing")
                menu_visible = False
        else:
            if y >= 5 and y <= 35 and x >= 10 and x <= 290:
                print("Clicked menu button, opening menu")
                menu_visible = True
                menu_selected_item = 0


def save_screenshot_flag():
    """Set flag for screenshot in main loop"""
    global screenshot_requested
    screenshot_requested = True


def draw_dropdown_menu(frame):
    """Draw configuration dropdown menu with hover effects"""
    global menu_selected_item, mouse_x, mouse_y, frame_width

    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (frame_width, menu_height), (40, 40, 40), -1)
    cv2.addWeighted(overlay, 0.85, frame, 0.15, 0, frame)

    cv2.rectangle(frame, (0, 0), (frame_width, menu_height), (100, 100, 100), 2)

    cv2.putText(frame, "CONFIGURATION MENU", (20, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

    cv2.putText(frame, "X", (frame_width - 30, 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 100, 100), 2)

    y_start = 60
    item_height = 25

    for i, item in enumerate(MENU_ITEMS):
        y_pos = y_start + (i * item_height)

        hovering = (mouse_y >= y_pos - 10 and mouse_y <= y_pos + 10 and
                    mouse_x >= 20 and mouse_x <= 400 and menu_visible)

        if hovering:
            cv2.rectangle(frame, (15, y_pos - 12), (450, y_pos + 8), (70, 70, 70), -1)
            color = (0, 255, 255)
            prefix = "> "
        elif i == menu_selected_item:
            color = (0, 255, 0)
            prefix = "> "
        else:
            color = (255, 255, 255)
            prefix = "  "

        cv2.putText(frame, f"{prefix}{item}", (30, y_pos),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        if hovering:
            cv2.rectangle(frame, (15, y_pos - 12), (450, y_pos + 8), (0, 255, 255), 1)

    cv2.putText(frame, "Click on items to select - Click outside to close", (20, menu_height - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)


def handle_menu_selection():
    """Handle menu item selection"""
    global screenshot_requested, menu_visible

    item = MENU_ITEMS[menu_selected_item]
    print(f"Handling menu selection: {item}")

    if item == "Resolution Settings":
        show_resolution_menu()
    elif item == "Window Size":
        show_window_size_menu()
    elif item == "Counting Limits":
        show_limits_menu()
    elif item == "Reset Counter":
        reset_counter()
    elif item == "Toggle Fullscreen":
        toggle_fullscreen()
    elif item == "Save Screenshot":
        screenshot_requested = True
        menu_visible = False
        print("Screenshot will be saved")
    elif item == "Close Menu":
        menu_visible = False
        print("Menu closed")

    return None


def show_resolution_menu():
    """Show resolution selection submenu"""
    print("\n=== RESOLUTION SELECTION ===")
    for key, (width, height, name) in RESOLUTION_PRESETS.items():
        if key == '0':
            print(f"  {key}: {name} - Enter your own dimensions")
        else:
            print(f"  {key}: {name} - {width}x{height}")

    choice = input("\nSelect resolution (1-9, 0 for custom): ").strip()
    if choice in RESOLUTION_PRESETS:
        width, height, name = RESOLUTION_PRESETS[choice]
        if choice == '0':
            try:
                width = int(input("Enter width: "))
                height = int(input("Enter height: "))
            except ValueError:
                print("Invalid input")
                return

        if resize_camera(width, height):
            print(f"Resolution changed to {name}")
        else:
            print("Failed to change resolution")


def show_window_size_menu():
    """Show window size selection"""
    global window_name
    print("\n=== WINDOW SIZE SELECTION ===")
    print("1: Small (800x600)")
    print("2: Medium (1200x800)")
    print("3: Large (1600x1000)")
    print("4: X-Large (1920x1080)")

    choice = input("Select window size (1-4): ").strip()
    size_map = {'1': 'small', '2': 'medium', '3': 'large', '4': 'xlarge'}

    if choice in size_map:
        size_name = size_map[choice]
        width, height = WINDOW_SIZES[size_name]
        cv2.resizeWindow(window_name, width, height)
        print(f"Window resized to {size_name}: {width}x{height}")


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


def show_limits_menu():
    """Show counting limits adjustment menu"""
    global left_limit, right_limit, frame_width
    print("\n=== COUNTING LIMITS ADJUSTMENT ===")
    print(f"Current limits: Left={left_limit}, Right={right_limit}")
    print("1: Move left limit left")
    print("2: Move left limit right")
    print("3: Move right limit left")
    print("4: Move right limit right")
    print("5: Reset to default positions")

    choice = input("Select option (1-5): ").strip()
    if choice == '1':
        left_limit = max(0, left_limit - 50)
    elif choice == '2':
        left_limit = min(frame_width - 100, left_limit + 50)
    elif choice == '3':
        right_limit = max(left_limit + 100, right_limit - 50)
    elif choice == '4':
        right_limit = min(frame_width, right_limit + 50)
    elif choice == '5':
        left_limit = frame_width // 6
        right_limit = frame_width * 5 // 6

    print(f"Limits updated: Left={left_limit}, Right={right_limit}")


def reset_counter():
    """Reset counter with new value"""
    global car_count, count_increases, count_decreases, track_states, counted_vehicles
    try:
        new_count = int(input("Enter new count value: "))
        car_count = new_count
        count_increases = 0
        count_decreases = 0
        track_states.clear()
        counted_vehicles.clear()
        print(f"Counter reset to {car_count}")
    except ValueError:
        print("Invalid input, counter unchanged")


def toggle_fullscreen():
    """Toggle fullscreen mode"""
    global fullscreen_mode, window_name
    fullscreen_mode = not fullscreen_mode
    if fullscreen_mode:
        cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
        print("Switched to fullscreen")
    else:
        cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_NORMAL)
        print("Switched to windowed mode")


def select_resolution():
    """Let user select screen resolution"""
    print("\n=== RESOLUTION SELECTION ===")
    for key, (width, height, name) in RESOLUTION_PRESETS.items():
        if key == '0':
            print(f"  {key}: {name} - Enter your own dimensions")
        else:
            print(f"  {key}: {name} - {width}x{height}")

    while True:
        choice = input("\nSelect resolution (1-9, 0 for custom, Enter for 1080p): ").strip()

        if not choice:
            return 1920, 1080

        if choice in RESOLUTION_PRESETS:
            width, height, name = RESOLUTION_PRESETS[choice]
            if choice == '0':
                try:
                    width = int(input("Enter width (pixels): "))
                    height = int(input("Enter height (pixels): "))
                    print(f"Selected custom resolution: {width}x{height}")
                    return width, height
                except ValueError:
                    print("Invalid input, using 1080p default")
                    return 1920, 1080
            else:
                print(f"Selected: {name}")
                return width, height
        else:
            print("Invalid choice, please try again")


# Get user's preferred resolution
screen_width, screen_height = select_resolution()

# Common RTSP URL formats for Annke cameras
rtsp_urls = [
    "rtsp://admin:Golddoor99!@192.168.1.107:554/11",  # Main stream
    "rtsp://admin:Golddoor99!@192.168.1.107:554/12",  # Sub stream
    "rtsp://admin:Golddoor99!@192.168.1.107:554/Streaming/Channels/101",  # H.264 main
    "rtsp://admin:Golddoor99!@192.168.1.107:554/Streaming/Channels/102",  # H.264 sub
    "rtsp://admin:Golddoor99!@192.168.1.107/cam/realmonitor?channel=1&subtype=0",  # Alternative
]

print("\n=== TRYING RTSP CONNECTIONS ===")
cap = None
working_url = None

def create_capture(url):
    """Create video capture with optimal settings for RTSP - LOW LATENCY"""
    import os
    # UDP for lowest latency, critical for real-time tracking
    os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;udp|max_delay;500000|reorder_queue_size;0|fflags;nobuffer|flags;low_delay"
    
    temp_cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
    temp_cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Minimal buffer
    temp_cap.set(cv2.CAP_PROP_FPS, 30)
    temp_cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'H264'))
    
    return temp_cap

for rtsp_url in rtsp_urls:
    print(f"Trying: {rtsp_url}")
    test_cap = create_capture(rtsp_url)
    ret, test_frame = test_cap.read()
    
    if ret:
        print(f"SUCCESS! Connected to: {rtsp_url}")
        cap = test_cap
        working_url = rtsp_url
        break
    else:
        print(f"Failed")
        test_cap.release()

if cap is None:
    print("\n" + "="*70)
    print("ERROR: Could not connect with any RTSP URL!")
    print("\nPlease check your camera's RTSP settings:")
    print("1. Log into camera web interface: http://192.168.1.107")
    print("2. Go to Configuration > Network > Advanced Settings > RTSP")
    print("3. Find the RTSP URL path")
    print("4. Or try entering a custom RTSP URL below")
    print("="*70)
    
    custom_url = input("\nEnter custom RTSP URL (or press Enter to exit): ").strip()
    if custom_url:
        cap = create_capture(custom_url)
        ret, test_frame = cap.read()
        if not ret:
            print("Custom URL also failed. Exiting.")
            exit(1)
        working_url = custom_url
    else:
        exit(1)

print(f"\nUsing RTSP URL: {working_url}")

# Reconnection settings
max_reconnect_attempts = 5
reconnect_delay = 2
failed_frame_count = 0
max_failed_frames = 30

def reconnect_stream():
    """Attempt to reconnect to the RTSP stream"""
    global cap, failed_frame_count
    print("\n" + "!"*70)
    print("CONNECTION LOST - Attempting to reconnect...")
    print("!"*70)
    
    cap.release()
    
    for attempt in range(1, max_reconnect_attempts + 1):
        print(f"Reconnection attempt {attempt}/{max_reconnect_attempts}...")
        import time
        time.sleep(reconnect_delay)
        
        cap = create_capture(working_url)
        ret, test_frame = cap.read()
        
        if ret:
            print("Reconnected successfully!")
            failed_frame_count = 0
            return True
        else:
            cap.release()
    
    print("Failed to reconnect after maximum attempts")
    return False

cap.set(cv2.CAP_PROP_FRAME_WIDTH, screen_width)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, screen_height)

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
    print("ERROR: Could not read frame from RTSP stream!")
    print("Connection was established but no video data received.")
    cap.release()
    exit(1)

line_spacing = 80
center_y = frame_height // 2

line1_y = center_y - line_spacing
line2_y = center_y
line3_y = center_y + line_spacing

line1_start, line1_end = (0, line1_y), (frame_width, line1_y)
line2_start, line2_end = (0, line2_y), (frame_width, line2_y)
line3_start, line3_end = (0, line3_y), (frame_width, line3_y)

print("=== DIRECTIONAL VEHICLE COUNTER SETUP ===")
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

display_width = 1200
display_height = 800


def is_vehicle_class(class_id):
    """Check if detected class is a vehicle type for parking garage"""
    # Parking garage vehicles: cars, motorcycles, bicycles, buses, trucks
    parking_vehicles = [2, 3, 5, 7]
    return class_id in parking_vehicles


def get_vehicle_name(class_id):
    """Get human readable vehicle name"""
    vehicle_names = {
        2: "car", 3: "motorcycle",
        5: "bus", 7: "truck"
    }
    return vehicle_names.get(class_id, f"vehicle_{class_id}")


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


print("=== DIRECTIONAL VEHICLE COUNTER ===")
print("Three-line system for accurate directional counting")
print("Line 1 (red) -> Line 2 (green) -> Line 3 (red) = COUNT UP")
print("Line 3 (red) -> Line 2 (green) -> Line 1 (red) = COUNT DOWN")
print("All vehicle types are counted")
print("CONTROLS:")
print("  q = quit")
print("  r = reset counter")
print("  a/d = adjust left limit | j/l = adjust right limit")
print("  t/b = move lines up/down | +/- = adjust line spacing")
print("  w/s = move center line up/down | e/c = fine adjust spacing")
print("  m/click = open configuration menu")
print("  f = toggle fullscreen | x = save screenshot")
print("=" * 70)

frame_count = 0
fullscreen_mode = False
window_name = "Directional Vehicle Counter [GPU ACCELERATED]"


def resize_camera(width, height):
    """Resize camera resolution and update all related elements"""
    global frame_width, frame_height, center_y, line1_y, line2_y, line3_y
    global line1_start, line1_end, line2_start, line2_end, line3_start, line3_end
    global left_limit, right_limit, line_spacing, window_name
    
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

    ret, test_frame = cap.read()
    if ret:
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

        try:
            cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(window_name, frame_width, frame_height)
            print(f"Display window auto-resized to fit camera: {frame_width}x{frame_height}")
        except Exception as e:
            print(f"Warning: Could not auto-resize display window: {e}")

        return True
    else:
        print("Failed to test new camera resolution")
        return False


def save_screenshot(frame):
    """Save current frame as screenshot"""
    import time
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    filename = f"vehicle_count_screenshot_{timestamp}.jpg"
    cv2.imwrite(filename, frame)
    print(f"Screenshot saved as: {filename}")


cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
cv2.setMouseCallback(window_name, mouse_callback)

print("\nStarting video stream...")
print("Connection monitoring: Active")
print(f"Auto-reconnect: Enabled (max {max_reconnect_attempts} attempts)")
print("Low-latency mode: ENABLED (frame skipping + buffer flushing)")
print(f"GPU Acceleration: {'ENABLED' if device == 'cuda:0' else 'DISABLED (using CPU)'}")
print("="*70)

frame_skip_counter = 0
last_frame_time = 0

while True:
    # CRITICAL: Aggressive buffer flushing to prevent lag
    # Grab and discard frames to stay current with the stream
    for _ in range(1):  # Reduced from 2 to 1 for better tracking continuity
        cap.grab()
    
    ret, frame = cap.read()
    
    if not ret:
        failed_frame_count += 1
        print(f"Warning: Failed to read frame ({failed_frame_count}/{max_failed_frames})")
        
        if failed_frame_count >= max_failed_frames:
            if not reconnect_stream():
                print("Unable to maintain connection. Exiting.")
                break
            continue
        else:
            import time
            time.sleep(0.1)
            continue
    
    if failed_frame_count > 0:
        print(f"Connection restored. Resuming normal operation.")
    failed_frame_count = 0

    frame_count += 1
    
    import time
    current_time = time.time()
    last_frame_time = current_time
    
    process_this_frame = (frame_count % PROCESS_EVERY_N_FRAMES == 0)
    
    # Run YOLO on GPU with proper memory management
    if process_this_frame:
        with torch.no_grad():  # Disable gradient computation to save memory
            results = model.track(frame, persist=True, conf=0.4, iou=0.5, 
                                tracker="bytetrack.yaml", device=device, verbose=False)
        
        # CRITICAL: Clear GPU cache periodically to prevent memory buildup
        if frame_count % 150 == 0 and device == 'cuda:0':  # Increased from 100 to 150
            torch.cuda.empty_cache()
            if frame_count % 450 == 0:  # Print stats every 450 frames
                print(f"GPU Memory: {torch.cuda.memory_allocated(0) / 1024**2:.1f}MB allocated")

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
        
        # CRITICAL: Cleanup old tracks to prevent memory buildup
        current_track_ids = set(track_ids)
        stale_tracks = [tid for tid in track_states.keys() if tid not in current_track_ids]
        for tid in stale_tracks:
            if frame_count - track_states.get(tid, {}).get('last_seen', frame_count) > MAX_TRACK_AGE:
                del track_states[tid]

        for box, track_id, cls, conf in zip(boxes, track_ids, classes, confidences):
            # OPTIMIZATION: Check class type FIRST (cheapest operation)
            if not is_vehicle_class(cls):
                continue
            
            x_center, y_center, width, height = box
            current_x = int(x_center)
            
            # OPTIMIZATION: Check limits SECOND before doing any other processing
            if current_x < left_limit or current_x > right_limit:
                continue  # Skip all processing for objects outside limits
            
            # Only process vehicles within the counting zone
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
    
    connection_status = "Connected" if failed_frame_count == 0 else f"Issues ({failed_frame_count})"
    status_color = (0, 255, 0) if failed_frame_count == 0 else (0, 165, 255)
    cv2.putText(frame, f"Stream: {connection_status}", (10, 200),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, status_color, 2)
    
    fps = int(1.0 / (time.time() - last_frame_time + 0.001))
    cv2.putText(frame, f"FPS: {fps}", (10, 230),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    
    # GPU status indicator
    gpu_status = "GPU" if device == 'cuda:0' else "CPU"
    gpu_color = (0, 255, 0) if device == 'cuda:0' else (0, 165, 255)
    cv2.putText(frame, f"Device: {gpu_status}", (10, 260),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, gpu_color, 2)

    cv2.putText(frame, "1->2->3 = COUNT UP", (frame_width - 300, 50),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    cv2.putText(frame, "3->2->1 = COUNT DOWN", (frame_width - 300, 80),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 255), 2)

    cv2.putText(frame, "Yellow=Tracking | Green=Counted Up | Magenta=Counted Down",
                (10, frame_height - 70), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)

    cv2.putText(frame, f"Left Limit: {left_limit}px | Right Limit: {right_limit}px",
                (10, frame_height - 50), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

    if menu_visible:
        draw_dropdown_menu(frame)

    display_info = f"Display: {display_width}x{display_height}"
    if fullscreen_mode:
        display_info += " (Fullscreen)"
    cv2.putText(frame, display_info, (frame_width - 300, frame_height - 60),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

    if not menu_visible:
        cv2.rectangle(frame, (10, 5), (290, 35), (60, 60, 60), -1)
        cv2.rectangle(frame, (10, 5), (290, 35), (100, 100, 100), 2)
        cv2.putText(frame, "Configuration Menu (Click)", (15, 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

    cv2.putText(frame, "q=quit | r=reset | a/d j/l=limits | t/b w/s=lines | +/-e/c=spacing | m/click=menu",
                (10, frame_height - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

    if screenshot_requested:
        save_screenshot(frame)
        screenshot_requested = False

    cv2.imshow(window_name, frame)

    key = cv2.waitKey(1) & 0xFF

    if menu_visible:
        if key == 27:
            menu_visible = False
        elif key == 82 or key == ord('w'):
            menu_selected_item = (menu_selected_item - 1) % len(MENU_ITEMS)
        elif key == 84 or key == ord('s'):
            menu_selected_item = (menu_selected_item + 1) % len(MENU_ITEMS)
        elif key == 13 or key == ord(' '):
            handle_menu_selection()

    if key == ord('q'):
        break
    elif key == ord('m'):
        menu_visible = not menu_visible
        menu_selected_item = 0
    elif key == ord('r'):
        reset_counter()
    elif key == ord('a'):
        left_limit = max(0, left_limit - limit_step)
        print(f"Left limit: {left_limit}")
    elif key == ord('d'):
        left_limit = min(frame_width - 100, left_limit + limit_step)
        print(f"Left limit: {left_limit}")
    elif key == ord('j'):
        right_limit = max(left_limit + 100, right_limit - limit_step)
        print(f"Right limit: {right_limit}")
    elif key == ord('l'):
        right_limit = min(frame_width, right_limit + limit_step)
        print(f"Right limit: {right_limit}")
    elif key == ord('t'):
        center_y = max(line_spacing + 20, center_y - 5)
        update_lines_realtime()
    elif key == ord('b'):
        center_y = min(frame_height - line_spacing - 20, center_y + 5)
        update_lines_realtime()
    elif key == ord('w') and not menu_visible:
        center_y = max(line_spacing + 20, center_y - 2)
        update_lines_realtime()
    elif key == ord('s') and not menu_visible:
        center_y = min(frame_height - line_spacing - 20, center_y + 2)
        update_lines_realtime()
    elif key == ord('=') or key == ord('+'):
        line_spacing = min(frame_height // 3, line_spacing + 5)
        update_lines_realtime()
    elif key == ord('-'):
        line_spacing = max(20, line_spacing - 5)
        update_lines_realtime()
    elif key == ord('e'):
        line_spacing = min(frame_height // 3, line_spacing + 2)
        update_lines_realtime()
    elif key == ord('c'):
        line_spacing = max(20, line_spacing - 2)
        update_lines_realtime()
    elif key == ord('f'):
        toggle_fullscreen()
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