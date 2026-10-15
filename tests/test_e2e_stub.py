"""End-to-End Integration Test using Fake agy Stub.

Validates:
1. PTY lifecycle (spawning fake_agy, bidirectional output).
2. Unique job folder & subfolder structure.
3. Prompt injection into PTY.
4. Watcher detecting progressive clip creation (>100KB stable rule).
5. Final video detection and transition to 'Done' state.
6. Progress log tail and job history persistence.
"""
import asyncio
import os
import sys
import tempfile
import time

from backend.job_manager import JobManager
from backend.pty_session import PtySession
from backend.watcher import JobMonitor


async def _run_e2e_flow():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_workspace:
        jobs_dir = os.path.join(tmp_workspace, "jobs")
        os.makedirs(jobs_dir, exist_ok=True)

        fake_agy_script = os.path.abspath(os.path.join(os.path.dirname(__file__), "fake_agy.py"))
        os.environ["FILM_STUDIO_AGY_CMD"] = f'"{sys.executable}" "{fake_agy_script}"'

        # 1. Start PTY Session
        pty = PtySession(cwd=tmp_workspace)
        monitor = None
        terminal_chunks = []

        def on_output(chunk: str):
            terminal_chunks.append(chunk)

        try:
            pty.add_output_listener(on_output)
            started = pty.start()
            assert started, f"PTY failed to start: {pty.error_message}"
            assert pty.state == "running"

            # Wait up to 3s for fake_agy startup banner
            for _ in range(30):
                if any("Fake agy" in c for c in terminal_chunks):
                    break
                time.sleep(0.1)

            full_output = "".join(terminal_chunks)
            assert "Fake agy" in full_output, f"Banner not found in: {full_output}"

            # 2. Create Job
            jm = JobManager(workspace_root=tmp_workspace)
            settings = {
                "title": "Neon Horizons E2E",
                "story": "A rebel courier runs across neon roofs.",
                "style": "Cyberpunk 4K",
                "duration_minutes": 0.25,
                "seconds_per_clip": 8.0,
                "output_root": jobs_dir,
                "approval_mode": False
            }
            job_info = jm.create_job(settings)
            job_dir = job_info["path"]
            assert os.path.exists(job_dir)
            assert os.path.exists(os.path.join(job_dir, "prompt.md"))

            # 3. Setup Watcher
            monitor = JobMonitor(job_dir=job_dir, expected_clips=2)
            await monitor.start()

            # Initial check
            init_state = monitor.evaluate_state()
            assert init_state["state_badge"] == "Waiting for agy"
            assert init_state["clips_found"] == 0

            # 4. Inject Prompt into PTY
            with open(os.path.join(job_dir, "prompt.md"), "r", encoding="utf-8") as f:
                prompt_content = f.read()

            fallback = f'Read "{job_dir}/prompt.md" and follow it exactly'
            injected = pty.send_prompt(prompt_content, fallback_cmd=fallback)
            assert injected

            # 5. Wait for fake_agy to generate assets and watcher to reach 'Done'
            max_wait = 15.0
            start_t = time.time()
            final_state = None

            while time.time() - start_t < max_wait:
                state = monitor.evaluate_state()
                if state.get("final_video", {}).get("found") and state.get("state_badge") == "Done":
                    final_state = state
                    break
                time.sleep(0.4)

            assert final_state is not None, f"Pipeline did not reach 'Done' within timeout. Last state: {state}"
            assert final_state["clips_found"] >= 2
            assert final_state["final_video"]["found"] is True
            assert final_state["final_video"]["size_mb"] > 0.2
            assert final_state["state_badge"] == "Done"
            assert final_state["script_scenes"] is True
            assert final_state["script_story"] is True
            assert final_state["narration_count"] >= 1
            assert len(final_state["log_tail"]) > 0

            # 6. Verify Job History
            history = jm.list_jobs(output_root=jobs_dir)
            assert len(history) == 1
            assert history[0]["id"] == job_info["id"]

        finally:
            if monitor:
                monitor.stop()
            pty.stop()
            time.sleep(0.5)


def test_full_pipeline_with_fake_agy():
    asyncio.run(_run_e2e_flow())
