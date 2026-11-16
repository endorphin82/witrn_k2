# ⚡ WITRN K2 - Data Analysis Software (Linux & Windows)

**English** | [Українська](README.uk.md)

A full-featured cross-platform laboratory suite for analyzing, monitoring, and logging the metrics of the **WITRN K2** USB tester (Vendor ID `0716`, Product ID `5060`) under **Linux** (Arch, Ubuntu/Debian, Fedora) and **Windows** (10/11).

The software is built on top of open WITRN protocol reverse-engineering projects ([`lliooly/WITRN-K2-REVERSE`](https://github.com/lliooly/WITRN-K2-REVERSE), [`lliooly/witrn-k2-mac`](https://github.com/lliooly/witrn-k2-mac) and the findings of [`didim99/usbmeter-utils`](https://github.com/didim99/usbmeter-utils)).

---

## 🌟 Key Features

- **Direct reads without third-party lockouts**:
  - **Linux**: native access to the `/dev/hidrawX` kernel node without libusb interface capture issues.
  - **Windows**: works through the built-in system HID stack (`hidapi`); no extra drivers or WinUSB needed (Plug & Play).
  - Reads 64-byte telemetry packets in real time (up to 100 Hz).
  - Double checksum verification (internal over bytes `[8:62]` and external over `[:62]`).
- **Measured and computed values**:
  - VBUS voltage (V, up to 4 decimal places).
  - Signed bus current IBUS (A, forward/reverse).
  - Instantaneous power (W).
  - Dynamic load resistance (Ω, $R = V / |I|$).
  - Fast-charging signal lines: D+ and D- (V).
  - Temperature sensors: internal CPU sensor and external NTC probe (°C).
  - K2 hardware counters (Ah, Wh, recording time, uptime).
- **Modern Web Dashboard (SPA)**:
  - Dark laboratory theme with large, highly visible digital indicators.
  - High-speed real-time Canvas chart with zoom, pan, and time-window selection (10s, 30s, 1min, 5min, All).
  - Toggle individual channels (V, I, P, R, D+/D-, T).
  - Crosshair with instant value readout on hover.
- **Flexible logging and recorder**:
  - SQLite storage with a WAL journal (protects against crashes and data corruption).
  - Configurable save rate: 1 Hz, 10 Hz, 50 Hz, 100 Hz, or full speed.
  - Auto-Stop: a trigger that fires when current or power stays below a set threshold for a given duration (charge-completion detection).
- **Analytics and integration**:
  - Piecewise-linear integration separating forward and reverse current across zero.
  - Capacity (mAh forward / reverse / net) and energy (mWh forward / reverse / net) computation.
  - Statistics table: Min, Max, time-weighted average, ripple range (Peak-to-Peak $V_{pp}$, $I_{pp}$).
- **Compatibility and export**:
  - **Official WITRN CSV** (UTF-8 BOM, compatible with the original WITRN software and MS Excel).
  - **Standard CSV** with all engineering fields.
  - **JSON** with summary statistics and the measurement array.
  - **SQLite** file of the original recording.
  - **Import** of previously saved WITRN CSV files for retrospective analysis.
- **Simulator mode**:
  - Fully test graphs and features even without the physical tester connected.

---

## 📦 Dependency Installation

### Windows (in 1 click):
- **File Explorer / CMD:** double-click `install.bat`
- **PowerShell:** `.\install.ps1` (or `powershell -ExecutionPolicy Bypass -File .\install.ps1`)

> [!IMPORTANT]
> If PowerShell blocks script execution (`*.ps1`) due to the execution policy, first run this in the current PowerShell window:
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process
> ```
> The policy applies only to the current process (PowerShell window) and is automatically revoked once it is closed — no system-wide changes are persisted.

The script automatically:
1. Finds a compatible Python interpreter (Python 3.10–3.13 recommended, for which prebuilt `hidapi`, `PyQt6` and `pyyaml` packages exist without needing the Microsoft Visual C++ Build Tools).
2. Creates an isolated `.venv` virtual environment.
3. Upgrades `pip` and installs all required modules from `requirements.txt`.
4. Verifies integrity and successful library imports.

> [!TIP]
> The launch scripts (`run_gui.bat`, `run.bat`, `menu.bat`) will also invoke `install.bat` automatically if the `.venv` environment has not been initialized yet.

### Linux:
```bash
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
sudo ./setup_udev.sh
```

---

## 🚀 Quick Start

### 🎮 Main interactive menu (all in one):
- **Linux:** `./menu.sh`
- **Windows CMD:** `menu.bat` (double-click)
- **PowerShell:** `.\menu.ps1`

Lets you pick any operating mode in a single click without memorizing parameters.

---

### 📂 Ready-made scripts for different scenarios:

| Launch scenario | Linux | Windows (CMD / Explorer) | Windows (PowerShell) | Description |
|---|---|---|---|---|
| **Install dependencies** | — | `install.bat` | `.\install.ps1` | Automatic setup of `.venv` and all libraries |
| **Web interface (SPA)** | `./run.sh` | `run.bat` | `.\run.ps1` | Launch the modern dashboard at `http://127.0.0.1:8000` |
| **Desktop GUI** | `./run_gui.sh` | `run_gui.bat` | `.\run_gui.ps1` | Native PyQt6 app with high-speed graphs |
| **Main menu** | `./menu.sh` | `menu.bat` | `.\menu.ps1` | Interactive menu with all modes |
| **Terminal TUI** | `./run_tui.sh` | `run_tui.bat` | — | Full-screen terminal dashboard with sparkline graphs |
| **TUI Simulator** | `./run_tui_sim.sh` | `run_tui_sim.bat` | — | TUI dashboard in simulator mode (no physical tester) |
| **Live monitor** | `./run_live.sh` | `run_live.bat` | — | Lightweight one-line monitor of live values |
| **Charge test** | `./record_charge.sh` | `record_charge.bat` | — | Auto-stop when charging finishes (<50 mA) + WITRN CSV export |
| **High-speed recording** | `./record_100hz.sh` | `record_100hz.bat` | — | Recording at the maximum 100 Hz rate for ripple analysis |

> [!NOTE]
> On Windows, third-party USB drivers (Zadig / WinUSB) are **not required** — K2 works as a standard USB HID device.
> Before launching, make sure the official WITRN program is closed (otherwise it blocks access to the device).

---

## 🔒 Access Permissions Setup in Linux (udev)

In Linux, `hidraw` devices are accessible only to `root` by default. To use the application without `sudo`:

### Permanent setup (recommended):
```bash
sudo ./setup_udev.sh
```
This copies the `99-witrn-k2.rules` rule into `/etc/udev/rules.d/` and reloads the udev subsystem.

### Or a quick one-time access:
```bash
sudo chmod 666 /dev/hidraw*
```

---

## 💻 Console Interface (`witrn-cli`)

The utility supports all core operations from the terminal:

> [!NOTE]
> The commands below use the Linux syntax (`.venv/bin/python`).
> On **Windows**, use `.venv\Scripts\python.exe` or the corresponding one-click `.bat` / `.ps1` scripts.

### Connection diagnostics:
```bash
.venv/bin/python -m witrn_k2.cli info
```

### Live terminal monitor:
```bash
.venv/bin/python -m witrn_k2.cli live
```

### Native GUI application (PyQt6):
```bash
# Launch the graphical interface (dark laboratory theme, real-time graphs):
.venv/bin/python -m witrn_k2.cli gui
```
**GUI capabilities:**
- Real-time V / I / P graphs with pyqtgraph (zoom/pan with precise time synchronization, antialias)
- Large metrics: V, I, P, Ω, T, Ah
- **Load recordings** (SQLite and CSV) for retrospective analysis
- **Export**: WITRN CSV, standard CSV, JSON, **vector SVG graphs** (single file, all three plots)
- **Crosshair** with instant value readout at any point
- **Moving average** (configurable window) as an overlay on the graphs
- **Peak detection** with adjustable sensitivity
- **Session comparison**: load a reference session as a dotted overlay
- **Report generation**: charging phases, top peaks, Δ vs. reference, integral metrics
- **Table view** of the data (up to 2000 rows)
- Recording at 1/10/50/100 Hz rates with auto-stop

**GUI hotkeys:**

| Key | Action |
|---|---|
| `F5` | Connect |
| `Esc` | Disconnect |
| `F9` | Start/stop recording |
| `Ctrl+O` | Load recording (SQLite) |
| `Ctrl+Shift+O` | Load CSV |
| `Ctrl+S` | Export WITRN CSV |
| `Ctrl+Shift+S` | Export standard CSV |
| `Ctrl+J` | Export JSON |
| `Ctrl+Shift+V` | Export graphs as vector SVG |
| `Ctrl+R` | Analysis report |
| `C` / `M` / `P` | Cursor / moving average / peaks |
| `Ctrl+0` | Reset zoom |
| `Ctrl+Delete` | Clear live data |
| `Ctrl+Shift+R` | Reference session |
| `F1` | Keyboard help |
| `Ctrl+Q` | Quit |

### Full-screen terminal dashboard (TUI):
```bash
# Dashboard with real-time sparkline graphs:
.venv/bin/python -m witrn_k2.cli dash --simulator

# Dashboard with parallel recording to SQLite:
.venv/bin/python -m witrn_k2.cli dash --record -r 10 -o recordings/cap.sqlite
```

### Data logging to file (Headless logger):
```bash
# Record for 60 seconds at 10 Hz with CSV export:
.venv/bin/python -m witrn_k2.cli record -d 60 -r 10 --format witrn_csv -o recordings/test.sqlite

# Record with auto-stop when the current drops below 50 mA for 10 s:
.venv/bin/python -m witrn_k2.cli record --auto-stop --threshold 0.05 --trigger-duration 10
```

### Analyze a saved session (SQLite or CSV):
```bash
.venv/bin/python -m witrn_k2.cli analyze recordings/test.sqlite
```

---

## 📁 Project Structure

```
custom_soft_for_official_fw/
├── 99-witrn-k2.rules         # udev rules for passwordless access in Linux
├── setup_udev.sh             # udev rules installation script (Linux)
├── install.bat               # Dependency installer for Windows (CMD / Explorer)
├── install.ps1               # Dependency installer for Windows (PowerShell)
├── run.bat                   # Launch the web interface (Windows CMD)
├── run.ps1                   # Launch the web interface (Windows PowerShell)
├── run.sh                    # Launch the web interface (Linux)
├── run_gui.bat               # Launch the desktop PyQt6 GUI (Windows CMD)
├── run_gui.ps1               # Launch the desktop PyQt6 GUI (Windows PowerShell)
├── run_gui.sh                # Launch the desktop PyQt6 GUI (Linux)
├── menu.bat                  # Main menu (Windows CMD)
├── menu.ps1                  # Main menu (Windows PowerShell)
├── menu.sh                   # Main menu (Linux)
├── requirements.txt          # Minimal set of Python dependencies
├── witrn_k2/
│   ├── core/
│   │   ├── protocol.py       # 64-byte frame, validation, double checksum
│   │   ├── telemetry.py      # 0x1A packet decoding, normalization, Sampler
│   │   ├── transport.py      # Native Linux hidraw, hidapi, K2 simulator
│   │   ├── recorder.py       # SQLite WAL recorder, segments, auto-stop triggers
│   │   ├── analytics.py      # Piecewise capacity/energy integrals, statistics
│   │   └── exporter.py       # Export/import of official CSV/SQLite, standard CSV, JSON
│   ├── web/
│   │   ├── app.py            # FastAPI server, REST API, telemetry WebSocket streamer
│   │   └── static/
│   │       ├── index.html    # Interactive instrument panel (SPA)
│   │       ├── style.css     # Dark laboratory theme styling
│   │       └── app.js        # Canvas chart engine and WebSocket client
│   ├── cli.py                # witrn-cli console utility
│   ├── tui.py                # Full-screen terminal dashboard (rich TUI)
│   ├── gui.py                # Native GUI application (PyQt6 + pyqtgraph)
│   └── svgfix.py             # SVG export compatibility of pyqtgraph with Qt 6.x
├── tests/                    # Automated test suite
│   ├── test_protocol.py
│   ├── test_telemetry.py
│   ├── test_recorder.py
│   └── test_analytics.py
└── recordings/               # Directory for logs and SQLite databases
```

---

## 🧪 Running Tests

To run all unit tests:
```bash
.venv/bin/python -m unittest discover -s tests
```
