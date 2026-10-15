# 🎬 Film Studio

A desktop application designed for Windows 10/11 (Python 3.11+) that controls a live **Antigravity CLI (`agy`)** session to direct AI film pipelines using **`gflow-cli` (Google Flow / Veo)**, and monitors generation progress in real time.

---

## 🌟 Visual Layout & Screenshot Description

The interface features a **dark, cinematic aesthetic** with a deep charcoal palette (`#0c0f12`), neon teal accents (`#00e5b7`), soft ambient shadows, rounded container cards, and responsive typography:

```
+----------------------------------------------------------------------------------------------------------------------+
| 🎬 FILM STUDIO  [AGY • GFLOW VEO]          ● [GENERATING]                 [⚡ Check gflow]  [📁 Jobs Folder]        |
+----------------------------------+---------------------------------------------------+-------------------------------+
| ⚙️ JOB SETTINGS                   | 💻 LIVE AGY TERMINAL                              | 📊 LIVE MONITOR               |
|                                  | [agy 1.3.6] ● RUNNING  [▶ Start] [■ Stop] [↻] [⌫] |                               |
| • Title: Neon Horizons           | +-----------------------------------------------+ | • Active: job_20261016_0012   |
| • Story: Courier delivery ...    | | > agy interactive prompt                      | | • Folder: ./jobs/job_...      |
| • Style: Cyberpunk 35mm          | | > Generating scene 001 with gflow veo...      | | • Timer:  02:45             |
| • Duration: 1.0 min (8s / clip)  | | > ffmpeg concat final_film.mp4                | |                               |
| • Aspect: 16:9 | Res: 1080p      | |                                               | | • Clips: 8 / 8 found [100%] |
| • Characters (pasted in scenes): | |                                               | | [=========================] |
|   - Kira: Teal cybernetic eyes   | |                                               | |                               |
| • Narration: ON (Christopher)    | |                                               | | Scene Tiles:                |
| • Music: ON | Duck Audio: ON     | |                                               | | [sc_001][sc_002][sc_003]... |
| • Budget: 50 credits             | |                                               | | (Green: Found | Amber: Write) |
| • [✓] Pause & ask before spend   | |                                               | |                               |
|   (Unchecked shows RED WARNING)  | |                                               | | Final Film: [FOUND]         |
| • Output: ./jobs                 | |                                               | | ▶ [ HTML5 Video Player ]   |
|                                  | |                                               | | • 01:04 • 14.2 MB           |
| [ ⚡ RUN JOB ] (Glow effect)     | +-----------------------------------------------+ | • Assets: scenes.json, story  |
|                                  | ⌨ Tip: Type directly inside terminal ("go", "y")| • Progress Log (last 20 lines)|
|                                  |                                                   | • Job History (switch & re-run)|
+----------------------------------+---------------------------------------------------+-------------------------------+
```

### Three-Column Architecture (Closeable & Resizable):
1. **Left: Job Settings (Closeable & Resizable)**
   - Collapse button `◀` to tuck away the sidebar and give the live terminal more room.
   - Draggable resizer divider to adjust sidebar width (240px - 700px, saved in `localStorage`).
   - Title, multi-line Story premise, Style description.
   - Video duration, seconds per clip (default 8s), aspect ratio, resolution.
   - Dynamic character rows: full visual descriptions injected into every scene prompt.
   - Voice narration toggle (`edge-tts` voices) + background music + ducking options.
   - Credit budget limit and "Pause and ask me before spending credits" safety toggle.
   - Read-only "Check gflow" diagnostics button.
   - Primary "Run Job" launch button (automatically greys out with spinner when running).
2. **Center: Live agy Terminal**
   - VT100 interactive PTY running real `agy` session using `pywinpty` (WinPTY backend).
   - Starts automatically when the app opens.
   - Streamed over authenticated WebSocket to `xterm.js` with `FitAddon`.
   - Smooth, non-blocking I/O pipeline that never freezes the terminal during prompt injections or generation turns.
   - Bidirectional: type directly into the terminal at any time to answer agy (e.g., typing `"go"` or approval prompts).
   - Session status controls: Start, Stop (sends `Ctrl+C` / `\x03`), Restart, Clear.
3. **Right: Live Monitor (Closeable & Resizable)**
   - Collapse button `▶` to tuck away the monitor and give the terminal full width.
   - Draggable resizer divider to adjust monitor width.
   - Real-time job telemetry via WebSocket.
   - Clips progress bar and numbered scene grid (`scene_001` ... `scene_N`).
   - **Stable-Size Rule**: A clip counts as found only when it is `>100 KB` and its size stopped changing across two polls.
   - Duration extraction via `ffprobe` (cached).
   - In-app HTML5 video preview player for finished scenes and `final_film.mp4`.
   - Asset indicators (`scenes.json`, `story.md`, audio files).
   - Tail of `progress.log` (last 20 lines).
   - Job history drawer with one-click folder opening and prompt re-submission.

### Video Generation Command Syntax:
The AI prompt explicitly instructs agy to generate clips using:
```bash
gflow video t2v "<prompt>" --aspect 16:9 -o ./clips/scene_001.mp4
# Example:
gflow video t2v "A calm lake at sunrise, slow cinematic pan" --aspect 16:9
```

---

## 🔒 Safety & Credit Protection Rules

- **Zero Autonomous Spending by App**: The backend app **never** executes `gflow auth login` or video generation commands. Only read-only diagnostics (`gflow auth status` and `gflow credits user`) are permitted.
- **Credit Limits Enforced in Prompts**: The prompt builder rigorously instructs agy with credit budgets, stopping criteria, and cost confirmation steps before any generation turn.
- **No Credentials Stored**: The app never stores, prompts for, or logs passwords, session tokens, or API keys.

---

## 🚀 Quick Start Guide

### 1. Setup Environment
Run the setup batch script to install dependencies and verify offline vendor assets:
```cmd
setup.bat
```
*(Installs `fastapi`, `uvicorn`, `pywinpty`, `watchdog`, `pywebview`, `pytest`, etc., and vendors `xterm.js` into `static/vendor`.)*

### 2. Launch Film Studio
Run the application launcher:
```cmd
run.bat
```
- Film Studio starts the local server on `127.0.0.1:8765` with a cryptographically secure startup token.
- Opens a dedicated desktop window via `pywebview`.
- If pywebview is unavailable, it automatically falls back to your default web browser.

---

## 🧪 Testing & Verification

The test suite includes complete unit tests and end-to-end integration tests using an interactive fake `agy` stub:

```cmd
python -m pytest tests -v
```

### Included Tests:
- `tests/test_prompt_builder.py`: Validates prompt generation, approval mode variants (ON/OFF), clip count rounding, character description formatting, and fallback commands.
- `tests/test_job_manager.py`: Tests unique folder naming (`job_<YYYYMMDD_HHMMSS>_<4rand>/`), subfolder hierarchy (`script`, `clips`, `audio`, `final`), `job.json`, `prompt.md`, and active job detection.
- `tests/test_watcher.py`: Verifies the `>100 KB` stable size rule, size polling, writing-to-found state transitions, and `Done` badge detection.
- `tests/test_e2e_stub.py`: Full end-to-end integration test with `tests/fake_agy.py` exercising PTY startup, terminal output streaming, prompt injection, clip detection, final video detection, and job history.
- `tests/test_real_agy_smoke.py`: Smoke test validating real `agy.exe` binary execution and harmless prompt interaction.

---

## 📁 Project Structure

```
Project_Astra/
├── app.py                     # FastAPI application & pywebview desktop runner
├── requirements.txt           # Dependencies
├── setup.bat                  # One-click Windows setup script
├── run.bat                    # One-click Windows launch script
├── NOTES.md                   # Documented agy & gflow CLI research findings
├── README.md                  # System guide & screenshot description
├── settings.json              # Persistent user preferences
├── backend/
│   ├── __init__.py
│   ├── pty_session.py         # pywinpty interactive terminal session manager
│   ├── prompt_builder.py      # Standardized film prompt generator
│   ├── job_manager.py         # Folder structure, job.json, history tracking
│   ├── watcher.py             # Watchdog filesystem monitor & stable size detection
│   └── gflow_tools.py         # Read-only gflow auth status & credits checker
├── static/
│   ├── index.html             # 3-column studio layout
│   ├── style.css              # Dark cinematic CSS theme
│   ├── app.js                 # Vanilla frontend logic & xterm bridge
│   └── vendor/                # Offline vendored assets
│       ├── xterm.js
│       ├── xterm.css
│       └── xterm-addon-fit.js
└── tests/
    ├── __init__.py
    ├── fake_agy.py            # Mock agy CLI stub for offline testing
    ├── test_prompt_builder.py # Unit tests for prompt builder
    ├── test_job_manager.py    # Unit tests for job manager
    ├── test_watcher.py        # Unit tests for watcher & stable-size detection
    ├── test_e2e_stub.py       # Full pipeline end-to-end test
    └── test_real_agy_smoke.py # Live smoke test for real agy execution
```
