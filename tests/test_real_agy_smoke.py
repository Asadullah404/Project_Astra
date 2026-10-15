"""Smoke test for live agy terminal execution.

Confirms that the real agy session spawns in a real PTY, emits terminal
output, accepts input ("say hello"), and can be cleanly stopped.
NO generation commands or credits are spent.
"""
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.pty_session import PtySession, find_agy_executable


def test_real_agy_terminal_smoke():
    exe = find_agy_executable()
    if not exe or not os.path.exists(exe):
        print(f"Skipping smoke test: agy not found at {exe}")
        return

    # Clear any test override to test real agy
    os.environ.pop("FILM_STUDIO_AGY_CMD", None)

    pty = PtySession()
    output_chunks = []

    def on_output(data: str):
        output_chunks.append(data)

    pty.add_output_listener(on_output)

    try:
        started = pty.start()
        assert started, f"Failed to start live agy session: {pty.error_message}"
        assert pty.state == "running"

        # Wait up to 5s to receive initial TUI output
        start_wait = time.time()
        while time.time() - start_wait < 5.0:
            if output_chunks:
                break
            time.sleep(0.2)

        initial_output = "".join(output_chunks)
        assert len(initial_output) > 0, "No output received from live agy session"

        # Send a harmless prompt / input
        pty.write("say hello\r\n")
        time.sleep(2.0)

        total_output = "".join(output_chunks)
        assert len(total_output) > len(initial_output) or "say hello" in total_output

    finally:
        pty.stop()
        time.sleep(0.5)


if __name__ == "__main__":
    test_real_agy_terminal_smoke()
    print("Real agy terminal smoke test passed successfully!")
