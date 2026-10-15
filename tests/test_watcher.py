"""Unit tests for JobMonitor and stable-size detection."""
import os
import tempfile
import time
from backend.watcher import JobMonitor


def test_clip_stable_size_rule():
    with tempfile.TemporaryDirectory() as tmpdir:
        clips_dir = os.path.join(tmpdir, "clips")
        os.makedirs(clips_dir, exist_ok=True)

        monitor = JobMonitor(job_dir=tmpdir, expected_clips=3)

        # Poll 1: No files created yet -> all missing
        state1 = monitor.evaluate_state()
        assert state1["clips_found"] == 0
        assert all(s["status"] == "missing" for s in state1["scenes"])
        assert state1["state_badge"] == "Waiting for agy"

        # Create scene_001.mp4 but small (< 100KB: e.g. 50 KB)
        scene1 = os.path.join(clips_dir, "scene_001.mp4")
        with open(scene1, "wb") as f:
            f.write(b"X" * (50 * 1024))

        # Poll 2: Small file -> status should be 'writing'
        state2 = monitor.evaluate_state()
        s1 = state2["scenes"][0]
        assert s1["status"] == "writing"
        assert state2["clips_found"] == 0
        assert state2["state_badge"] == "Generating"

        # Poll 3: Still 50 KB (unchanged), but < 100KB -> still 'writing'
        state3 = monitor.evaluate_state()
        assert state3["scenes"][0]["status"] == "writing"
        assert state3["clips_found"] == 0

        # Now enlarge scene_001.mp4 to 120 KB (> 100KB)
        with open(scene1, "wb") as f:
            f.write(b"X" * (120 * 1024))

        # Poll 4: Size changed from 50KB to 120KB -> still 'writing' during this poll
        state4 = monitor.evaluate_state()
        assert state4["scenes"][0]["status"] == "writing"
        assert state4["clips_found"] == 0

        # Poll 5: Size remained 120 KB (unchanged across two polls and > 100KB) -> FOUND!
        state5 = monitor.evaluate_state()
        assert state5["scenes"][0]["status"] == "found"
        assert state5["clips_found"] == 1
        assert state5["scenes"][0]["size_kb"] > 100


def test_final_video_detection_and_done_state():
    with tempfile.TemporaryDirectory() as tmpdir:
        final_dir = os.path.join(tmpdir, "final")
        os.makedirs(final_dir, exist_ok=True)

        monitor = JobMonitor(job_dir=tmpdir, expected_clips=1)

        # Initially final video not found
        s1 = monitor.evaluate_state()
        assert not s1["final_video"]["found"]
        assert s1["state_badge"] == "Waiting for agy"

        # Create final video file (>100KB)
        final_file = os.path.join(final_dir, "final_film.mp4")
        with open(final_file, "wb") as f:
            f.write(b"F" * (200 * 1024))

        # Poll 1 after creation (first seen -> size recorded)
        s2 = monitor.evaluate_state()
        assert not s2["final_video"]["found"]

        # Poll 2 after creation (size stable across two polls) -> Final FOUND & state is DONE!
        s3 = monitor.evaluate_state()
        assert s3["final_video"]["found"]
        assert s3["state_badge"] == "Done"
        assert s3["final_video"]["size_mb"] > 0.1
