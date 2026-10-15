"""Unit tests for JobManager."""
import json
import os
import re
import tempfile
import time
from backend.job_manager import JobManager


def test_job_id_format():
    jm = JobManager()
    job_id = jm.generate_job_id()
    # Format: job_<YYYYMMDD_HHMMSS>_<4 chars>
    pattern = r"^job_\d{8}_\d{6}_[a-z0-9]{4}$"
    assert re.match(pattern, job_id), f"Job ID {job_id} does not match pattern {pattern}"


def test_create_job_and_structure():
    with tempfile.TemporaryDirectory() as tmpdir:
        jm = JobManager(workspace_root=tmpdir)
        settings = {
            "title": "Test Odyssey",
            "story": "Space explorer testing job manager.",
            "duration_minutes": 1.0,
            "seconds_per_clip": 8.0,
            "output_root": os.path.join(tmpdir, "my_jobs")
        }

        job = jm.create_job(settings)
        job_dir = job["path"]

        # Check main folder exists
        assert os.path.exists(job_dir)

        # Check required subfolders: script, clips, audio, final
        for sub in ("script", "clips", "audio", "final"):
            subpath = os.path.join(job_dir, sub)
            assert os.path.exists(subpath), f"Subfolder {sub} missing"

        # Check job.json
        job_json_file = os.path.join(job_dir, "job.json")
        assert os.path.exists(job_json_file)
        with open(job_json_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            assert data["id"] == job["id"]
            assert data["expected_clips"] == 8
            assert data["title"] == "Test Odyssey"

        # Check prompt.md
        prompt_file = os.path.join(job_dir, "prompt.md")
        assert os.path.exists(prompt_file)
        with open(prompt_file, "r", encoding="utf-8") as pf:
            content = pf.read()
            assert "TITLE: Test Odyssey" in content
            assert "WORK FOLDER" in content


def test_settings_persistence():
    with tempfile.TemporaryDirectory() as tmpdir:
        jm = JobManager(workspace_root=tmpdir, settings_file="custom_settings.json")
        default_s = jm.load_settings()
        assert default_s["title"] == "Neon Horizons"

        # Save update
        jm.save_settings({"title": "Cyber City 2099", "budget": 100})
        reloaded = jm.load_settings()
        assert reloaded["title"] == "Cyber City 2099"
        assert reloaded["budget"] == 100
        # Preserved other fields
        assert reloaded["seconds_per_clip"] == 8.0


def test_is_job_active():
    with tempfile.TemporaryDirectory() as tmpdir:
        jm = JobManager(workspace_root=tmpdir)
        job_dir = os.path.join(tmpdir, "job_test_active")
        os.makedirs(os.path.join(job_dir, "clips"), exist_ok=True)
        os.makedirs(os.path.join(job_dir, "final"), exist_ok=True)

        # Initially inactive
        assert not jm.is_job_active(job_dir)

        # Create recent clip
        clip_path = os.path.join(job_dir, "clips", "scene_001.mp4")
        with open(clip_path, "wb") as f:
            f.write(b"0" * 1000)

        # Now active
        assert jm.is_job_active(job_dir)

        # Once final video (>100KB) exists, job is considered complete (not actively running)
        final_video = os.path.join(job_dir, "final", "final_film.mp4")
        with open(final_video, "wb") as f:
            f.write(b"0" * 150000)

        assert not jm.is_job_active(job_dir)
