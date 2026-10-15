"""Job Manager for Film Studio.

Manages job directories, job.json configuration, prompt.md generation,
settings persistence, and job history tracking.
"""
import datetime
import json
import os
import random
import string
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional

from backend.prompt_builder import build_film_prompt, calculate_clips_count

DEFAULT_SETTINGS: Dict[str, Any] = {
    "title": "Neon Horizons",
    "story": (
        "In a rain-drenched cyberpunk metropolis, a renegade data courier must deliver "
        "a glowing memory shard to a secret rooftop sanctuary before the corporate enforcers intercept her."
    ),
    "style": "Cinematic sci-fi, blade runner aesthetic, neon teal and amber lighting, anamorphic lens, 8k photorealistic",
    "duration_minutes": 1.0,
    "seconds_per_clip": 8.0,
    "aspect": "16:9",
    "resolution": "1080p",
    "characters": [
        {
            "name": "Kira",
            "description": "Young woman with cybernetic teal eyes, sleek black leather jacket with illuminated collar, silver braided hair."
        }
    ],
    "narration": True,
    "voice": "en-US-ChristopherNeural",
    "background_music": True,
    "keep_clip_audio_low": True,
    "budget": 50,
    "approval_mode": True,
    "output_root": "./jobs"
}


class JobManager:
    """Handles job creation, tracking, settings persistence, and history."""

    def __init__(self, workspace_root: str = ".", settings_file: str = "settings.json"):
        self.workspace_root = os.path.abspath(workspace_root)
        self.settings_file = os.path.join(self.workspace_root, settings_file)
        self.current_job: Optional[Dict[str, Any]] = None

    def load_settings(self) -> Dict[str, Any]:
        """Load settings from settings.json or return defaults."""
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    merged = DEFAULT_SETTINGS.copy()
                    merged.update(data)
                    return merged
            except Exception:
                pass
        return DEFAULT_SETTINGS.copy()

    def save_settings(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        """Save settings to settings.json."""
        current = self.load_settings()
        current.update(settings)
        try:
            with open(self.settings_file, "w", encoding="utf-8") as f:
                json.dump(current, f, indent=2)
        except Exception as e:
            print(f"Error saving settings: {e}")
        return current

    def generate_job_id(self) -> str:
        """Generate unique job id: job_<YYYYMMDD_HHMMSS>_<4 random chars>."""
        now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        rand = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
        return f"job_{now}_{rand}"

    def create_job(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new job directory and subfolders, saving job.json and prompt.md."""
        output_root = settings.get("output_root", "./jobs")
        if not os.path.isabs(output_root):
            output_root = os.path.join(self.workspace_root, output_root)
        output_root = os.path.abspath(output_root)
        os.makedirs(output_root, exist_ok=True)

        job_id = self.generate_job_id()
        job_dir = os.path.join(output_root, job_id)
        os.makedirs(job_dir, exist_ok=True)

        # Create subfolders: script, clips, audio, final
        for sub in ("script", "clips", "audio", "final"):
            os.makedirs(os.path.join(job_dir, sub), exist_ok=True)

        # Calculate clip counts
        duration = float(settings.get("duration_minutes", 1.0))
        sec_per_clip = float(settings.get("seconds_per_clip", 8.0))
        expected_clips = calculate_clips_count(duration, sec_per_clip)

        # Build prompt
        prompt_content = build_film_prompt(settings, job_dir)
        prompt_path = os.path.join(job_dir, "prompt.md")
        with open(prompt_path, "w", encoding="utf-8") as f:
            f.write(prompt_content)

        job_info: Dict[str, Any] = {
            "id": job_id,
            "title": settings.get("title", "Untitled Film"),
            "path": job_dir.replace("\\", "/"),
            "created_at": datetime.datetime.now().isoformat(),
            "expected_clips": expected_clips,
            "duration_minutes": duration,
            "seconds_per_clip": sec_per_clip,
            "settings": settings,
            "status": "running"
        }

        job_json_path = os.path.join(job_dir, "job.json")
        with open(job_json_path, "w", encoding="utf-8") as f:
            json.dump(job_info, f, indent=2)

        self.current_job = job_info
        return job_info

    def list_jobs(self, output_root: Optional[str] = None) -> List[Dict[str, Any]]:
        """List previous jobs in the output root folder, sorted by creation date descending."""
        if not output_root:
            settings = self.load_settings()
            output_root = settings.get("output_root", "./jobs")

        if not os.path.isabs(output_root):
            output_root = os.path.join(self.workspace_root, output_root)
        output_root = os.path.abspath(output_root)

        if not os.path.exists(output_root):
            return []

        jobs: List[Dict[str, Any]] = []
        for name in os.listdir(output_root):
            full_path = os.path.join(output_root, name)
            if os.path.isdir(full_path) and name.startswith("job_"):
                job_json_path = os.path.join(full_path, "job.json")
                if os.path.exists(job_json_path):
                    try:
                        with open(job_json_path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            # Update path if moved
                            data["path"] = full_path.replace("\\", "/")
                            jobs.append(data)
                            continue
                    except Exception:
                        pass
                # Fallback for folder without valid job.json
                stat = os.stat(full_path)
                jobs.append({
                    "id": name,
                    "title": name,
                    "path": full_path.replace("\\", "/"),
                    "created_at": datetime.datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    "expected_clips": 10,
                    "settings": {},
                    "status": "unknown"
                })

        jobs.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return jobs

    def is_job_active(self, job_dir: str) -> bool:
        """Check whether a job is actively running (clips or progress modified in last 45s)."""
        if not os.path.exists(job_dir):
            return False

        # If final video exists, job is complete
        final_video = os.path.join(job_dir, "final", "final_film.mp4")
        if os.path.exists(final_video) and os.path.getsize(final_video) > 102400:
            return False

        now = time.time()
        clips_dir = os.path.join(job_dir, "clips")
        if os.path.exists(clips_dir):
            for fname in os.listdir(clips_dir):
                fpath = os.path.join(clips_dir, fname)
                if os.path.isfile(fpath):
                    mtime = os.path.getmtime(fpath)
                    if (now - mtime) < 45.0:
                        return True

        progress_log = os.path.join(job_dir, "progress.log")
        if os.path.exists(progress_log):
            mtime = os.path.getmtime(progress_log)
            if (now - mtime) < 45.0:
                return True

        return False

    @staticmethod
    def open_folder_in_os(path: str) -> bool:
        """Open the given directory path in OS file explorer."""
        abs_path = os.path.abspath(path)
        if not os.path.exists(abs_path):
            return False

        try:
            if sys.platform == "win32":
                os.startfile(abs_path)
            elif sys.platform == "darwin":
                subprocess.run(["open", abs_path], check=False)
            else:
                subprocess.run(["xdg-open", abs_path], check=False)
            return True
        except Exception as e:
            print(f"Error opening folder {path}: {e}")
            return False
