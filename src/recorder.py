"""
Mosquito Laser Tracker - Session Video Recorder
=================================================
Records detection sessions to local video files.
Saves both the annotated view (with detections overlay) and
optionally the raw camera feed.

Files are saved to ~/mosquito-laser/recordings/ with timestamp names.
"""

import os
import time
import threading
import cv2
import numpy as np
from datetime import datetime

from config import CAMERA_WIDTH, CAMERA_HEIGHT, CAMERA_FPS


class SessionRecorder:
    """
    Records detection sessions to MP4/AVI video files.

    Two recording modes:
    - annotated: the detection overlay view (boxes, tracks, stats)
    - raw: the unprocessed camera feed

    Automatically names files with timestamps.
    Starts/stops via the web dashboard or main loop.
    """

    def __init__(self, output_dir=None, record_raw=False):
        if output_dir is None:
            output_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "recordings"
            )
        self.output_dir = output_dir
        self.record_raw = record_raw

        self._recording = False
        self._writer_annotated = None
        self._writer_raw = None
        self._lock = threading.Lock()
        self._frame_count = 0
        self._start_time = 0.0
        self._current_path = None

        os.makedirs(self.output_dir, exist_ok=True)

    @property
    def is_recording(self) -> bool:
        return self._recording

    @property
    def current_file(self) -> str:
        return self._current_path

    @property
    def elapsed(self) -> float:
        if not self._recording:
            return 0.0
        return time.time() - self._start_time

    @property
    def frame_count(self) -> int:
        return self._frame_count

    def start(self, fps=None, width=None, height=None):
        """Start recording a new session."""
        with self._lock:
            if self._recording:
                return  # already recording

            if fps is None:
                fps = CAMERA_FPS
            if width is None:
                width = CAMERA_WIDTH
            if height is None:
                height = CAMERA_HEIGHT

            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            fourcc = cv2.VideoWriter_fourcc(*"XVID")

            # Annotated output (always)
            ann_path = os.path.join(self.output_dir, f"session_{ts}_annotated.avi")
            self._writer_annotated = cv2.VideoWriter(
                ann_path, fourcc, fps, (width, height)
            )
            if not self._writer_annotated.isOpened():
                print(f"[recorder] ERROR: cannot open {ann_path} for writing")
                self._writer_annotated = None
                return

            self._current_path = ann_path

            # Raw output (optional)
            if self.record_raw:
                raw_path = os.path.join(self.output_dir, f"session_{ts}_raw.avi")
                self._writer_raw = cv2.VideoWriter(
                    raw_path, fourcc, fps, (width, height)
                )

            self._recording = True
            self._frame_count = 0
            self._start_time = time.time()
            print(f"[recorder] Started recording: {ann_path}")

    def stop(self):
        """Stop recording and finalize video files."""
        with self._lock:
            if not self._recording:
                return

            self._recording = False
            elapsed = time.time() - self._start_time

            if self._writer_annotated:
                self._writer_annotated.release()
                self._writer_annotated = None
            if self._writer_raw:
                self._writer_raw.release()
                self._writer_raw = None

            print(f"[recorder] Stopped. {self._frame_count} frames, "
                  f"{elapsed:.1f}s, saved to {self._current_path}")

    def write_frame(self, annotated_frame, raw_frame=None):
        """Write a frame to the recording. Called from the main loop."""
        with self._lock:
            if not self._recording:
                return

            if self._writer_annotated and annotated_frame is not None:
                self._writer_annotated.write(annotated_frame)

            if self._writer_raw and raw_frame is not None:
                self._writer_raw.write(raw_frame)

            self._frame_count += 1

    def toggle(self):
        """Toggle recording on/off."""
        if self._recording:
            self.stop()
        else:
            self.start()

    def get_state(self) -> dict:
        return {
            "recording": self._recording,
            "file": self._current_path,
            "frames": self._frame_count,
            "elapsed": round(self.elapsed, 1),
            "output_dir": self.output_dir,
        }

    def list_recordings(self) -> list:
        """List all recorded session files."""
        files = []
        if os.path.isdir(self.output_dir):
            for f in sorted(os.listdir(self.output_dir), reverse=True):
                if f.endswith((".avi", ".mp4")):
                    path = os.path.join(self.output_dir, f)
                    size = os.path.getsize(path)
                    files.append({
                        "name": f,
                        "path": path,
                        "size_mb": round(size / (1024 * 1024), 1),
                    })
        return files
