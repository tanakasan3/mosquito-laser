# Mosquito Laser Tracker - Management Makefile
# Usage: make [target] [OPTION=value ...]
#
# Examples:
#   make run                     # start with defaults (headless, no aim)
#   make run-record              # start + record session
#   make run AIM=servo           # start with servo aiming
#   make run CAMERA=usb PORT=9090
#   make run-debug               # foreground with verbose output
#   make status                  # check if running + show stats
#   make stop                    # graceful shutdown
#   make logs                    # tail the log
#   make recordings              # list recorded sessions
#   make clean-recordings        # delete all recordings

# ── Options (override on command line) ─────────────────
CAMERA   ?= raw_bayer
AIM      ?= none
PORT     ?= 8080
RECORD   ?=
RECORD_RAW ?=
EXTRA    ?=

# ── Paths ──────────────────────────────────────────────
APP      := src/main.py
PIDFILE  := .mosquito.pid
LOGFILE  := /tmp/mosquito-laser.log
REC_DIR  := recordings

# ── Build flags ────────────────────────────────────────
PY       := python3
FLAGS    := --aim $(AIM) --headless --port $(PORT)

ifdef CAMERA
  FLAGS += --camera $(CAMERA)
endif
ifdef RECORD
  FLAGS += --record
endif
ifdef RECORD_RAW
  FLAGS += --record-raw
endif
ifneq ($(EXTRA),)
  FLAGS += $(EXTRA)
endif

# ── Targets ────────────────────────────────────────────

.PHONY: run run-record run-debug stop restart status logs \
        recordings clean-recordings install deps help

help: ## Show this help
	@echo ""
	@echo "  🦟 Mosquito Laser Tracker"
	@echo ""
	@echo "  Targets:"
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*## "}; {printf "    %-20s %s\n", $$1, $$2}'
	@echo ""
	@echo "  Options (override with VAR=value):"
	@echo "    CAMERA=raw_bayer    Camera mode: raw_bayer|usb|picamera|file"
	@echo "    AIM=none            Aim mode: none|servo|galvo"
	@echo "    PORT=8080           Web dashboard port"
	@echo "    RECORD=1            Enable recording on start"
	@echo "    RECORD_RAW=1        Also record raw camera feed"
	@echo "    EXTRA='--flag'      Extra flags passed to main.py"
	@echo ""
	@echo "  Examples:"
	@echo "    make run"
	@echo "    make run CAMERA=usb AIM=servo"
	@echo "    make run-record"
	@echo "    make run PORT=9090 EXTRA='--no-laser --no-ir'"
	@echo ""

run: stop ## Start tracker in background
	@echo "[make] Starting mosquito-laser..."
	@echo "[make] Camera=$(CAMERA) Aim=$(AIM) Port=$(PORT)"
	@nohup $(PY) $(APP) $(FLAGS) > $(LOGFILE) 2>&1 & \
		echo $$! > $(PIDFILE); \
		echo "[make] PID=$$(cat $(PIDFILE)), log=$(LOGFILE)"; \
		sleep 2; \
		if kill -0 $$(cat $(PIDFILE)) 2>/dev/null; then \
			echo "[make] Running. Dashboard: http://$$(hostname -I | awk '{print $$1}'):$(PORT)"; \
		else \
			echo "[make] FAILED to start. Check: make logs"; \
			cat $(LOGFILE) | tail -20; \
		fi

run-record: RECORD=1 ## Start tracker + recording
run-record: run

run-debug: stop ## Start in foreground (Ctrl-C to stop)
	$(PY) $(APP) $(FLAGS) 2>&1 | tee $(LOGFILE)

stop: ## Stop the tracker
	@if [ -f $(PIDFILE) ]; then \
		PID=$$(cat $(PIDFILE)); \
		if kill -0 $$PID 2>/dev/null; then \
			echo "[make] Stopping PID $$PID..."; \
			kill $$PID; \
			sleep 2; \
			kill -0 $$PID 2>/dev/null && kill -9 $$PID; \
			echo "[make] Stopped."; \
		else \
			echo "[make] Not running (stale PID)."; \
		fi; \
		rm -f $(PIDFILE); \
	else \
		echo "[make] Not running (no PID file)."; \
	fi

restart: stop run ## Restart the tracker

status: ## Show tracker status + live stats
	@if [ -f $(PIDFILE) ] && kill -0 $$(cat $(PIDFILE)) 2>/dev/null; then \
		PID=$$(cat $(PIDFILE)); \
		echo "[make] Running (PID $$PID)"; \
		echo ""; \
		curl -s --max-time 2 http://localhost:$(PORT)/api/status 2>/dev/null | \
			python3 -c "import sys,json;d=json.load(sys.stdin);det=d['detector'];rec=d.get('recorder',{});print(f'  FPS:        {det[\"fps\"]:.1f}');print(f'  Raw blobs:  {det[\"detections_raw\"]}');print(f'  Filtered:   {det[\"detections_filtered\"]}');print(f'  Tracks:     {det[\"active_tracks\"]} ({det[\"confirmed_tracks\"]} confirmed)');print(f'  Total seen: {det[\"total_tracks_created\"]}');print(f'  Recording:  {\"YES \" + str(rec.get(\"elapsed\",0)) + \"s\" if rec.get(\"recording\") else \"no\"}');print(f'  Aim mode:   {d[\"aim_mode\"]}')" \
			2>/dev/null || echo "  (cannot reach dashboard)"; \
	else \
		echo "[make] Not running."; \
	fi

logs: ## Tail the log file
	@tail -f $(LOGFILE) 2>/dev/null || echo "No log file yet. Run: make run"

recordings: ## List recorded sessions
	@if [ -d $(REC_DIR) ]; then \
		echo "Recordings in $(REC_DIR)/:" ; \
		ls -lhtr $(REC_DIR)/*.avi 2>/dev/null || echo "  (none)"; \
	else \
		echo "No recordings directory yet."; \
	fi

clean-recordings: ## Delete all recordings
	@echo "Deleting all recordings..."
	@rm -f $(REC_DIR)/*.avi
	@echo "Done."

deps: ## Install Python dependencies
	sudo apt install -y python3-opencv python3-flask python3-numpy v4l-utils

install: deps ## Full install (deps + create dirs)
	@mkdir -p $(REC_DIR)
	@echo "Installed. Run: make run"
