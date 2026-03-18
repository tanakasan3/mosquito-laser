"""
Mosquito Laser Tracker - Servo Aiming Controller
==================================================
Pan-tilt servo control via hardware PWM on Raspberry Pi GPIO.
Falls back to software PWM or stub mode on non-Pi systems.
"""

import time
import threading
from typing import Optional, Tuple

from config import (
    SERVO_PAN_PIN, SERVO_TILT_PIN,
    SERVO_PAN_RANGE, SERVO_TILT_RANGE,
    SERVO_PAN_CENTER, SERVO_TILT_CENTER,
    SERVO_PAN_INVERT, SERVO_TILT_INVERT,
    SERVO_DEG_PER_PX_X, SERVO_DEG_PER_PX_Y,
    CAMERA_WIDTH, CAMERA_HEIGHT,
)

# Try hardware GPIO, fall back to stub
try:
    import RPi.GPIO as GPIO
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    HAS_GPIO = True
except (ImportError, RuntimeError):
    HAS_GPIO = False
    print("[servo] RPi.GPIO not available -- running in stub mode")


def _angle_to_duty(angle: float) -> float:
    """Convert angle (0-180) to PWM duty cycle (2.5-12.5% at 50Hz)."""
    return 2.5 + (angle / 180.0) * 10.0


class ServoAimer:
    """
    Controls two servos (pan + tilt) to aim a laser at pixel coordinates.

    The mapping from pixel offset to servo angle is linear:
        angle_offset = pixel_offset * DEG_PER_PX

    Calibrate DEG_PER_PX by pointing at targets at known pixel positions.
    """

    def __init__(self):
        self.pan_angle = SERVO_PAN_CENTER
        self.tilt_angle = SERVO_TILT_CENTER
        self._pan_pwm = None
        self._tilt_pwm = None
        self._lock = threading.Lock()
        self._enabled = False

    def start(self):
        if HAS_GPIO:
            GPIO.setup(SERVO_PAN_PIN, GPIO.OUT)
            GPIO.setup(SERVO_TILT_PIN, GPIO.OUT)
            self._pan_pwm = GPIO.PWM(SERVO_PAN_PIN, 50)   # 50 Hz
            self._tilt_pwm = GPIO.PWM(SERVO_TILT_PIN, 50)
            self._pan_pwm.start(_angle_to_duty(self.pan_angle))
            self._tilt_pwm.start(_angle_to_duty(self.tilt_angle))
        self._enabled = True
        self.center()
        print(f"[servo] started (pan=GPIO{SERVO_PAN_PIN}, tilt=GPIO{SERVO_TILT_PIN})")

    def center(self):
        """Move to center position."""
        self.set_angle(SERVO_PAN_CENTER, SERVO_TILT_CENTER)

    def set_angle(self, pan: float, tilt: float):
        """Set absolute servo angles (degrees)."""
        with self._lock:
            self.pan_angle = max(SERVO_PAN_RANGE[0], min(SERVO_PAN_RANGE[1], pan))
            self.tilt_angle = max(SERVO_TILT_RANGE[0], min(SERVO_TILT_RANGE[1], tilt))

            if HAS_GPIO and self._pan_pwm and self._tilt_pwm:
                self._pan_pwm.ChangeDutyCycle(_angle_to_duty(self.pan_angle))
                self._tilt_pwm.ChangeDutyCycle(_angle_to_duty(self.tilt_angle))

    def aim_at_pixel(self, px: float, py: float):
        """
        Aim laser at a pixel coordinate in the camera frame.

        The offset from frame center is converted to angle delta:
            dx = (px - center_x) * DEG_PER_PX_X
            dy = (py - center_y) * DEG_PER_PX_Y
        """
        cx = CAMERA_WIDTH / 2.0
        cy = CAMERA_HEIGHT / 2.0

        dx = (px - cx) * SERVO_DEG_PER_PX_X
        dy = (py - cy) * SERVO_DEG_PER_PX_Y

        if SERVO_PAN_INVERT:
            dx = -dx
        if SERVO_TILT_INVERT:
            dy = -dy

        new_pan = self.pan_angle + dx
        new_tilt = self.tilt_angle + dy
        self.set_angle(new_pan, new_tilt)

    def get_state(self) -> dict:
        return {
            "pan": round(self.pan_angle, 1),
            "tilt": round(self.tilt_angle, 1),
            "enabled": self._enabled,
            "has_gpio": HAS_GPIO,
        }

    def stop(self):
        self._enabled = False
        self.center()
        time.sleep(0.3)
        if self._pan_pwm:
            self._pan_pwm.stop()
        if self._tilt_pwm:
            self._tilt_pwm.stop()
        if HAS_GPIO:
            GPIO.cleanup([SERVO_PAN_PIN, SERVO_TILT_PIN])
        print("[servo] stopped")
