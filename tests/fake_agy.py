"""Fake agy stub script for automated testing.

Simulates agy interactive CLI session:
1. Responds to --version and --help flags.
2. Runs interactive TUI prompt in terminal/PTY.
3. Detects prompt input containing WORK FOLDER or Read prompt.md.
4. Generates dummy script, clips, narration, and final video after realistic delays.
5. Emits live progress lines to stdout and progress.log.
"""
import os
import re
import sys
import threading
import time


def create_dummy_file(path: str, size_bytes: int):
    """Create a dummy file with specified byte size."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(b"\x00" * size_bytes)


def simulate_generation(work_folder: str):
    """Simulate realistic AI video generation steps in the background."""
    time.sleep(0.3)
    log_path = os.path.join(work_folder, "progress.log")

    def append_log(msg: str):
        print(f"[Fake agy] {msg}", flush=True)
        try:
            with open(log_path, "a", encoding="utf-8") as lf:
                lf.write(f"[{time.strftime('%X')}] {msg}\n")
        except Exception:
            pass

    append_log("Starting generation pipeline...")

    # Step 1: Script files
    time.sleep(0.3)
    os.makedirs(os.path.join(work_folder, "script"), exist_ok=True)
    with open(os.path.join(work_folder, "script", "scenes.json"), "w", encoding="utf-8") as f:
        f.write('{"scenes": [{"id": 1}, {"id": 2}]}')
    with open(os.path.join(work_folder, "script", "story.md"), "w", encoding="utf-8") as f:
        f.write("# Story\nTest story script.")
    append_log("Saved ./script/scenes.json and ./script/story.md")

    # Step 2: Scene 1 (gradual write to test 'writing' state)
    time.sleep(0.3)
    scene1_path = os.path.join(work_folder, "clips", "scene_001.mp4")
    # First write partial file (50KB -> shows writing)
    create_dummy_file(scene1_path, 50 * 1024)
    append_log("Writing scene_001.mp4 (in-progress)...")

    time.sleep(0.8)
    # Complete file (>100KB -> 150KB, stable)
    create_dummy_file(scene1_path, 150 * 1024)
    append_log("Completed ./clips/scene_001.mp4 (150 KB)")

    # Step 3: Scene 2
    time.sleep(0.8)
    scene2_path = os.path.join(work_folder, "clips", "scene_002.mp4")
    create_dummy_file(scene2_path, 180 * 1024)
    append_log("Completed ./clips/scene_002.mp4 (180 KB)")

    # Step 4: Narration audio
    time.sleep(0.6)
    audio_path = os.path.join(work_folder, "audio", "voiceover.mp3")
    create_dummy_file(audio_path, 80 * 1024)
    append_log("Generated ./audio/voiceover.mp3")

    # Step 5: Final video
    time.sleep(0.8)
    final_path = os.path.join(work_folder, "final", "final_film.mp4")
    create_dummy_file(final_path, 320 * 1024)
    append_log("Stitched ./final/final_film.mp4 (320 KB) - Complete!")


def main():
    if "--version" in sys.argv:
        print("1.3.6-stub")
        return

    if "--help" in sys.argv:
        print("Usage: fake_agy [--version] [--help]")
        return

    # Interactive PTY loop
    print("[Fake agy CLI v1.3.6-stub] Ready. Type commands or paste prompt:", flush=True)

    work_folder_regex = re.compile(r"WORK FOLDER[^\n:]*:\s*([^\r\n\[]+?)(?:\s*TITLE:|\r|\n|$)", re.IGNORECASE)
    read_fallback_regex = re.compile(r'Read\s+["\']?([^"\']+)["\']?\s+and follow it exactly', re.IGNORECASE)

    sim_thread = None
    input_buffer = ""

    while True:
        try:
            char = sys.stdin.read(1)
            if not char:
                break

            input_buffer += char

            if char in ("\n", "\r"):
                line = input_buffer.strip()
                input_buffer = ""
                if not line:
                    continue

                clean_line = re.sub(r"\x1b\[\d+~|\[\d+~", "", line).strip()
                print(f"> ECHO: {clean_line}", flush=True)

                match = work_folder_regex.search(clean_line)
                fallback_match = read_fallback_regex.search(clean_line)

                target_folder = None
                if match:
                    target_folder = match.group(1).strip()
                elif fallback_match:
                    prompt_file = fallback_match.group(1).strip()
                    target_folder = os.path.dirname(prompt_file)

                if target_folder and (sim_thread is None or not sim_thread.is_alive()):
                    norm_folder = os.path.abspath(target_folder)
                    print(f"[Fake agy] Acknowledged work folder: {norm_folder}", flush=True)
                    sim_thread = threading.Thread(target=simulate_generation, args=(norm_folder,), daemon=True)
                    sim_thread.start()

        except KeyboardInterrupt:
            print("\n[Fake agy] Interrupted (Ctrl+C).", flush=True)
            break
        except Exception as e:
            print(f"[Fake agy error] {e}", flush=True)
            break


if __name__ == "__main__":
    main()
