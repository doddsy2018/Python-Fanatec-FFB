# Fanatec Python Driver

Python library and example scripts for controlling Fanatec steering wheels on Windows via DirectInput (SDL2) and raw HID. Enables programmatic force-feedback configuration, closed-loop wheel angle control, and live input monitoring without a sim game running.

## Requirements

- **Windows 10/11** (SDL2 DirectInput and raw HID are Windows-only)
- **Python 3.12+**
- **Poetry** (dependency manager)
- Fanatec wheel base connected and recognized as a game controller (check Device Manager / joy.cpl)
- Run scripts **as Administrator** if the HID vendor layer reports unavailable

## Setup & Install

```bash
# Install Poetry if you don't have it
pip install poetry

# Install project dependencies into a local .venv
poetry install

# Activate the virtual environment
poetry shell
```

Alternatively, install dependencies directly:

```bash
pip install pygame hidapi numpy keyboard carla
```

## Files

### Libraries

| File | Description |
|------|-------------|
| [lib_fanatec_controller_with_pid.py](lib_fanatec_controller_with_pid.py) | Core library — SDL2 DirectInput FFB, raw HID vendor commands, PID closed-loop angle control |
| [lib_fanatec_controller_with_mpc.py](lib_fanatec_controller_with_mpc.py) | Same as above with an MPC (Model Predictive Control) angle controller instead of PID |

Both libraries expose the same public API:

- `FanatecDirectInput` — SDL2 haptic layer: play/stop constant force, sine, spring, damper, friction, inertia effects
- `FanatecHID` — Raw HID vendor commands: set steering range, FFB strength, damper, friction, LED control
- `FFBPreset` / `PRESETS` — Named FFB configurations (`road`, `gt`, `formula`, `drift`, `menu`, `snap`)
- `apply_preset(di, hid_dev, preset)` — Apply a preset to both layers at once
- `AngleHoldController` — Threaded closed-loop controller that drives the wheel to a target angle and holds it
- `get_values(js)` — Read current axis, button, and hat state as a dict

### Example Scripts

| Script | What it does |
|--------|-------------|
| [1_fanatec_ffb_with_get_values.py](1_fanatec_ffb_with_get_values.py) | Apply the `snap` preset and print live wheel values at 30 Hz |
| [2_fanatec_drive_wheel_pid.py](2_fanatec_drive_wheel_pid.py) | PID angle hold — use `+`/`-` keys to move the wheel to a target angle |
| [3_fanatec_drive_with_MPC.py](3_fanatec_drive_with_MPC.py) | Same as above but uses the MPC controller (900° range) |
| [4_fanatect_effect.py](4_fanatect_effect.py) | Raw effect playback demo — cornering load (constant force) then a kerb-hit (sine) |

### CARLA Integration

| Script | What it does |
|--------|-------------|
| [carla_manual_control_fanatec_wheel.py](carla_manual_control_fanatec_wheel.py) | Drive a CARLA vehicle with the Fanatec wheel — steering, throttle, and brake mapped from raw axis inputs with MPC-based FFB |

## Usage

### 1. Monitor inputs with FFB active

```bash
python 1_fanatec_ffb_with_get_values.py
```

Applies the `snap` preset (strong spring centering), then prints axis/button/hat values at 30 Hz. Press `Ctrl+C` to stop.

### 2. PID angle hold (360° range)

```bash
python 2_fanatec_drive_wheel_pid.py
```

Applies a custom FFB preset then activates the PID controller at 0°. Use `+` / `-` to command the wheel to move in 5° steps. Press `Q` to quit.

### 3. MPC angle hold (900° range)

```bash
python 3_fanatec_drive_with_MPC.py
```

Same keyboard controls as above, but uses the MPC controller on a 900° steering range. The MPC solves a 10-step horizon quadratic program at construction; online computation is a single matrix multiply.

### 4. Raw FFB effects demo

```bash
python 4_fanatect_effect.py
```

Plays a 2-second cornering load (constant force at level 14000), waits, then plays a 500 ms kerb-hit (sine at 20000 magnitude, 60 ms period). No user interaction required — runs and exits.

### 5. CARLA manual control with Fanatec wheel

**Prerequisites:** A running CARLA server (default `localhost:2000`) and the `carla` Python package installed.

```bash
python carla_manual_control_fanatec_wheel.py
```

Optional arguments:

| Flag | Default | Description |
|------|---------|-------------|
| `--host H` | `127.0.0.1` | CARLA server IP |
| `-p PORT` | `2000` | CARLA server TCP port |
| `-a` | off | Start with autopilot enabled |
| `--res WxH` | `1280x720` | Display resolution |
| `--filter PATTERN` | `vehicle.*` | Actor blueprint filter |
| `-v` | off | Verbose debug logging |

The script spawns a random vehicle matching the filter, attaches collision, lane-invasion, GNSS, and camera sensors, and hands control to the `DualControl` class which reads both keyboard and wheel inputs each frame.

**Wheel axis mapping (joystick index 1):**

| Axis | Input | Transform |
|------|-------|-----------|
| A0 | Steering | `steer = tan(1.1 × A0)` |
| A1 | Throttle pedal | log-curve mapped to [0, 1] |
| A4 | Brake pedal | log-curve mapped to [0, 1] |

FFB is applied via `lib_fanatec_controller_with_mpc` using the `snap` preset on startup.

**Wheel button mapping:**

| Button | Action |
|--------|--------|
| 0 | Respawn vehicle |
| 1 | Toggle HUD info overlay |
| 2 | Toggle camera position |
| 3 | Cycle weather preset |
| 23 | Cycle sensor type |

**Keyboard controls:**

| Key | Action |
|-----|--------|
| `W` / `↑` | Throttle |
| `S` / `↓` | Brake |
| `A` / `←` | Steer left |
| `D` / `→` | Steer right |
| `Space` | Hand brake |
| `Q` | Toggle reverse |
| `M` | Toggle manual gear shift |
| `,` / `.` | Shift down / up (manual mode) |
| `P` | Toggle autopilot |
| `C` / `Shift+C` | Cycle weather forward / backward |
| `Tab` | Toggle camera position |
| `` ` `` | Cycle sensor |
| `1`–`9` | Select sensor by index |
| `R` | Toggle frame recording |
| `F1` | Toggle HUD info |
| `H` / `?` | Toggle help overlay |
| `Backspace` | Respawn vehicle |
| `Escape` / `Ctrl+Q` | Quit |

## Configuration

### Joystick index

Each script sets `joystick_index = 1` near the top. If your wheel is not at index 1, open Device Manager or run a joystick enumeration and change this value:

```python
joystick_index = 0  # adjust to match your wheel
```

### FFB presets

Built-in presets in both libraries:

| Key | Name | Gain | Spring | Damper | Range |
|-----|------|------|--------|--------|-------|
| `road` | Road Car | 75% | 16000 | 8000 | 900° |
| `gt` | GT / Race Car | 85% | 22000 | 12000 | 720° |
| `formula` | Formula | 90% | 28000 | 16000 | 360° |
| `drift` | Drift | 70% | 8000 | 4000 | 720° |
| `menu` | Menu | 50% | 20000 | 5000 | 540° |
| `snap` | Snap Center | 85% | 32000 | 2000 | 360° |

Apply a preset:

```python
fc.apply_preset(di, hid_dev, fc.PRESETS["gt"])
```

Or define a custom one:

```python
my_preset = fc.FFBPreset("custom", gain_pct=80.0, autocenter_pct=0,
                          spring_coeff=20000, damper_coeff=10000,
                          friction_coeff=6000, inertia_coeff=7000,
                          hw_ffb_pct=80, steering_range=540)
fc.apply_preset(di, hid_dev, my_preset)
```

### Angle hold controller

```python
ctrl = fc.AngleHoldController(di, js, steering_range=360.0, poll_hz=120.0)
ctrl.activate(0.0)        # drive to centre and hold
ctrl.set_target(90.0)     # move to 90° right and hold
ctrl.deactivate()         # release
```

## Notes

- The HID vendor layer (`FanatecHID`) requires the wheel to be recognised under the Fanatec VID (`0xEB7`). If it reports unavailable, the DirectInput layer still works for effects — only hardware-level settings (range, FFB strength %) will be skipped.
- SDL2 is loaded from the pygame bundle (`pygame/SDL2.dll`) — no separate SDL2 install needed.
- The `keyboard` library requires elevated privileges on some Windows configurations. If key detection fails, run the script as Administrator.
