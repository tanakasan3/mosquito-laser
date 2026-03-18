"""
Mosquito Laser Tracker - Laser & IR LED Control
=================================================
GPIO control for the visible-light spotter laser and IR illumination.
"""

import time
import threading

from config import (
    LASER_PIN, LASER_ON_TIME, LASER_COOLDOWN,
    IR_ENABLE_PIN, IR_ON_AT_START,
)

try:
    import RPi.GPIO as GPIO
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    HAS_GPIO = True
except (ImportError, RuntimeError):
    HAS_GPIO = False


class LaserController:
    """
    Controls the visible-light spotter laser.

    Safety features:
    - Auto-off timer (LASER_ON_TIME seconds max)
    - Cooldown between engagements
    - Software kill switch
    """

    def __init__(self):
        self._on = False
        self._enabled = True       # software kill switch
        self._last_off_time = 0.0
        self._on_since = 0.0
        self._lock = threading.Lock()
        self._auto_off_thread = None

    def start(self):
        if HAS_GPIO:
            GPIO.setup(LASER_PIN, GPIO.OUT)
            GPIO.output(LASER_PIN, GPIO.LOW)
        self._on = False
        print(f"[laser] ready on GPIO{LASER_PIN}")

    def fire(self):
        """Turn laser ON (subject to cooldown and kill switch)."""
        with self._lock:
            if not self._enabled:
                return
            now = time.time()
            if now - self._last_off_time < LASER_COOLDOWN:
                return  # still in cooldown
            if self._on:
                # Already on -- reset the auto-off timer
                self._on_since = now
                return

            self._on = True
            self._on_since = now
            if HAS_GPIO:
                GPIO.output(LASER_PIN, GPIO.HIGH)

            # Start auto-off timer
            if self._auto_off_thread is None or not self._auto_off_thread.is_alive():
                self._auto_off_thread = threading.Thread(
                    target=self._auto_off_loop, daemon=True
                )
                self._auto_off_thread.start()

    def off(self):
        """Turn laser OFF."""
        with self._lock:
            self._on = False
            self._last_off_time = time.time()
            if HAS_GPIO:
                GPIO.output(LASER_PIN, GPIO.LOW)

    def _auto_off_loop(self):
        """Auto-off after LASER_ON_TIME seconds."""
        while True:
            time.sleep(0.1)
            with self._lock:
                if not self._on:
                    return
                if time.time() - self._on_since >= LASER_ON_TIME:
                    self._on = False
                    self._last_off_time = time.time()
                    if HAS_GPIO:
                        GPIO.output(LASER_PIN, GPIO.LOW)
                    return

    def toggle_enable(self):
        """Toggle software kill switch."""
        with self._lock:
            self._enabled = not self._enabled
            if not self._enabled:
                self._on = False
                if HAS_GPIO:
                    GPIO.output(LASER_PIN, GPIO.LOW)

    @property
    def is_on(self) -> bool:
        return self._on

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    def get_state(self) -> dict:
        return {
            "on": self._on,
            "enabled": self._enabled,
            "has_gpio": HAS_GPIO,
        }

    def stop(self):
        self.off()
        if HAS_GPIO:
            GPIO.cleanup([LASER_PIN])
        print("[laser] stopped")


class IRController:
    """
    Controls IR LED illumination via the 555 timer RESET pin.

    The 555 timer runs the IR LEDs at an adjustable frequency
    (set by hardware potentiometers). This controller just
    enables/disables the 555 via its RESET pin.
    """

    def __init__(self):
        self._on = False

    def start(self):
        if HAS_GPIO:
            GPIO.setup(IR_ENABLE_PIN, GPIO.OUT)
        if IR_ON_AT_START:
            self.on()
        else:
            self.off()
        print(f"[ir] ready on GPIO{IR_ENABLE_PIN}")

    def on(self):
        """Enable IR LEDs (assert 555 RESET high)."""
        self._on = True
        if HAS_GPIO:
            GPIO.output(IR_ENABLE_PIN, GPIO.HIGH)

    def off(self):
        """Disable IR LEDs (pull 555 RESET low)."""
        self._on = False
        if HAS_GPIO:
            GPIO.output(IR_ENABLE_PIN, GPIO.LOW)

    def toggle(self):
        if self._on:
            self.off()
        else:
            self.on()

    def get_state(self) -> dict:
        return {
            "on": self._on,
            "has_gpio": HAS_GPIO,
        }

    def stop(self):
        self.off()
        if HAS_GPIO:
            GPIO.cleanup([IR_ENABLE_PIN])
        print("[ir] stopped")
