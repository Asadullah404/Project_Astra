"""PTY Session Manager for Film Studio.

Spawns and manages a live PTY running agy (using pywinpty on Windows, ptyprocess on Unix),
bridges bidirectional I/O to WebSockets/xterm.js, handles bracketed paste, terminal resizing,
and session lifecycle control.
"""
import asyncio
import os
import shutil
import subprocess
import sys
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Set

IS_WINDOWS = sys.platform == "win32"

if IS_WINDOWS:
    try:
        import winpty
        WINPTY_AVAILABLE = True
    except ImportError:
        WINPTY_AVAILABLE = False
        winpty = None
else:
    try:
        import ptyprocess
        PTYPROCESS_AVAILABLE = True
    except ImportError:
        PTYPROCESS_AVAILABLE = False
        ptyprocess = None


def find_agy_executable() -> Optional[str]:
    """Locate agy executable on host system."""
    override = os.environ.get("FILM_STUDIO_AGY_CMD")
    if override:
        return override

    found = shutil.which("agy")
    if found:
        return found

    if IS_WINDOWS:
        candidate = os.path.expandvars(r"%LOCALAPPDATA%\agy\bin\agy.exe")
        if os.path.exists(candidate):
            return candidate
        candidate2 = os.path.expanduser(r"~\AppData\Local\agy\bin\agy.exe")
        if os.path.exists(candidate2):
            return candidate2

    return None


def get_agy_version(exe_path: Optional[str]) -> str:
    """Retrieve version string from agy executable."""
    if not exe_path:
        return "Not Installed"
    try:
        res = subprocess.run([exe_path, "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=3)
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    except Exception:
        pass
    return "Unknown"


class PtySession:
    """Manages a single interactive PTY process running agy."""

    def __init__(self, cwd: Optional[str] = None):
        self.cwd = os.path.abspath(cwd) if cwd else os.getcwd()
        self.process: Optional[Any] = None
        self.state: str = "stopped"  # "starting", "running", "stopped", "error"
        self.error_message: Optional[str] = None
        self.exe_path: Optional[str] = find_agy_executable()
        self.version: str = get_agy_version(self.exe_path)
        self.cols: int = 100
        self.rows: int = 30
        self._reader_thread: Optional[threading.Thread] = None
        self._is_terminating: bool = False
        self._output_listeners: Set[Callable[[str], None]] = set()
        self._state_listeners: Set[Callable[[str], None]] = set()
        self._history_buffer: List[str] = []
        self._max_history_chars: int = 250000

    def add_output_listener(self, callback: Callable[[str], None], replay_history: bool = True):
        """Add a callback to receive terminal output chunks."""
        self._output_listeners.add(callback)
        if replay_history and self._history_buffer:
            replay_text = "".join(self._history_buffer)
            try:
                callback(replay_text)
            except Exception:
                pass

    def remove_output_listener(self, callback: Callable[[str], None]):
        """Remove an output callback."""
        self._output_listeners.discard(callback)

    def add_state_listener(self, callback: Callable[[str], None]):
        """Add a callback for state changes."""
        self._state_listeners.add(callback)
        callback(self.state)

    def remove_state_listener(self, callback: Callable[[str], None]):
        """Remove a state callback."""
        self._state_listeners.discard(callback)

    def _set_state(self, state: str, error: Optional[str] = None):
        """Update and broadcast session state."""
        self.state = state
        self.error_message = error
        for cb in list(self._state_listeners):
            try:
                cb(state)
            except Exception:
                pass

    def _broadcast_output(self, data: str):
        """Append to history buffer and broadcast to all output listeners."""
        self._history_buffer.append(data)
        total_len = sum(len(c) for c in self._history_buffer)
        while total_len > self._max_history_chars and self._history_buffer:
            removed = self._history_buffer.pop(0)
            total_len -= len(removed)

        for cb in list(self._output_listeners):
            try:
                cb(data)
            except Exception as e:
                print(f"Error in output listener: {e}")

    def clear_history(self):
        """Clear local buffer."""
        self._history_buffer.clear()

    def start(self) -> bool:
        """Start the agy process inside a real PTY."""
        if self.state in ("starting", "running") and self.process is not None:
            return True

        self._set_state("starting")
        self.exe_path = find_agy_executable()
        self.version = get_agy_version(self.exe_path)

        if not self.exe_path:
            err = (
                "Antigravity CLI ('agy') is not found on your system.\n\n"
                "Please install agy or ensure it is added to your PATH.\n"
                "Expected location on Windows: %LOCALAPPDATA%\\agy\\bin\\agy.exe"
            )
            self._set_state("error", err)
            self._broadcast_output(f"\r\n\x1b[31;1m[ERROR]\x1b[0m {err}\r\n")
            return False

        self._is_terminating = False

        try:
            import shlex
            if isinstance(self.exe_path, str) and " " in self.exe_path and not os.path.exists(self.exe_path):
                cmd_args = shlex.split(self.exe_path)
            else:
                cmd_args = self.exe_path

            if IS_WINDOWS:
                if not WINPTY_AVAILABLE:
                    raise RuntimeError("pywinpty is required on Windows but not installed.")
                # We specifically use Backend.WinPTY for reliable VT100 interactive streaming
                self.process = winpty.PtyProcess.spawn(
                    cmd_args,
                    cwd=self.cwd,
                    dimensions=(self.rows, self.cols),
                    backend=winpty.enums.Backend.WinPTY
                )
            else:
                if not PTYPROCESS_AVAILABLE:
                    raise RuntimeError("ptyprocess is required on Unix but not installed.")
                args_list = cmd_args if isinstance(cmd_args, list) else [cmd_args]
                self.process = ptyprocess.PtyProcessUnicode.spawn(
                    args_list,
                    cwd=self.cwd,
                    dimensions=(self.rows, self.cols)
                )

            self._set_state("running")

            # Start background reader thread
            self._reader_thread = threading.Thread(target=self._reader_worker, daemon=True)
            self._reader_thread.start()
            return True
        except Exception as e:
            err_msg = f"Failed to start agy PTY session: {e}"
            self._set_state("error", err_msg)
            self._broadcast_output(f"\r\n\x1b[31;1m[ERROR]\x1b[0m {err_msg}\r\n")
            return False

    def _reader_worker(self):
        """Continuously reads output from PTY and dispatches to listeners."""
        while not self._is_terminating and self.process is not None:
            try:
                chunk = self.process.read(2048)
                if chunk:
                    self._broadcast_output(chunk)
                    # Yield slightly so the asyncio event loop and WebSockets breathe smoothly
                    time.sleep(0.002)
                else:
                    time.sleep(0.02)
            except EOFError:
                break
            except Exception as e:
                if not self._is_terminating:
                    print(f"PTY read error: {e}")
                break

        if not self._is_terminating:
            self._set_state("stopped")
            self._broadcast_output("\r\n\x1b[33m[Session terminated]\x1b[0m\r\n")

    def write(self, data: str):
        """Write user input or command directly into PTY."""
        if not self.process or self.state != "running":
            return
        try:
            self.process.write(data)
        except Exception as e:
            print(f"PTY write error: {e}")

    def send_interrupt(self):
        """Send Ctrl+C to interrupt the current command/session."""
        if not self.process or self.state != "running":
            return
        try:
            # Send Ctrl+C character (ASCII 3)
            self.process.write("\x03")
        except Exception as e:
            print(f"Error sending interrupt: {e}")

    def send_prompt(self, prompt_text: str, fallback_cmd: Optional[str] = None):
        """Send prompt to agy using bracketed paste or fallback with chunked writes to prevent pipe lockups."""
        if not self.process or self.state != "running":
            return False

        try:
            # Bracketed paste escape sequences: ESC[200~ ... ESC[201~ followed by newline
            # This indicates to readline/bubbletea TUIs that the text was pasted as a block
            norm_text = prompt_text.replace("\r\n", "\n").replace("\n", "\r\n")
            bracketed_payload = f"\x1b[200~{norm_text}\x1b[201~\r\n"
            
            # Write in small chunks with micro pauses so WinPTY pipe never backs up and locks
            chunk_size = 1024
            for i in range(0, len(bracketed_payload), chunk_size):
                if not self.process or self.state != "running":
                    break
                self.process.write(bracketed_payload[i:i + chunk_size])
                time.sleep(0.002)
            return True
        except Exception as e:
            print(f"Bracketed paste failed: {e}")
            if fallback_cmd:
                try:
                    self.process.write(fallback_cmd.strip() + "\r\n")
                    return True
                except Exception as ex:
                    print(f"Fallback prompt command also failed: {ex}")
            return False

    def resize(self, cols: int, rows: int):
        """Resize PTY window dimensions."""
        self.cols = max(10, cols)
        self.rows = max(5, rows)
        if self.process and self.state == "running":
            try:
                self.process.setwinsize(self.rows, self.cols)
            except Exception as e:
                print(f"PTY resize error: {e}")

    def stop(self):
        """Gracefully stop session or terminate."""
        self._is_terminating = True
        if self.process:
            try:
                self.send_interrupt()
                time.sleep(0.1)
                self.process.close()
            except Exception:
                pass
            self.process = None
        self._set_state("stopped")

    def restart(self) -> bool:
        """Restart session."""
        self.stop()
        time.sleep(0.5)
        return self.start()

    def get_status(self) -> Dict[str, Any]:
        """Return session metadata."""
        return {
            "state": self.state,
            "error": self.error_message,
            "exe_path": self.exe_path,
            "version": self.version,
            "cols": self.cols,
            "rows": self.rows
        }
