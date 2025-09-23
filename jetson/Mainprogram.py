import cv2
import numpy as np
from ultralytics import YOLO
from collections import defaultdict

# Load YOLOv8 model
model = YOLO("yolov8n.pt")

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
    global mouse_x, mouse_y, menu_visible, menu_selected_item, screenshot_requested

    mouse_x, mouse_y = x, y

    if event == cv2.EVENT_LBUTTONDOWN:
        print(f"Mouse clicked at ({x}, {y})")  # Debug output

        if menu_visible:
            print("Menu is visible, checking click area")
            # Check if click is within menu area
            if y <= menu_height and x >= 10:
                # Calculate which menu item was clicked
                y_start = 60
                item_height = 25

                for i in range(len(MENU_ITEMS)):
                    item_y_start = y_start + (i * item_height) - 12
                    item_y_end = item_y_start + item_height

                    print(f"Checking item {i} ({MENU_ITEMS[i]}): y range {item_y_start}-{item_y_end}")

                    if item_y_start <= y <= item_y_end and x >= 15 and x <= 500:
                        print(f"✓ Clicked on menu item {i}: {MENU_ITEMS[i]}")
                        menu_selected_item = i
                        handle_menu_selection()
                        return

                # Check for close button (X)
                if x >= frame_width - 40 and x <= frame_width - 10 and y >= 10 and y <= 35:
                    print("Clicked close button")
                    menu_visible = False
                    return
            else:
                # Click outside menu area closes it
                print("Clicked outside menu, closing")
                menu_visible = False
        else:
            # Check if click is on menu button area
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
    global menu_selected_item, mouse_x, mouse_y

    # Semi-transparent overlay
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (frame_width, menu_height), (40, 40, 40), -1)
    cv2.addWeighted(overlay, 0.85, frame, 0.15, 0, frame)

    # Menu border
    cv2.rectangle(frame, (0, 0), (frame_width, menu_height), (100, 100, 100), 2)

    # Menu title
    cv2.putText(frame, "CONFIGURATION MENU", (20, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

    # Close button (X)
    cv2.putText(frame, "✕", (frame_width - 30, 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 100, 100), 2)

    # Menu items with hover detection
    y_start = 60
    item_height = 25

    for i, item in enumerate(MENU_ITEMS):
        y_pos = y_start + (i * item_height)

        # Check if mouse is hovering over this item
        hovering = (mouse_y >= y_pos - 10 and mouse_y <= y_pos + 10 and
                    mouse_x >= 20 and mouse_x <= 400 and menu_visible)

        # Color and styling based on hover/selection
        if hovering:
            # Draw hover background
            cv2.rectangle(frame, (15, y_pos - 12), (450, y_pos + 8), (70, 70, 70), -1)
            color = (0, 255, 255)  # Cyan for hover
            prefix = "► "
        elif i == menu_selected_item:
            color = (0, 255, 0)  # Green for selected
            prefix = "► "
        else:
            color = (255, 255, 255)  # White for normal
            prefix = "  "

        cv2.putText(frame, f"{prefix}{item}", (30, y_pos),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        # Add clickable area indicator
        if hovering:
            cv2.rectangle(frame, (15, y_pos - 12), (450, y_pos + 8), (0, 255, 255), 1)

    # Instructions
    cv2.putText(frame, "Click on items to select • Click outside to close", (20, menu_height - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)


def handle_menu_selection():
    """Handle menu item selection"""
    global screenshot_requested

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


def show_line_position_menu():
    """Show line position adjustment menu"""
    print("\n=== LINE POSITION ADJUSTMENT ===")
    print("Current positions:")
    print(f"  Line 1 (top): Y = {line1_y}")
    print(f"  Line 2 (center): Y = {line2_y}")
    print(f"  Line 3 (bottom): Y = {line3_y}")
    print("1: Move all lines up")
    print("2: Move all lines down")
    print("3: Increase line spacing")
    print("4: Decrease line spacing")
    print("5: Reset to center")

    choice = input("Select option (1-5): ").strip()
    move_lines_menu(choice)


def move_lines_menu(choice):
    """Handle line movement menu choices"""
    global center_y, line1_y, line2_y, line3_y, line_spacing
    global line1_start, line1_end, line2_start, line2_end, line3_start, line3_end

    if choice == '1':  # Move up
        center_y = max(line_spacing + 20, center_y - 20)
    elif choice == '2':  # Move down
        center_y = min(frame_height - line_spacing - 20, center_y + 20)
    elif choice == '3':  # Increase spacing
        line_spacing = min(frame_height // 4, line_spacing + 10)
    elif choice == '4':  # Decrease spacing
        line_spacing = max(30, line_spacing - 10)
    elif choice == '5':  # Reset to center
        center_y = frame_height // 2
        line_spacing = 80
    else:
        return

    # Recalculate line positions
    line1_y = center_y - line_spacing
    line2_y = center_y
    line3_y = center_y + line_spacing

    line1_start, line1_end = (0, line1_y), (frame_width, line1_y)
    line2_start, line2_end = (0, line2_y), (frame_width, line2_y)
    line3_start, line3_end = (0, line3_y), (frame_width, line3_y)

    print(f"Lines repositioned: Y1={line1_y}, Y2={line2_y}, Y3={line3_y}")


def update_lines_realtime():
    """Update line positions in real-time based on current variables"""
    global line1_y, line2_y, line3_y, line1_start, line1_end, line2_start, line2_end, line3_start, line3_end

    # Recalculate line positions
    line1_y = center_y - line_spacing
    line2_y = center_y
    line3_y = center_y + line_spacing

    # Update line coordinates
    line1_start, line1_end = (0, line1_y), (frame_width, line1_y)
    line2_start, line2_end = (0, line2_y), (frame_width, line2_y)
    line3_start, line3_end = (0, line3_y), (frame_width, line3_y)


def show_limits_menu():
    """Show counting limits adjustment menu"""
    global left_limit, right_limit
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
    global fullscreen_mode
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

        if not choice:  # Default to 1080p
            return 1920, 1080

        if choice in RESOLUTION_PRESETS:
            width, height, name = RESOLUTION_PRESETS[choice]
            if choice == '0':  # Custom resolution
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

# Start webcam
cap = cv2.VideoCapture(1, cv2.CAP_DSHOW)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, screen_width)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, screen_height)

# Get actual frame dimensions (camera may not support exact resolution)
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
    frame_width, frame_height = screen_width, screen_height
    print("Warning: Could not read test frame, using requested dimensions")

# Define three-line system for directional counting
line_spacing = 80  # Distance between lines
center_y = frame_height // 2

line1_y = center_y - line_spacing  # Top line
line2_y = center_y  # Middle line (main counter)
line3_y = center_y + line_spacing  # Bottom line

# Line coordinates
line1_start, line1_end = (0, line1_y), (frame_width, line1_y)
line2_start, line2_end = (0, line2_y), (frame_width, line2_y)
line3_start, line3_end = (0, line3_y), (frame_width, line3_y)

# Get initial count from user
print("=== DIRECTIONAL VEHICLE COUNTER SETUP ===")
initial_count = input("Enter initial count (press Enter for 0): ").strip()
try:
    car_count = int(initial_count) if initial_count else 0
except ValueError:
    car_count = 0
    print("Invalid input, starting with count 0")

print(f"Starting count: {car_count}")

# Tracking variables for directional counting
track_states = {}  # Track which lines each vehicle has crossed
count_increases = 0  # Cars going from line 1 to line 3
count_decreases = 0  # Cars going from line 3 to line 1
counted_vehicles = set()  # Prevent double counting

# Detection tolerance
line_tolerance = 25  # Smaller tolerance for better slow vehicle detection

# Counting area limits (yellow lines)
left_limit = 200  # Left boundary (adjustable with Shift + arrow keys)
right_limit = frame_width - 200  # Right boundary (adjustable with Ctrl + arrow keys)
limit_step = 10  # Pixels to move limits with each key press

# Display window settings (separate from camera resolution)
display_width = 1200  # Default display window width
display_height = 800  # Default display window height


def is_vehicle_class(class_id):
    """Check if detected class is ANY type of vehicle"""
    # Expanded vehicle classes from COCO dataset
    vehicle_classes = [
        1,  # bicycle
        2,  # car
        3,  # motorcycle
        4,  # airplane
        5,  # bus
        6,  # train
        7,  # truck
        8,  # boat
    ]
    return class_id in vehicle_classes


def get_vehicle_name(class_id):
    """Get human readable vehicle name"""
    vehicle_names = {
        1: "bicycle", 2: "car", 3: "motorcycle", 4: "airplane",
        5: "bus", 6: "train", 7: "truck", 8: "boat"
    }
    return vehicle_names.get(class_id, f"vehicle_{class_id}")


def update_line_crossing(track_id, current_x, current_y, tolerance):
    """Track which lines a vehicle has crossed and determine direction"""
    global car_count, count_increases, count_decreases

    # Only count vehicles within the left/right limits
    if current_x < left_limit or current_x > right_limit:
        return None

    # Initialize tracking state for new vehicles
    if track_id not in track_states:
        track_states[track_id] = {
            'line1_crossed': False,
            'line2_crossed': False,
            'line3_crossed': False,
            'direction': None,
            'counted': False
        }

    state = track_states[track_id]

    # Check line crossings with tolerance
    near_line1 = abs(current_y - line1_y) <= tolerance
    near_line2 = abs(current_y - line2_y) <= tolerance
    near_line3 = abs(current_y - line3_y) <= tolerance

    # Update line crossing states
    if near_line1:
        state['line1_crossed'] = True
    if near_line2:
        state['line2_crossed'] = True
    if near_line3:
        state['line3_crossed'] = True

    # Check for complete directional sequences
    if not state['counted']:
        # Direction 1→3 (Increase count)
        if (state['line1_crossed'] and state['line2_crossed'] and state['line3_crossed'] and
                current_y > line3_y + tolerance):  # Vehicle has passed line 3

            car_count += 1
            count_increases += 1
            state['counted'] = True
            state['direction'] = 'down'
            print(f"🚗 VEHICLE ENTERING: ID {track_id} - Count: {car_count} (+{count_increases}/-{count_decreases})")
            return 'increase'

        # Direction 3→1 (Decrease count)
        elif (state['line3_crossed'] and state['line2_crossed'] and state['line1_crossed'] and
              current_y < line1_y - tolerance):  # Vehicle has passed line 1

            car_count -= 1
            count_decreases += 1
            state['counted'] = True
            state['direction'] = 'up'
            print(f"🚙 VEHICLE EXITING: ID {track_id} - Count: {car_count} (+{count_increases}/-{count_decreases})")
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
print("Line 1 (red) → Line 2 (green) → Line 3 (red) = COUNT UP")
print("Line 3 (red) → Line 2 (green) → Line 1 (red) = COUNT DOWN")
print("All vehicle types are counted")
print("CONTROLS:")
print("  q = quit")
print("  r = reset counter")
print("  a/d = adjust left limit | j/l = adjust right limit")
print("  t/b = move lines up/down | +/- = adjust line spacing")
print("  w/s = move center line up/down | e/c = fine adjust spacing")
print("  m/click = open configuration menu")
print("  f = toggle fullscreen | s = save screenshot")
print("=" * 70)

frame_count = 0
fullscreen_mode = False
window_name = "Directional Vehicle Counter"


def resize_camera(width, height):
    """Resize camera resolution and update all related elements"""
    global frame_width, frame_height
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

    # Test the new resolution
    ret, test_frame = cap.read()
    if ret:
        frame_height, frame_width = test_frame.shape[:2]
        print(f"Camera resolution changed to: {frame_width}x{frame_height}")

        # Recalculate line positions for new resolution
        global center_y, line1_y, line2_y, line3_y
        global line1_start, line1_end, line2_start, line2_end, line3_start, line3_end
        global left_limit, right_limit

        center_y = frame_height // 2
        line1_y = center_y - line_spacing
        line2_y = center_y
        line3_y = center_y + line_spacing

        line1_start, line1_end = (0, line1_y), (frame_width, line1_y)
        line2_start, line2_end = (0, line2_y), (frame_width, line2_y)
        line3_start, line3_end = (0, line3_y), (frame_width, line3_y)

        # Adjust limits proportionally
        left_limit = min(left_limit, frame_width // 4)
        right_limit = max(right_limit, frame_width * 3 // 4)

        # Resize display window to fit new camera resolution
        try:
            cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
            # Auto-resize window to camera resolution for best fit
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


# Set up the window and mouse callback
cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
cv2.setMouseCallback(window_name, mouse_callback)

while True:
    ret, frame = cap.read()
    if not ret:
        break

    frame_count += 1

    # Run YOLO with tracking
    results = model.track(frame, persist=True, conf=0.35)

    # Draw the three counting lines
    # Line 1 (top) - Red
    cv2.line(frame, line1_start, line1_end, (0, 0, 255), 3)
    cv2.putText(frame, "LINE 1", (10, line1_y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

    # Line 2 (middle/main) - Green
    cv2.line(frame, line2_start, line2_end, (0, 255, 0), 4)
    cv2.putText(frame, "COUNTING LINE 2", (10, line2_y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

    # Line 3 (bottom) - Red
    cv2.line(frame, line3_start, line3_end, (0, 0, 255), 3)
    cv2.putText(frame, "LINE 3", (10, line3_y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

    # Draw left and right limit lines (yellow)
    cv2.line(frame, (left_limit, 0), (left_limit, frame_height), (0, 255, 255), 3)
    cv2.line(frame, (right_limit, 0), (right_limit, frame_height), (0, 255, 255), 3)

    # Label the limit lines
    cv2.putText(frame, "LEFT LIMIT", (left_limit + 5, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
    cv2.putText(frame, "RIGHT LIMIT", (right_limit - 120, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

    # Process tracked detections
    active_vehicles = 0
    if results[0].boxes is not None and results[0].boxes.id is not None:
        boxes = results[0].boxes.xywh.cpu()
        track_ids = results[0].boxes.id.int().cpu().tolist()
        classes = results[0].boxes.cls.int().cpu().tolist()
        confidences = results[0].boxes.conf.cpu().tolist()

        for box, track_id, cls, conf in zip(boxes, track_ids, classes, confidences):
            # Process ALL vehicle types
            if is_vehicle_class(cls):
                active_vehicles += 1

                x_center, y_center, width, height = box
                x1 = int(x_center - width / 2)
                y1 = int(y_center - height / 2)
                x2 = int(x_center + width / 2)
                y2 = int(y_center + height / 2)

                center_point = (int(x_center), int(y_center))
                current_x = int(x_center)
                current_y = int(y_center)

                # Update line crossing status (now includes x position check)
                crossing_result = update_line_crossing(track_id, current_x, current_y, line_tolerance)

                # Draw bounding box (different colors based on position and status)
                if current_x < left_limit or current_x > right_limit:
                    color = (128, 128, 128)  # Gray for vehicles outside counting area
                elif track_id in track_states and track_states[track_id]['counted']:
                    if track_states[track_id]['direction'] == 'down':
                        color = (0, 255, 0)  # Green for counted going down
                    else:
                        color = (255, 0, 255)  # Magenta for counted going up
                else:
                    color = (255, 255, 0)  # Yellow for tracking

                # Flash effect when counted
                if crossing_result:
                    cv2.circle(frame, center_point, 60, (0, 0, 255), 8)

                # Draw bounding box
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 3)

                # Draw center point
                cv2.circle(frame, center_point, 8, color, -1)

                # Show detailed tracking info
                vehicle_name = get_vehicle_name(cls)
                line_status = get_line_status(track_id)

                # Main label
                cv2.putText(frame, f"ID:{track_id} {vehicle_name}", (x1, y1 - 35),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

                # Line crossing status
                cv2.putText(frame, f"Lines: {line_status}", (x1, y1 - 15),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

                # Y position
                cv2.putText(frame, f"Y:{current_y}", (x1, y2 + 20),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

    # Display comprehensive statistics
    cv2.putText(frame, f"NET COUNT: {car_count}", (10, 80),
                cv2.FONT_HERSHEY_SIMPLEX, 2, (255, 255, 255), 4)
    cv2.putText(frame, f"NET COUNT: {car_count}", (10, 80),
                cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 255, 255), 3)

    # Detailed breakdown
    cv2.putText(frame, f"IN: +{count_increases} | OUT: -{count_decreases}", (10, 130),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

    cv2.putText(frame, f"Active Vehicles: {active_vehicles}", (10, 170),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

    # Direction indicators
    cv2.putText(frame, "1→2→3 = COUNT UP", (frame_width - 300, 50),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    cv2.putText(frame, "3→2→1 = COUNT DOWN", (frame_width - 300, 80),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 255), 2)

    # Color legend (updated)
    cv2.putText(frame, "Yellow=Tracking | Green=Counted Up | Magenta=Counted Down | Dark Gray=Ignored (Outside Limits)",
                (10, frame_height - 70), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)

    # Limit positions
    cv2.putText(frame, f"Left Limit: {left_limit}px | Right Limit: {right_limit}px",
                (10, frame_height - 50), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

    # Draw dropdown menu if visible
    if menu_visible:
        draw_dropdown_menu(frame)

    # Display current display size info (not camera resolution)
    display_info = f"Display: {display_width}x{display_height}"
    if fullscreen_mode:
        display_info += " (Fullscreen)"
    cv2.putText(frame, display_info, (frame_width - 300, frame_height - 60),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

    # Menu access hint (now clickable)
    if not menu_visible:
        # Draw clickable menu button
        cv2.rectangle(frame, (10, 5), (290, 35), (60, 60, 60), -1)
        cv2.rectangle(frame, (10, 5), (290, 35), (100, 100, 100), 2)
        cv2.putText(frame, "📋 Configuration Menu (Click)", (15, 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

    # Instructions (updated for real-time line controls)
    cv2.putText(frame, "q=quit | r=reset | a/d j/l=limits | t/b w/s=lines | +/-e/c=spacing | m/click=menu",
                (10, frame_height - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

    # Handle screenshot request from menu
    if screenshot_requested:
        save_screenshot(frame)
        screenshot_requested = False

    cv2.imshow(window_name, frame)

    key = cv2.waitKey(1) & 0xFF

    # Handle menu navigation (keyboard still supported for accessibility)
    if menu_visible:
        if key == 27:  # ESC key
            menu_visible = False
        elif key == 82 or key == ord('w'):  # UP arrow or W
            menu_selected_item = (menu_selected_item - 1) % len(MENU_ITEMS)
        elif key == 84 or key == ord('s'):  # DOWN arrow or S
            menu_selected_item = (menu_selected_item + 1) % len(MENU_ITEMS)
        elif key == 13 or key == ord(' '):  # ENTER or SPACE
            result = handle_menu_selection()
            if result == "screenshot":
                save_screenshot(frame)

    # Regular key handling when menu is closed or for quick access
    if key == ord('q'):
        break
    elif key == ord('m'):  # Open configuration menu (keyboard shortcut)
        menu_visible = not menu_visible
        menu_selected_item = 0
    elif key == ord('r'):
        reset_counter()

    # Quick limit adjustment keys
    elif key == ord('a'):  # Move left limit left
        left_limit = max(0, left_limit - limit_step)
        print(f"Left limit: {left_limit}")
    elif key == ord('d'):  # Move left limit right
        left_limit = min(frame_width - 100, left_limit + limit_step)
        print(f"Left limit: {left_limit}")
    elif key == ord('j'):  # Move right limit left
        right_limit = max(left_limit + 100, right_limit - limit_step)
        print(f"Right limit: {right_limit}")
    elif key == ord('l'):  # Move right limit right
        right_limit = min(frame_width, right_limit + limit_step)
        print(f"Right limit: {right_limit}")

    # Line movement keys (real-time adjustment)
    elif key == ord('t'):  # Move all lines up
        center_y = max(line_spacing + 20, center_y - 5)
        update_lines_realtime()
    elif key == ord('b'):  # Move all lines down
        center_y = min(frame_height - line_spacing - 20, center_y + 5)
        update_lines_realtime()
    elif key == ord('w') and not menu_visible:  # Move center line up (fine control)
        center_y = max(line_spacing + 20, center_y - 2)
        update_lines_realtime()
    elif key == ord('s') and not menu_visible:  # Move center line down (avoid conflict with menu nav)
        center_y = min(frame_height - line_spacing - 20, center_y + 2)
        update_lines_realtime()
    elif key == ord('=') or key == ord('+'):  # Increase spacing
        line_spacing = min(frame_height // 3, line_spacing + 5)
        update_lines_realtime()
    elif key == ord('-'):  # Decrease spacing
        line_spacing = max(20, line_spacing - 5)
        update_lines_realtime()
    elif key == ord('e'):  # Fine increase spacing
        line_spacing = min(frame_height // 3, line_spacing + 2)
        update_lines_realtime()
    elif key == ord('c'):  # Fine decrease spacing
        line_spacing = max(20, line_spacing - 2)
        update_lines_realtime()

    # Quick function keys
    elif key == ord('f'):
        toggle_fullscreen()
    elif key == ord('x'):  # Screenshot key
        save_screenshot(frame)
        print("Screenshot saved!")

    # Window control keys (quick display size changes)
    elif key == ord('1') and not menu_visible:  # Quick window resize
        try:
            display_width, display_height = 800, 600
            cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(window_name, display_width, display_height)
            print("Display resized to Small (800x600) - camera feed scaled to fit")
        except:
            pass
    elif key == ord('2') and not menu_visible:
        try:
            display_width, display_height = 1200, 800
            cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(window_name, display_width, display_height)
            print("Display resized to Medium (1200x800) - camera feed scaled to fit")
        except:
            pass
    elif key == ord('3') and not menu_visible:
        try:
            display_width, display_height = 1600, 1000
            cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(window_name, display_width, display_height)
            print("Display resized to Large (1600x1000) - camera feed scaled to fit")
        except:
            pass

    # Legacy resolution keys (still supported)
    elif key in [ord('1'), ord('2'), ord('3'), ord('4'), ord('5'),
                 ord('6'), ord('7'), ord('8'), ord('9')]:
        preset_key = chr(key)
        if preset_key in RESOLUTION_PRESETS:
            width, height, name = RESOLUTION_PRESETS[preset_key]
            print(f"Quick resolution change to {name}...")
            if resize_camera(width, height):
                track_states.clear()
                print(f"Resolution changed!")
    elif key == ord('0'):
        try:
            width = int(input("Enter width: "))
            height = int(input("Enter height: "))
            if resize_camera(width, height):
                track_states.clear()
                print("Custom resolution set!")
        except ValueError:
            print("Invalid input")

cap.release()
cv2.destroyAllWindows()
print(f"Final Results:")
print(f"Net Count: {car_count}")
print(f"Vehicles In: {count_increases}")
print(f"Vehicles Out: {count_decreases}")
