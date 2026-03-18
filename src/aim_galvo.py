"""
Mosquito Laser Tracker - Galvanometer Aiming Controller
=========================================================
XY galvo mirror control via MCP4922 dual 12-bit SPI DAC.
Falls back to stub mode on non-Pi systems.
"""

import time
import struct
import threading
from typing import Optional

from config import (
    GALVO_SPI_BUS, GALVO_SPI_DEVICE, GALVO_SPI_SPEED,
    GALVO_X_RANGE, GALVO_Y_RANGE,
    GALVO_X_CENTER, GALVO_Y_CENTER,
    GALVO_X_INVERT, GALVO_Y_INVERT,
    GALVO_VOLTS_PER_PX_X, GALVO_VOLTS_PER_PX_Y,
    CAMERA_WIDTH, CAMERA_HEIGHT,
)

# Try SPI, fall back to stub
try:
    import spidev
    HAS_SPI = True
except ImportError:
    HAS_SPI = False
    print("[galvo] spidev not available -- running in stub mode")


class MCP4922:
    """
    MCP4922 Dual 12-bit DAC over SPI.

    Data format (16 bits):
      Bit 15:    ~A/B      (0 = DAC_A, 1 = DAC_B)
      Bit 14:    BUF       (0 = unbuffered)
      Bit 13:    ~GA       (1 = 1x gain, 0 = 2x gain)
      Bit 12:    ~SHDN     (1 = active, 0 = shutdown)
      Bits 11-0: DATA      (12-bit value)
    """

    def __init__(self, bus=0, device=0, speed=1000000):
        self._spi = None
        if HAS_SPI:
            self._spi = spidev.SpiDev()
            self._spi.open(bus, device)
            self._spi.max_speed_hz = speed
            self._spi.mode = 0

    def write(self, channel: int, value: int):
        """
        Write 12-bit value to DAC channel.
        channel: 0 = DAC_A (X), 1 = DAC_B (Y)
        value: 0-4095
        """
        value = max(0, min(4095, int(value)))
        # Build 16-bit command
        cmd = (channel & 1) << 15  # channel select
        cmd |= 0 << 14            # unbuffered
        cmd |= 1 << 13            # 1x gain
        cmd |= 1 << 12            # active (not shutdown)
        cmd |= value & 0x0FFF

        high = (cmd >> 8) & 0xFF
        low = cmd & 0xFF

        if self._spi:
            self._spi.xfer2([high, low])

    def close(self):
        if self._spi:
            self._spi.close()


class GalvoAimer:
    """
    Controls XY galvanometer mirrors via MCP4922 DAC.

    Pixel-to-DAC mapping:
        dac_offset = pixel_offset * VOLTS_PER_PX * (4096 / Vref)

    Much faster than servos -- sub-millisecond repositioning.
    """

    def __init__(self):
        self.x_value = GALVO_X_CENTER
        self.y_value = GALVO_Y_CENTER
        self._dac: Optional[MCP4922] = None
        self._lock = threading.Lock()
        self._enabled = False

        # DAC counts per pixel (calibrate for your setup)
        # Assuming Vref = 3.3V, range = 4096 counts
        # counts_per_volt = 4096 / 3.3 ≈ 1241
        self._counts_per_px_x = GALVO_VOLTS_PER_PX_X * (4096.0 / 3.3)
        self._counts_per_px_y = GALVO_VOLTS_PER_PX_Y * (4096.0 / 3.3)

    def start(self):
        self._dac = MCP4922(GALVO_SPI_BUS, GALVO_SPI_DEVICE, GALVO_SPI_SPEED)
        self._enabled = True
        self.center()
        print(f"[galvo] started (SPI bus={GALVO_SPI_BUS}, dev={GALVO_SPI_DEVICE})")

    def center(self):
        """Move mirrors to center position."""
        self.set_position(GALVO_X_CENTER, GALVO_Y_CENTER)

    def set_position(self, x: int, y: int):
        """Set absolute DAC values (0-4095)."""
        with self._lock:
            self.x_value = max(GALVO_X_RANGE[0], min(GALVO_X_RANGE[1], int(x)))
            self.y_value = max(GALVO_Y_RANGE[0], min(GALVO_Y_RANGE[1], int(y)))

            if self._dac:
                self._dac.write(0, self.x_value)  # DAC_A = X
                self._dac.write(1, self.y_value)  # DAC_B = Y

    def aim_at_pixel(self, px: float, py: float):
        """
        Aim galvo mirrors at a pixel coordinate in the camera frame.

        Converts pixel offset from center to DAC count offset.
        """
        cx = CAMERA_WIDTH / 2.0
        cy = CAMERA_HEIGHT / 2.0

        dx = (px - cx) * self._counts_per_px_x
        dy = (py - cy) * self._counts_per_px_y

        if GALVO_X_INVERT:
            dx = -dx
        if GALVO_Y_INVERT:
            dy = -dy

        new_x = GALVO_X_CENTER + dx
        new_y = GALVO_Y_CENTER + dy
        self.set_position(int(new_x), int(new_y))

    def get_state(self) -> dict:
        return {
            "x": self.x_value,
            "y": self.y_value,
            "enabled": self._enabled,
            "has_spi": HAS_SPI,
        }

    def stop(self):
        self._enabled = False
        self.center()
        time.sleep(0.05)
        if self._dac:
            self._dac.close()
        print("[galvo] stopped")
