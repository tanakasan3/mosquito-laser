"""
Mosquito Laser Tracker - Web Dashboard
========================================
Flask-based web UI with MJPEG live streaming and REST API.
"""

import cv2
import time
import math
import threading
from flask import Flask, Response, render_template, jsonify, request

from config import WEB_HOST, WEB_PORT, STREAM_QUALITY, AIM_MODE

app = Flask(__name__,
            template_folder="../templates",
            static_folder="../static")

# These get set by main.py before starting the server
detector = None
camera = None
laser_ctrl = None
ir_ctrl = None
aimer = None

# Frame buffers for streaming (set by main loop)
_frames = {
    "annotated": None,
    "raw": None,
    "mask": None,
}
_frame_lock = threading.Lock()


def update_frames(annotated, raw, mask):
    """Called by main loop to update stream buffers."""
    with _frame_lock:
        _frames["annotated"] = annotated
        _frames["raw"] = raw
        _frames["mask"] = mask


def _generate_mjpeg(feed_name: str):
    """MJPEG stream generator."""
    while True:
        with _frame_lock:
            frame = _frames.get(feed_name)
        if frame is None:
            time.sleep(0.05)
            continue

        # Encode to JPEG
        if len(frame.shape) == 2:
            # Grayscale (fg mask)
            _, buf = cv2.imencode('.jpg', frame,
                                  [cv2.IMWRITE_JPEG_QUALITY, STREAM_QUALITY])
        else:
            _, buf = cv2.imencode('.jpg', frame,
                                  [cv2.IMWRITE_JPEG_QUALITY, STREAM_QUALITY])

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' +
               buf.tobytes() + b'\r\n')
        time.sleep(0.033)  # ~30 fps cap


# ── Routes ──────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/video_feed/<feed_name>")
def video_feed(feed_name):
    if feed_name not in _frames:
        feed_name = "annotated"
    return Response(
        _generate_mjpeg(feed_name),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )


@app.route("/api/status")
def api_status():
    target = detector.get_primary_target() if detector else None
    tracks_data = []
    if detector:
        for t in detector.tracks:
            tracks_data.append({
                "id": t.track_id,
                "x": int(t.x),
                "y": int(t.y),
                "speed": round(math.hypot(t.vx, t.vy), 1),
                "confirmed": t.confirmed,
                "age": t.age,
                "lost": t.lost,
            })

    return jsonify({
        "detector": detector.stats if detector else {},
        "laser": laser_ctrl.get_state() if laser_ctrl else {},
        "ir": ir_ctrl.get_state() if ir_ctrl else {},
        "aimer": aimer.get_state() if aimer else {},
        "aim_mode": AIM_MODE,
        "target": {
            "id": target.track_id,
            "x": int(target.x),
            "y": int(target.y),
        } if target else None,
        "tracks": tracks_data,
    })


@app.route("/api/laser/toggle", methods=["POST"])
def api_laser_toggle():
    if laser_ctrl:
        laser_ctrl.toggle_enable()
    return jsonify({"ok": True})


@app.route("/api/ir/toggle", methods=["POST"])
def api_ir_toggle():
    if ir_ctrl:
        ir_ctrl.toggle()
    return jsonify({"ok": True})


@app.route("/api/aim/center", methods=["POST"])
def api_aim_center():
    if aimer:
        aimer.center()
    return jsonify({"ok": True})


@app.route("/api/detector/reset", methods=["POST"])
def api_detector_reset():
    if detector:
        detector.reset()
    return jsonify({"ok": True})


@app.route("/api/tune", methods=["POST"])
def api_tune():
    """Live-tune detection parameters."""
    import config
    data = request.get_json(force=True)
    if "min_area" in data:
        config.MOSQUITO_MIN_AREA = int(data["min_area"])
    if "max_area" in data:
        config.MOSQUITO_MAX_AREA = int(data["max_area"])
    if "bg_threshold" in data:
        val = int(data["bg_threshold"])
        config.BG_THRESHOLD = val
        if detector:
            detector.bg_sub.setVarThreshold(val)
    return jsonify({"ok": True})


def run_dashboard():
    """Start Flask in a background thread."""
    app.run(host=WEB_HOST, port=WEB_PORT, threaded=True, use_reloader=False)
