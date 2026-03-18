"""
Mosquito Laser Tracker - Detection & Tracking Pipeline
========================================================
OpenCV-based mosquito detection using background subtraction,
contour filtering, and multi-object tracking.
"""

import time
import math
import cv2
import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from config import (
    BG_HISTORY, BG_THRESHOLD, BG_DETECT_SHADOWS,
    MOSQUITO_MIN_AREA, MOSQUITO_MAX_AREA, MOSQUITO_MIN_CIRCULARITY,
    MIN_VELOCITY, MAX_VELOCITY,
    MAX_TRACK_DISTANCE, MAX_LOST_FRAMES, MIN_CONFIRM_FRAMES,
)


@dataclass
class Detection:
    """A single-frame mosquito candidate."""
    x: float           # centroid x
    y: float           # centroid y
    area: float        # contour area (px^2)
    bbox: Tuple[int, int, int, int]  # (x, y, w, h)
    contour: np.ndarray = field(repr=False, default=None)


@dataclass
class Track:
    """A tracked mosquito across frames."""
    track_id: int
    x: float
    y: float
    vx: float = 0.0    # velocity x (px/frame)
    vy: float = 0.0     # velocity y (px/frame)
    age: int = 0        # total frames since creation
    hits: int = 0       # frames with matched detection
    lost: int = 0       # consecutive frames without match
    confirmed: bool = False
    bbox: Tuple[int, int, int, int] = (0, 0, 0, 0)
    last_seen: float = 0.0


class MosquitoDetector:
    """
    Detects and tracks mosquito-like objects using:
    1. MOG2 background subtraction
    2. Morphological filtering
    3. Contour size/shape filtering
    4. Simple multi-object tracker (IoU + distance)
    """

    def __init__(self):
        self.bg_sub = cv2.createBackgroundSubtractorMOG2(
            history=BG_HISTORY,
            varThreshold=BG_THRESHOLD,
            detectShadows=BG_DETECT_SHADOWS,
        )
        self._next_id = 0
        self.tracks: List[Track] = []
        self.frame_count = 0

        # Morphological kernels
        self._kernel_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        self._kernel_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))

        # Stats
        self.stats = {
            "detections_raw": 0,
            "detections_filtered": 0,
            "active_tracks": 0,
            "confirmed_tracks": 0,
            "total_tracks_created": 0,
            "fps": 0.0,
        }
        self._last_time = time.time()

    def process_frame(self, frame: np.ndarray) -> Tuple[np.ndarray, List[Track]]:
        """
        Process a single frame. Returns annotated frame and active tracks.
        """
        self.frame_count += 1
        now = time.time()
        dt = now - self._last_time
        self._last_time = now
        if dt > 0:
            self.stats["fps"] = 0.9 * self.stats["fps"] + 0.1 * (1.0 / dt)

        # 1. Preprocess
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        # 2. Background subtraction
        fg_mask = self.bg_sub.apply(blurred)

        # 3. Morphological cleanup
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, self._kernel_open)
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, self._kernel_close)

        # 4. Find contours
        contours, _ = cv2.findContours(
            fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        self.stats["detections_raw"] = len(contours)

        # 5. Filter by size and shape
        detections = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < MOSQUITO_MIN_AREA or area > MOSQUITO_MAX_AREA:
                continue

            # Circularity filter
            perimeter = cv2.arcLength(cnt, True)
            if perimeter > 0:
                circularity = 4 * math.pi * area / (perimeter * perimeter)
                if circularity < MOSQUITO_MIN_CIRCULARITY:
                    continue

            # Centroid
            M = cv2.moments(cnt)
            if M["m00"] == 0:
                continue
            cx = M["m10"] / M["m00"]
            cy = M["m01"] / M["m00"]

            bbox = cv2.boundingRect(cnt)
            detections.append(Detection(
                x=cx, y=cy, area=area, bbox=bbox, contour=cnt
            ))

        self.stats["detections_filtered"] = len(detections)

        # 6. Update tracks
        self._update_tracks(detections)

        # 7. Annotate frame
        annotated = self._annotate(frame, fg_mask, detections)

        return annotated, self.tracks, fg_mask

    def _update_tracks(self, detections: List[Detection]):
        """Simple nearest-neighbor tracker with velocity model."""

        # Predict track positions
        for t in self.tracks:
            t.x += t.vx
            t.y += t.vy

        # Build cost matrix (distance from each track to each detection)
        matched_det = set()
        matched_trk = set()

        if self.tracks and detections:
            costs = np.zeros((len(self.tracks), len(detections)))
            for i, t in enumerate(self.tracks):
                for j, d in enumerate(detections):
                    costs[i, j] = math.hypot(t.x - d.x, t.y - d.y)

            # Greedy matching (good enough for sparse targets)
            while True:
                if costs.size == 0:
                    break
                i, j = np.unravel_index(np.argmin(costs), costs.shape)
                if costs[i, j] > MAX_TRACK_DISTANCE:
                    break
                # Match
                matched_trk.add(i)
                matched_det.add(j)
                d = detections[j]
                t = self.tracks[i]
                # Smooth velocity update
                t.vx = 0.7 * t.vx + 0.3 * (d.x - t.x)
                t.vy = 0.7 * t.vy + 0.3 * (d.y - t.y)
                t.x = d.x
                t.y = d.y
                t.bbox = d.bbox
                t.hits += 1
                t.lost = 0
                t.last_seen = time.time()
                if t.hits >= MIN_CONFIRM_FRAMES:
                    t.confirmed = True
                # Invalidate row/col
                costs[i, :] = 1e9
                costs[:, j] = 1e9

        # Age unmatched tracks
        for i, t in enumerate(self.tracks):
            t.age += 1
            if i not in matched_trk:
                t.lost += 1

        # Create new tracks for unmatched detections
        for j, d in enumerate(detections):
            if j not in matched_det:
                # Velocity filter -- reject if in first few frames (bg learning)
                if self.frame_count < 30:
                    continue
                self.tracks.append(Track(
                    track_id=self._next_id,
                    x=d.x, y=d.y,
                    bbox=d.bbox,
                    hits=1,
                    last_seen=time.time(),
                ))
                self._next_id += 1
                self.stats["total_tracks_created"] += 1

        # Prune dead tracks
        self.tracks = [t for t in self.tracks if t.lost < MAX_LOST_FRAMES]

        self.stats["active_tracks"] = len(self.tracks)
        self.stats["confirmed_tracks"] = sum(1 for t in self.tracks if t.confirmed)

    def _annotate(self, frame: np.ndarray, fg_mask: np.ndarray,
                  detections: List[Detection]) -> np.ndarray:
        """Draw detection info on frame."""
        out = frame.copy()

        # Draw all raw detections as small circles
        for d in detections:
            cv2.circle(out, (int(d.x), int(d.y)), 3, (0, 255, 255), 1)

        # Draw confirmed tracks with box + ID + velocity vector
        for t in self.tracks:
            if not t.confirmed:
                # Unconfirmed: dim marker
                cv2.circle(out, (int(t.x), int(t.y)), 4, (128, 128, 128), 1)
                continue

            # Confirmed target
            bx, by, bw, bh = t.bbox
            color = (0, 0, 255)  # red for confirmed mosquito

            # Bounding box
            pad = 10
            cv2.rectangle(out,
                          (bx - pad, by - pad),
                          (bx + bw + pad, by + bh + pad),
                          color, 2)

            # Crosshair
            cx, cy = int(t.x), int(t.y)
            cv2.line(out, (cx - 15, cy), (cx + 15, cy), color, 1)
            cv2.line(out, (cx, cy - 15), (cx, cy + 15), color, 1)

            # Label
            speed = math.hypot(t.vx, t.vy)
            label = f"#{t.track_id} v={speed:.1f}px/f"
            cv2.putText(out, label, (bx - pad, by - pad - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)

            # Velocity vector
            vscale = 5
            cv2.arrowedLine(out,
                            (cx, cy),
                            (int(cx + t.vx * vscale), int(cy + t.vy * vscale)),
                            (0, 255, 0), 1, tipLength=0.3)

        # Stats overlay
        stats_text = [
            f"FPS: {self.stats['fps']:.1f}",
            f"Raw: {self.stats['detections_raw']}",
            f"Filt: {self.stats['detections_filtered']}",
            f"Tracks: {self.stats['active_tracks']}",
            f"Confirmed: {self.stats['confirmed_tracks']}",
        ]
        for i, txt in enumerate(stats_text):
            cv2.putText(out, txt, (10, 20 + i * 18),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1)

        return out

    def get_primary_target(self) -> Optional[Track]:
        """Return the highest-priority confirmed target for laser aiming."""
        confirmed = [t for t in self.tracks if t.confirmed]
        if not confirmed:
            return None
        # Priority: most recently seen, then closest to center
        confirmed.sort(key=lambda t: (-t.last_seen, t.lost))
        return confirmed[0]

    def reset(self):
        """Reset detector state."""
        self.tracks.clear()
        self._next_id = 0
        self.frame_count = 0
        self.bg_sub = cv2.createBackgroundSubtractorMOG2(
            history=BG_HISTORY,
            varThreshold=BG_THRESHOLD,
            detectShadows=BG_DETECT_SHADOWS,
        )
