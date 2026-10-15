"""Folder watcher and live film monitor for Film Studio.

Watches the active job folder using watchdog plus a 2-second polling fallback.
Enforces the clip stable-size rule (>100KB and size unchanged across two polls).
Extracts duration using ffprobe (if available) with cache.
"""
import asyncio
import os
import shutil
import subprocess
import time
from typing import Any, Callable, Dict, List, Optional, Set

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    Observer = None
    FileSystemEventHandler = object


FFPROBE_BIN = shutil.which("ffprobe")


def format_duration(seconds: float) -> str:
    """Format duration into MM:SS or HH:MM:SS."""
    m, s = divmod(int(round(seconds)), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def get_video_duration(file_path: str) -> Optional[float]:
    """Extract video duration using ffprobe if available."""
    if not FFPROBE_BIN or not os.path.exists(file_path):
        return None
    try:
        cmd = [
            FFPROBE_BIN,
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            file_path
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=3)
        if res.returncode == 0 and res.stdout.strip():
            return float(res.stdout.strip())
    except Exception:
        pass
    return None


class JobFileSystemHandler(FileSystemEventHandler):
    """Watchdog event handler for notifying on filesystem changes."""

    def __init__(self, callback: Callable[[], None]):
        super().__init__()
        self.callback = callback

    def on_any_event(self, event):
        self.callback()


class JobMonitor:
    """Monitors job folder, tracking clips, scripts, audio, final video, and log."""

    def __init__(self, job_dir: Optional[str] = None, expected_clips: int = 10):
        self.job_dir: Optional[str] = os.path.abspath(job_dir) if job_dir else None
        self.expected_clips: int = max(1, expected_clips)
        self.previous_sizes: Dict[str, int] = {}
        self.duration_cache: Dict[str, float] = {}
        self.is_running: bool = False
        self._observer: Optional[Any] = None
        self._poll_task: Optional[asyncio.Task] = None
        self._listeners: Set[Callable[[Dict[str, Any]], None]] = set()
        self.last_state: Dict[str, Any] = {}
        self.start_time: float = time.time()

    def set_job(self, job_dir: str, expected_clips: int = 10, start_time: Optional[float] = None):
        """Switch monitored job directory."""
        self.job_dir = os.path.abspath(job_dir)
        self.expected_clips = max(1, expected_clips)
        self.previous_sizes.clear()
        self.duration_cache.clear()
        self.start_time = start_time or time.time()
        self.restart_observer()

    def add_listener(self, listener: Callable[[Dict[str, Any]], None]):
        """Register a callback for monitor state updates."""
        self._listeners.add(listener)
        if self.last_state:
            listener(self.last_state)

    def remove_listener(self, listener: Callable[[Dict[str, Any]], None]):
        """Remove a registered callback."""
        self._listeners.discard(listener)

    def _notify(self):
        """Evaluate state and broadcast to all listeners."""
        state = self.evaluate_state()
        self.last_state = state
        for listener in list(self._listeners):
            try:
                listener(state)
            except Exception as e:
                print(f"Listener notification error: {e}")

    def evaluate_state(self) -> Dict[str, Any]:
        """Perform stable size analysis and build full monitor report."""
        if not self.job_dir or not os.path.exists(self.job_dir):
            return {
                "active": False,
                "job_dir": self.job_dir,
                "elapsed_seconds": 0,
                "state_badge": "Waiting for agy",
                "clips_found": 0,
                "expected_clips": self.expected_clips,
                "scenes": [],
                "final_video": {"found": False, "duration": None, "size_mb": 0, "path": None},
                "narration_count": 0,
                "script_scenes": False,
                "script_story": False,
                "log_tail": []
            }

        clips_dir = os.path.join(self.job_dir, "clips")
        final_dir = os.path.join(self.job_dir, "final")
        audio_dir = os.path.join(self.job_dir, "audio")
        script_dir = os.path.join(self.job_dir, "script")

        # 1. Evaluate scenes
        scenes: List[Dict[str, Any]] = []
        found_count = 0

        # Scan for existing clips files to determine if extra scenes exist
        existing_clips = set()
        if os.path.exists(clips_dir):
            try:
                existing_clips = {f for f in os.listdir(clips_dir) if f.lower().endswith(".mp4")}
            except Exception:
                pass

        total_scenes_to_track = max(self.expected_clips, len(existing_clips))

        for idx in range(1, total_scenes_to_track + 1):
            name = f"scene_{idx:03d}.mp4"
            fpath = os.path.join(clips_dir, name)
            scene_info = {
                "index": idx,
                "name": name,
                "status": "missing",  # "found" | "writing" | "missing"
                "size_bytes": 0,
                "size_kb": 0,
                "duration": None,
                "duration_formatted": None
            }

            if os.path.exists(fpath):
                try:
                    curr_size = os.path.getsize(fpath)
                    prev_size = self.previous_sizes.get(fpath)
                    self.previous_sizes[fpath] = curr_size
                    scene_info["size_bytes"] = curr_size
                    scene_info["size_kb"] = round(curr_size / 1024, 1)

                    # Stable size rule: > 100 KB and size unchanged across two polls
                    if curr_size > 102400 and prev_size is not None and curr_size == prev_size:
                        scene_info["status"] = "found"
                        found_count += 1
                        # Probe duration
                        if fpath not in self.duration_cache:
                            dur = get_video_duration(fpath)
                            if dur:
                                self.duration_cache[fpath] = dur
                        dur = self.duration_cache.get(fpath)
                        if dur:
                            scene_info["duration"] = dur
                            scene_info["duration_formatted"] = format_duration(dur)
                    else:
                        scene_info["status"] = "writing"
                except Exception:
                    scene_info["status"] = "writing"

            scenes.append(scene_info)

        # 2. Final video check
        final_video_path = os.path.join(final_dir, "final_film.mp4")
        final_found = False
        final_dur = None
        final_dur_str = None
        final_size_mb = 0.0

        if os.path.exists(final_video_path):
            try:
                final_size = os.path.getsize(final_video_path)
                prev_final = self.previous_sizes.get(final_video_path)
                self.previous_sizes[final_video_path] = final_size
                final_size_mb = round(final_size / (1024 * 1024), 2)
                if final_size > 102400 and prev_final is not None and final_size == prev_final:
                    final_found = True
                    if final_video_path not in self.duration_cache:
                        dur = get_video_duration(final_video_path)
                        if dur:
                            self.duration_cache[final_video_path] = dur
                    final_dur = self.duration_cache.get(final_video_path)
                    if final_dur:
                        final_dur_str = format_duration(final_dur)
            except Exception:
                pass

        # 3. Narration audio count
        narration_count = 0
        if os.path.exists(audio_dir):
            try:
                narration_count = len([
                    f for f in os.listdir(audio_dir)
                    if f.lower().endswith((".mp3", ".wav", ".m4a", ".aac"))
                ])
            except Exception:
                pass

        # 4. Script files
        script_scenes = os.path.exists(os.path.join(script_dir, "scenes.json"))
        script_story = os.path.exists(os.path.join(script_dir, "story.md"))

        # 5. Progress log tail (last 20 lines)
        log_path = os.path.join(self.job_dir, "progress.log")
        log_tail: List[str] = []
        if os.path.exists(log_path):
            try:
                with open(log_path, "r", encoding="utf-8", errors="replace") as lf:
                    lines = [ln.strip() for ln in lf.readlines() if ln.strip()]
                    log_tail = lines[-20:]
            except Exception:
                pass

        # 6. Overall state badge
        # Options: Waiting for agy / Generating / Stitching / Done
        if final_found:
            state_badge = "Done"
        elif found_count >= total_scenes_to_track and narration_count > 0:
            state_badge = "Stitching"
        elif found_count > 0 or any(s["status"] == "writing" for s in scenes):
            state_badge = "Generating"
        elif script_scenes or script_story:
            state_badge = "Generating"
        else:
            state_badge = "Waiting for agy"

        elapsed_seconds = int(time.time() - self.start_time)

        return {
            "active": True,
            "job_dir": self.job_dir.replace("\\", "/"),
            "job_name": os.path.basename(self.job_dir),
            "elapsed_seconds": elapsed_seconds,
            "state_badge": state_badge,
            "clips_found": found_count,
            "expected_clips": total_scenes_to_track,
            "scenes": scenes,
            "final_video": {
                "found": final_found,
                "duration": final_dur,
                "duration_formatted": final_dur_str,
                "size_mb": final_size_mb,
                "path": final_video_path.replace("\\", "/") if final_found else None
            },
            "narration_count": narration_count,
            "script_scenes": script_scenes,
            "script_story": script_story,
            "log_tail": log_tail
        }

    def restart_observer(self):
        """Restart watchdog filesystem observer on active folder."""
        if self._observer:
            try:
                self._observer.stop()
                self._observer.join(timeout=1.0)
            except Exception:
                pass
            self._observer = None

        if WATCHDOG_AVAILABLE and self.job_dir and os.path.exists(self.job_dir):
            try:
                self._observer = Observer()
                handler = JobFileSystemHandler(callback=self._notify)
                self._observer.schedule(handler, path=self.job_dir, recursive=True)
                self._observer.start()
            except Exception as e:
                print(f"Watchdog observer start error: {e}")

    async def start(self):
        """Start watcher and 2-second polling fallback loop."""
        if self.is_running:
            return
        self.is_running = True
        self.restart_observer()

        async def polling_loop():
            while self.is_running:
                try:
                    self._notify()
                except Exception as e:
                    print(f"Polling loop notification error: {e}")
                await asyncio.sleep(2.0)

        self._poll_task = asyncio.create_task(polling_loop())

    def stop(self):
        """Stop watcher and polling."""
        self.is_running = False
        if self._poll_task:
            self._poll_task.cancel()
            self._poll_task = None
        if self._observer:
            try:
                self._observer.stop()
                self._observer.join(timeout=1.0)
            except Exception:
                pass
            self._observer = None
