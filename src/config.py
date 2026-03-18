"""
Mosquito Laser Tracker - Configuration
=======================================
Edit these values to match your hardware setup.
"""

# ── Camera ──────────────────────────────────────────────
CAMERA_TYPE = "usb"       # "picamera" | "usb" | "raw_bayer" | "file"
CAMERA_INDEX = 0               # USB camera index (ignored for picamera)
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
CAMERA_FPS = 30
VIDEO_FILE = ""                # path to test video (when CAMERA_TYPE="file")

# ── Detection ───────────────────────────────────────────
# Background subtraction
BG_HISTORY = 500               # frames of bg history
BG_THRESHOLD = 16              # variance threshold
BG_DETECT_SHADOWS = False

# Mosquito size filter (pixels) -- tune for your camera/distance
MOSQUITO_MIN_AREA = 4          # min contour area (px^2)
MOSQUITO_MAX_AREA = 600        # max contour area (px^2)
MOSQUITO_MIN_CIRCULARITY = 0.1 # 0-1, how round the blob must be

# Motion filter
MIN_VELOCITY = 1.0             # min movement in px/frame to count as flying
MAX_VELOCITY = 80.0            # max movement -- reject large jumps (noise)

# Tracking
MAX_TRACK_DISTANCE = 60        # max px distance to associate detections
MAX_LOST_FRAMES = 15           # frames before dropping a lost track
MIN_CONFIRM_FRAMES = 3         # consecutive detections to confirm target

# ── Aiming ──────────────────────────────────────────────
AIM_MODE = "servo"             # "servo" | "galvo" | "none"

# Servo config (BCM pin numbers)
SERVO_PAN_PIN = 12             # GPIO12 = PWM0
SERVO_TILT_PIN = 13            # GPIO13 = PWM1
SERVO_PAN_RANGE = (0, 180)     # degrees
SERVO_TILT_RANGE = (0, 180)
SERVO_PAN_CENTER = 90
SERVO_TILT_CENTER = 90
SERVO_PAN_INVERT = False
SERVO_TILT_INVERT = False

# Camera-to-servo mapping (degrees per pixel)
# Calibrate by pointing at known positions
SERVO_DEG_PER_PX_X = 0.1      # pan degrees per pixel offset
SERVO_DEG_PER_PX_Y = 0.1      # tilt degrees per pixel offset

# Galvo config (SPI)
GALVO_SPI_BUS = 0
GALVO_SPI_DEVICE = 0           # CE0
GALVO_SPI_SPEED = 1000000      # 1 MHz
GALVO_X_RANGE = (0, 4095)      # 12-bit DAC range
GALVO_Y_RANGE = (0, 4095)
GALVO_X_CENTER = 2048
GALVO_Y_CENTER = 2048
GALVO_X_INVERT = False
GALVO_Y_INVERT = False
GALVO_VOLTS_PER_PX_X = 0.005  # calibrate for your setup
GALVO_VOLTS_PER_PX_Y = 0.005

# ── Laser ───────────────────────────────────────────────
LASER_PIN = 18                 # GPIO18 (BCM)
LASER_ON_TIME = 5.0            # seconds to keep laser on per target
LASER_COOLDOWN = 0.5           # seconds between re-engagement

# ── IR Illumination ─────────────────────────────────────
IR_ENABLE_PIN = 24             # GPIO24 -- controls 555 RESET
IR_ON_AT_START = True          # turn on IR LEDs on startup

# ── Web Dashboard ───────────────────────────────────────
WEB_HOST = "0.0.0.0"
WEB_PORT = 8080
STREAM_QUALITY = 70            # JPEG quality for MJPEG stream (1-100)
