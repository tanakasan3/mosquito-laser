# 🦟 Mosquito Laser Tracker

DIY mosquito detection and laser spotter system. Detects mosquitoes using
computer vision (OpenCV background subtraction + tracking), then aims a
visible-light laser pointer at the insect so you can find and eliminate it.

**Non-lethal** -- this is a spotter, not a killer.

```
  ┌─────────────────────────────────────────┐
  │          SYSTEM OVERVIEW                 │
  │                                          │
  │   Camera ──► Detection ──► Tracking      │
  │                              │            │
  │              IR LEDs         ▼            │
  │             (850nm)    Aim Controller     │
  │                         (servo/galvo)     │
  │                              │            │
  │                         Laser Pointer     │
  │                          (5mW red)        │
  │                                          │
  │          Web Dashboard ◄── Status        │
  │         (live MJPEG + controls)          │
  └─────────────────────────────────────────┘
```


## Features

- Real-time mosquito detection via background subtraction + contour filtering
- Multi-object tracking with velocity estimation
- Two aiming modes: servo pan-tilt (cheap) or galvo mirrors (fast)
- Adjustable IR LED illumination with 555 timer (DC to ~1kHz)
- Live web dashboard with MJPEG stream, stats, and controls
- Live tuning of detection parameters from the browser
- Auto laser safety: timeout, cooldown, software kill switch
- Works with Pi Camera (NoIR), USB webcam, or test video files


## Hardware Options

### Option A: Servo Build (~$120-170)
Good for tracking **landed** mosquitoes. Servos are too slow for flight tracking.

### Option B: Galvo Build (~$170-250)
Can track mosquitoes **in flight**. Sub-millisecond mirror repositioning.


## Parts List

### Core (both builds)

| Part | Price | Links |
|------|-------|-------|
| Raspberry Pi 4 (4GB) | $55-75 | [Amazon](https://www.amazon.com/Raspberry-Model-2019-Quad-Bluetooth/dp/B07TC2BK1X) |
| Pi Camera V2 **NoIR** (no IR filter!) | $25-30 | [Amazon](https://www.amazon.com/Raspberry-Pi-NoIR-Camera-V2/dp/B01ER2SKFS) |
| OR: USB webcam (Logitech C920) | $50-60 | [Amazon](https://www.amazon.com/Logitech-Webcam-Calling-Recording-Stereo/dp/B085TFF7M1) |
| 5mW 650nm red laser module (10-pack) | $7-9 | [Amazon](https://www.amazon.com/HiLetgo-650nm-Laser-Module-Head/dp/B071FT9HSV) |
| 850nm IR illuminator (Tendelux BI8) | $16-20 | [Amazon](https://www.amazon.com/Tendelux-Illuminator-Infrared-Security-BI8/dp/B075ZYG89D) |
| OR: High-power 850nm IR LEDs (DIY circuit) | $5-10 | [Amazon](https://www.amazon.com/s?k=850nm+IR+LED+high+power) / [AliExpress](https://www.aliexpress.com/w/wholesale-850nm-ir-led.html) |
| NE555 timer ICs (25-pack) | $5-6 | [Amazon](https://www.amazon.com/Bridgold-25pcs-NE555P-Single-Precision/dp/B07Q2NRR7J) |
| IRF520 MOSFET driver modules (5-pack) | $7-9 | [Amazon](https://www.amazon.com/HiLetgo-IRF520-MOSFET-Driver-Arduino/dp/B01I1J14MO) |
| 10K potentiometers (10-pack) | $6-8 | [Amazon](https://www.amazon.com/MCIGICM-Potentiometer-Single-Linear-Taper/dp/B07MPSG1HJ) |
| MicroSD card (32GB+) | $8-10 | [Amazon](https://www.amazon.com/s?k=micro+sd+card+32gb) |
| 5V 3A USB-C power supply | $10-12 | [Amazon](https://www.amazon.com/s?k=raspberry+pi+4+power+supply) |
| Breadboard + jumper wires | $8-10 | [Amazon](https://www.amazon.com/s?k=breadboard+jumper+wire+kit) |

### Option A: Servo Build (add these)

| Part | Price | Links |
|------|-------|-------|
| SG90 micro servos (10-pack) | $15-20 | [Amazon](https://www.amazon.com/Miuzei-Micro-Servo-Motor-Helicopter/dp/B07MLR1498) |
| Pan-tilt bracket kit | $5-12 | [Amazon](https://www.amazon.com/s?k=pan+tilt+servo+bracket+camera) |

### Option B: Galvo Build (add these)

| Part | Price | Links |
|------|-------|-------|
| 20K/30K galvo scanner set (XY + drivers) | $25-80 | [AliExpress](https://www.aliexpress.com/w/wholesale-galvanometer-scanner.html) / [Amazon](https://www.amazon.com/s?k=galvo+scanner+set+30K) |
| MCP4922 dual 12-bit SPI DAC | $2-5 | [AliExpress](https://www.aliexpress.com/w/wholesale-mcp4922.html) / [Amazon](https://www.amazon.com/s?k=mcp4922) |
| +/-12V dual-rail power supply (for galvo amps) | $10-15 | [Amazon](https://www.amazon.com/s?k=dual+rail+power+supply+12v) |


## Wiring

Detailed wiring diagrams with ASCII schematics are in the `circuits/` folder:

- `circuits/servo_wiring.txt` -- Full servo build wiring (RPi + camera + servos + laser + IR)
- `circuits/galvo_wiring.txt` -- Full galvo build wiring (RPi + camera + galvos + DAC + laser + IR)
- `circuits/ir_led_circuit.txt` -- IR LED driver circuit with 555 timer (adjustable freq/duty)

### Quick Pin Reference

| Function | GPIO (BCM) | Physical Pin |
|----------|-----------|-------------|
| Pan servo PWM | GPIO12 | Pin 32 |
| Tilt servo PWM | GPIO13 | Pin 33 |
| Laser ON/OFF | GPIO18 | Pin 12 |
| IR LED enable | GPIO24 | Pin 18 |
| SPI MOSI (galvo) | GPIO10 | Pin 19 |
| SPI SCLK (galvo) | GPIO11 | Pin 23 |
| SPI CE0 (galvo) | GPIO8 | Pin 24 |


## Software Setup

### 1. Raspberry Pi OS

Flash Raspberry Pi OS (Bookworm, 64-bit) to your SD card.
Enable camera, SPI, and SSH via `raspi-config`.

### 2. Install dependencies

```bash
sudo apt update
sudo apt install -y python3-opencv python3-flask python3-numpy python3-pip
pip3 install spidev   # for galvo mode
```

### 3. Clone and run

```bash
git clone <this-repo>
cd mosquito-laser

# Servo mode (default)
python3 src/main.py --aim servo

# Galvo mode
python3 src/main.py --aim galvo

# Detection only (no aiming hardware needed)
python3 src/main.py --aim none --headless

# Test with a video file
python3 src/main.py --camera file --video test_mosquito.mp4 --aim none

# Custom port
python3 src/main.py --port 9090
```

### 4. Open dashboard

Navigate to `http://<pi-ip>:8080` in your browser.


## Dashboard

The web UI shows:
- **Live video** with detection overlay (annotated / raw / foreground mask)
- **Detection stats**: FPS, raw blobs, filtered, active/confirmed tracks
- **Active track list** with IDs, positions, velocities
- **Controls**: laser on/off, IR toggle, center aim, reset detector
- **Live tuning sliders**: min/max area, background threshold
- **Aimer state**: current servo angles or galvo DAC values


## Calibration

### Camera-to-Aimer Calibration

The system needs to know how pixel offsets map to aim angles:

1. Point the camera at a wall ~2-3m away
2. Turn on laser, center the aim
3. Note where the laser dot appears in the camera frame
4. Adjust `SERVO_DEG_PER_PX_X/Y` (servo) or `GALVO_VOLTS_PER_PX_X/Y` (galvo)
   in `src/config.py` until the laser tracks your finger accurately
5. Invert axes if needed (`SERVO_PAN_INVERT`, etc.)

### Detection Tuning

Use the dashboard sliders to tune for your environment:
- **Min/Max Area**: Filter contour sizes. Mosquitoes at 2-3m are ~4-50px²
- **BG Threshold**: Lower = more sensitive (more false positives). Higher = less sensitive
- Good IR illumination dramatically improves detection in low light


## IR LED Circuit

The IR illumination uses a 555 timer in astable mode driving IR LEDs via MOSFET:

```
     +12V ─────┬──────────────────────┐
               │                      │
             [R1 1K]               [IR LEDs]
               │                   4x 850nm
               ├──── Pin 7 (DIS)   in 2S2P
               │                      │
            [R2 POT]              [MOSFET]
            (0-100K)              IRLZ44N
               │                      │
               ├──── Pin 2/6         GND
               │     (THR/TRIG)
            [C1 470nF]
               │
              GND
```

- **Frequency range**: ~15 Hz to ~1.5 kHz (covers mosquito wing-beat band)
- **Adjust with potentiometer** -- no software changes needed
- **RPi GPIO24** controls 555 RESET pin for software on/off
- Full schematic in `circuits/ir_led_circuit.txt`


## Architecture

```
src/
├── main.py          # Main orchestrator and entry point
├── config.py        # All tunable parameters
├── camera.py        # Camera abstraction (Pi/USB/file)
├── detector.py      # Detection + tracking pipeline
├── aim_servo.py     # Servo pan-tilt controller
├── aim_galvo.py     # Galvo mirror controller (MCP4922 DAC)
├── laser.py         # Laser + IR LED GPIO control
└── dashboard.py     # Flask web UI + MJPEG streaming

templates/
└── index.html       # Dashboard frontend

circuits/
├── servo_wiring.txt    # Servo build wiring diagram
├── galvo_wiring.txt    # Galvo build wiring diagram
└── ir_led_circuit.txt  # IR LED driver circuit
```


## Safety

⚠️ **LASER SAFETY**: Even 5mW lasers can cause eye damage. Never look
directly into the beam. The system includes auto-off timers and a software
kill switch, but these are NOT substitutes for physical safety measures.

⚠️ **IR LEDS**: 850nm IR is invisible but can still damage eyes at close
range. Don't stare into IR illuminators.

⚠️ **ELECTRICAL**: The 555 timer + MOSFET circuit handles 12V. Use proper
current-limiting resistors. Don't exceed LED current ratings.


## Tips

1. **Best detection setup**: Dark room + IR illumination + NoIR camera.
   Mosquitoes appear as bright/dark moving blobs against IR-lit background.

2. **Start with `--aim none`** to tune detection before adding hardware.

3. **Test with video first**: Record mosquitoes with your phone, then test
   with `--camera file --video your_recording.mp4`.

4. **Servo limitations**: SG90 servos reposition in ~100-200ms. This is fine
   for mosquitoes on walls but too slow for flight tracking. Galvos are
   sub-millisecond.

5. **Reduce false positives**: Good, consistent lighting helps. Avoid the
   camera seeing ceiling fans, curtains, or other moving objects.

6. **Pi 4 performance**: Expect ~25-30 FPS at 640x480 with the full
   detection pipeline. The Pi 5 is significantly faster.


## License

MIT -- Build it, hack it, track those mosquitoes. 🦟🔫
