# Film Studio - System Notes & CLI Findings

## 1. Antigravity CLI (`agy`) Findings

- **Executable Location**: `C:\Users\onlyg\AppData\Local\agy\bin\agy.exe`
- **Version**: `1.3.6`

### Flags & Modes
- **Non-interactive / Print Mode**:
  - `--print` (alias `-p` or `--prompt`): Runs a single prompt non-interactively and prints the response.
  - `--output-format <text|json|stream-json>`: Controls output representation (default `text`).
  - `--input-format <text|stream-json>`: For NDJSON turn-by-turn input in print mode.
  - `--print-timeout <duration>`: Optional timeout (default `0s` waits until turn completion).
  - `--disable-slash-commands`: Prevents slash command and skill expansion in print mode.
- **Working Directory / Workspace Configuration**:
  - Setting process working directory (`cwd`) when spawning `agy` establishes the initial active workspace.
  - `--add-dir <path>`: Repeatable flag to dynamically add extra directories to the workspace.
- **Interactive TUI & Multi-line Input**:
  - Default execution runs an interactive TUI session with rich formatting and live prompts.
  - `-i` / `--prompt-interactive`: Runs an initial prompt interactively and continues the interactive session.
  - Multi-line paste behavior: Directly typing or piping raw `\n` or `\r\n` can trigger premature submission on the first newline.
  - **Bracketed Paste**: Modern terminals send bracketed paste sequences: `\x1b[200~` + `<multi-line prompt>` + `\x1b[201~` followed by `\r` (Enter). This tells the TUI that the enclosed text is a single pasted payload.
  - **Safe Fallback**: If bracketed paste is rejected or split by the interactive shell, the app falls back to sending:
    `Read <absolute path to job folder>/prompt.md and follow it exactly` + `\r\n`.
  - **PTY Driver on Windows**: Python `pywinpty` with `winpty.enums.Backend.WinPTY` provides robust bi-directional PTY streaming, ANSI parsing, and window resize (`setwinsize`) support.

---

## 2. Google Flow CLI (`gflow`) Findings

- **Executable Location**: `C:\Users\onlyg\.local\bin\gflow.exe`
- **Version**: `0.85.0`

### Authentication & Account Inspection (Read-Only)
- `gflow auth status`: Probes the Flow session endpoint with profile cookies without launching a full browser and without spending credits. Returns exit code `0` when verified, `1` otherwise.
- `gflow credits user`: Retrieves profile credit balance.
  - Supports `--json` flag to emit structured machine-readable JSON.
  - Returns `AisandboxAuthError` or balance data if session lacks tokens or requires refresh.
  - **Safety constraint**: Never execute `gflow auth login` or generation commands from the app backend; the app only runs read-only `status` and `credits user` subprocess checks.

### Video Generation & Movie Pipeline
- Video Generation Command:
  `gflow video t2v "<prompt>" --aspect <aspect> -o ./clips/scene_001.mp4`
  - Example: `gflow video t2v "A calm lake at sunrise, slow cinematic pan" --aspect 16:9`
  - Aspect options: `16:9`, `9:16`
  - Explicit output option: `-o, --output FILE`
- Commands available in `gflow`:
  - `gflow video t2v`: Text to video.
  - `gflow video i2v`: Image to video.
  - `gflow video r2v`: Reference images to video.
  - `gflow video chain`: Chain multiple clips into continuous sequences.
  - `gflow movie run`: Multi-scene execution from `movie.toml`.
  - `gflow character create`: Character entity management for consistent visual generation.
- Media tools:
  - `ffmpeg` & `ffprobe`: Gyan.FFmpeg installed and accessible in PATH for concatenation and clip duration inspection.
  - `edge-tts`: Installed for Python-driven TTS narration generation.
