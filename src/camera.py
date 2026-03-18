"""
Mosquito Laser Tracker - Camera Abstraction
=============================================
Supports Pi Camera (libcamera/picamera2), USB webcam, and video files.
"""

import cv2
import numpy as np
import threading
import time
from typing import Optional, Tuple

from config import (
    CAMERA_TYPE, CAMERA_INDEX, CAMERA_WIDTH, CAMERA_HEIGHT,
    CAMERA_FPS, VIDEO_FILE,
)


class Camera:
    """
    Unified camera interface.
    Runs capture in a background thread for non-blocking reads.
    """

    def __init__(self):
        self._frame: Optional[np.ndarray] = None
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._cap = None
        self._picam = None

    def start(self):
        if self._running:
            return

        self._raw_bayer_mode = False
        if CAMERA_TYPE == "picamera":
            self._start_picamera()
        elif CAMERA_TYPE == "usb":
            self._start_usb()
        elif CAMERA_TYPE == "raw_bayer":
            self._start_raw_bayer()
            self._raw_bayer_mode = True
        elif CAMERA_TYPE == "file":
            self._start_file()
        else:
            raise ValueError(f"Unknown CAMERA_TYPE: {CAMERA_TYPE}")

        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        print(f"[camera] started ({CAMERA_TYPE}, {CAMERA_WIDTH}x{CAMERA_HEIGHT}@{CAMERA_FPS}fps)")

    def _start_picamera(self):
        """Start Pi Camera via picamera2 (Raspberry Pi OS Bookworm+)."""
        try:
            from picamera2 import Picamera2
            self._picam = Picamera2()
            config = self._picam.create_preview_configuration(
                main={"size": (CAMERA_WIDTH, CAMERA_HEIGHT), "format": "RGB888"},
            )
            self._picam.configure(config)
            self._picam.start()
            time.sleep(1)  # warm-up
        except ImportError:
            print("[camera] picamera2 not available, falling back to USB")
            self._start_usb()

    def _start_usb(self):
        """Start USB webcam via OpenCV."""
        self._cap = cv2.VideoCapture(CAMERA_INDEX)
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
        self._cap.set(cv2.CAP_PROP_FPS, CAMERA_FPS)
        if not self._cap.isOpened():
            raise RuntimeError(f"Cannot open USB camera index {CAMERA_INDEX}")

    def _start_raw_bayer(self):
        """
        Start CSI camera via raw Bayer capture on Pi (Ubuntu workaround).
        Uses v4l2 to grab 10-bit packed Bayer and debayers in software.
        Needed when libcamera IPA is broken (Ubuntu 24.04 on Pi).
        """
        import subprocess
        # Set sensor exposure and gain
        subprocess.run(["v4l2-ctl", "-d", "/dev/v4l-subdev0",
                        "-c", "exposure=1600,analogue_gain=120"],
                       capture_output=True)
        # Set raw Bayer format on unicam
        subprocess.run(["v4l2-ctl", "-d", f"/dev/video{CAMERA_INDEX}",
                        f"--set-fmt-video=width={CAMERA_WIDTH},height={CAMERA_HEIGHT},pixelformat=pBAA"],
                       capture_output=True)
        self._cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_V4L2)
        fourcc = cv2.VideoWriter_fourcc(*'pBAA')
        self._cap.set(cv2.CAP_PROP_FOURCC, fourcc)
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
        self._cap.set(cv2.CAP_PROP_CONVERT_RGB, 0)
        if not self._cap.isOpened():
            raise RuntimeError("Cannot open raw Bayer camera")

    def _start_file(self):
        """Open a video file for testing."""
        if not VIDEO_FILE:
            raise ValueError("VIDEO_FILE not set in config")
        self._cap = cv2.VideoCapture(VIDEO_FILE)
        if not self._cap.isOpened():
            raise RuntimeError(f"Cannot open video file: {VIDEO_FILE}")

    def _capture_loop(self):
        """Background capture thread."""
        while self._running:
            frame = None
            if self._picam is not None:
                frame = self._picam.capture_array()
                if frame is not None:
                    frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            elif self._cap is not None:
                ret, raw = self._cap.read()
                if not ret:
                    if CAMERA_TYPE == "file":
                        self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        continue
                    else:
                        time.sleep(0.01)
                        continue

                if getattr(self, '_raw_bayer_mode', False):
                    # Unpack 10-bit MIPI packed Bayer to 8-bit BGR
                    frame = self._debayer_mipi10(raw)
                else:
                    frame = raw

            if frame is not None:
                with self._lock:
                    self._frame = frame

            # Pace to target FPS (don't spin CPU)
            time.sleep(max(0.001, 1.0 / CAMERA_FPS - 0.005))

    def read(self) -> Optional[np.ndarray]:
        """Get the latest frame (non-blocking). Returns None if no frame yet."""
        with self._lock:
            if self._frame is None:
                return None
            return self._frame.copy()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        if self._cap:
            self._cap.release()
        if self._picam:
            self._picam.stop()
        print("[camera] stopped")

    def _debayer_mipi10(self, raw: np.ndarray) -> Optional[np.ndarray]:
        """Unpack 10-bit MIPI packed Bayer to 8-bit BGR."""
        try:
            data = raw.flatten()
            rows, cols = CAMERA_HEIGHT, CAMERA_WIDTH
            expected = rows * cols * 10 // 8
            if len(data) < expected:
                return None

            # Unpack: every 5 bytes = 4 pixels (10-bit packed)
            d = data[:expected]
            b0 = d[0::5].astype(np.uint16)
            b1 = d[1::5].astype(np.uint16)
            b2 = d[2::5].astype(np.uint16)
            b3 = d[3::5].astype(np.uint16)
            b4 = d[4::5].astype(np.uint16)

            p0 = (b0 << 2) | ((b4 >> 0) & 0x03)
            p1 = (b1 << 2) | ((b4 >> 2) & 0x03)
            p2 = (b2 << 2) | ((b4 >> 4) & 0x03)
            p3 = (b3 << 2) | ((b4 >> 6) & 0x03)

            pixels = np.empty(len(p0) * 4, dtype=np.uint16)
            pixels[0::4] = p0
            pixels[1::4] = p1
            pixels[2::4] = p2
            pixels[3::4] = p3

            bayer = (pixels[:rows * cols] >> 2).astype(np.uint8).reshape(rows, cols)

            # Debayer and normalize for visibility
            bgr = cv2.cvtColor(bayer, cv2.COLOR_BayerBG2BGR)

            # Auto-normalize: stretch contrast so image is visible
            mn, mx = bgr.min(), bgr.max()
            if mx > mn:
                bgr = ((bgr.astype(np.float32) - mn) / (mx - mn) * 255).astype(np.uint8)

            return bgr
        except Exception as e:
            return None

    @property
    def resolution(self) -> Tuple[int, int]:
        return (CAMERA_WIDTH, CAMERA_HEIGHT)
