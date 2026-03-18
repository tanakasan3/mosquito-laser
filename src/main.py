#!/usr/bin/env python3
"""
Mosquito Laser Tracker - Main Orchestrator
============================================

This is the main entry point. It:
1. Initializes camera, detector, laser, IR, and aimer
2. Runs the detection loop
3. Aims laser at confirmed mosquito targets
4. Serves the live web dashboard

Usage:
    python main.py                     # default config
    python main.py --aim servo         # force servo mode
    python main.py --aim galvo         # force galvo mode
    python main.py --aim none          # detection only, no aiming
    python main.py --camera usb        # use USB webcam
    python main.py --camera file --video test.mp4   # test with video file
    python main.py --port 8080         # dashboard port
"""

import sys
import time
import signal
import argparse
import threading
import cv2

# Add src to path
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from camera import Camera
from detector import MosquitoDetector
from laser import LaserController, IRController
import dashboard


def parse_args():
    p = argparse.ArgumentParser(description="Mosquito Laser Tracker")
    p.add_argument("--aim", choices=["servo", "galvo", "none"],
                    default=None, help="Aiming mode (overrides config)")
    p.add_argument("--camera", choices=["picamera", "usb", "file"],
                    default=None, help="Camera type (overrides config)")
    p.add_argument("--video", default=None, help="Video file path (for --camera file)")
    p.add_argument("--port", type=int, default=None, help="Web dashboard port")
    p.add_argument("--no-laser", action="store_true", help="Disable laser output")
    p.add_argument("--no-ir", action="store_true", help="Disable IR LEDs")
    p.add_argument("--headless", action="store_true", help="No local OpenCV window")
    return p.parse_args()


def main():
    args = parse_args()

    # Apply CLI overrides
    if args.aim:
        config.AIM_MODE = args.aim
    if args.camera:
        config.CAMERA_TYPE = args.camera
    if args.video:
        config.VIDEO_FILE = args.video
        config.CAMERA_TYPE = "file"
    if args.port:
        config.WEB_PORT = args.port

    print("=" * 60)
    print("  🦟 MOSQUITO LASER TRACKER")
    print("=" * 60)
    print(f"  Camera:  {config.CAMERA_TYPE}")
    print(f"  Aim:     {config.AIM_MODE}")
    print(f"  Web UI:  http://0.0.0.0:{config.WEB_PORT}")
    print("=" * 60)

    # ── Initialize components ───────────────────────────
    cam = Camera()
    det = MosquitoDetector()
    laser = LaserController()
    ir = IRController()
    aimer = None

    if config.AIM_MODE == "servo":
        from aim_servo import ServoAimer
        aimer = ServoAimer()
    elif config.AIM_MODE == "galvo":
        from aim_galvo import GalvoAimer
        aimer = GalvoAimer()

    # ── Start components ────────────────────────────────
    cam.start()
    if not args.no_laser:
        laser.start()
    if not args.no_ir:
        ir.start()
    if aimer:
        aimer.start()

    # ── Wire up dashboard ───────────────────────────────
    dashboard.detector = det
    dashboard.camera = cam
    dashboard.laser_ctrl = laser
    dashboard.ir_ctrl = ir
    dashboard.aimer = aimer

    # Start web server in background thread
    web_thread = threading.Thread(target=dashboard.run_dashboard, daemon=True)
    web_thread.start()
    print(f"[main] dashboard running at http://0.0.0.0:{config.WEB_PORT}")

    # ── Graceful shutdown ───────────────────────────────
    running = True
    def shutdown_handler(sig, frame):
        nonlocal running
        print("\n[main] shutting down...")
        running = False
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    # ── Main detection loop ─────────────────────────────
    print("[main] starting detection loop...")
    frame_count = 0

    try:
        while running:
            frame = cam.read()
            if frame is None:
                time.sleep(0.01)
                continue

            frame_count += 1

            # Run detection pipeline
            annotated, tracks, fg_mask = det.process_frame(frame)

            # Update dashboard streams
            dashboard.update_frames(
                annotated=annotated,
                raw=frame,
                mask=fg_mask,
            )

            # Get primary target
            target = det.get_primary_target()

            if target is not None:
                # Aim at target
                if aimer:
                    aimer.aim_at_pixel(target.x, target.y)

                # Fire laser
                if not args.no_laser and laser.is_enabled:
                    laser.fire()
            else:
                # No target -- turn off laser
                if laser.is_on:
                    laser.off()

            # Optional: show local window (for development)
            if not args.headless:
                try:
                    cv2.imshow("Mosquito Tracker", annotated)
                    key = cv2.waitKey(1) & 0xFF
                    if key == ord('q'):
                        running = False
                    elif key == ord('r'):
                        det.reset()
                        print("[main] detector reset")
                    elif key == ord('l'):
                        laser.toggle_enable()
                        print(f"[main] laser enabled={laser.is_enabled}")
                    elif key == ord('i'):
                        ir.toggle()
                        print(f"[main] IR on={ir._on}")
                    elif key == ord('c'):
                        if aimer:
                            aimer.center()
                            print("[main] aimer centered")
                except cv2.error:
                    # No display available -- go headless
                    args.headless = True

            # Pace the loop (avoid maxing CPU when camera is slower)
            time.sleep(0.001)

    finally:
        print("[main] cleaning up...")
        cam.stop()
        laser.stop()
        ir.stop()
        if aimer:
            aimer.stop()
        if not args.headless:
            try:
                cv2.destroyAllWindows()
            except cv2.error:
                pass
        print("[main] done. 🦟")


if __name__ == "__main__":
    main()
