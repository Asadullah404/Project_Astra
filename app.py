"""Film Studio - Main Application Server & Desktop Launcher.

Hosts FastAPI + Uvicorn backend bound to 127.0.0.1 with random token authentication,
pywinpty interactive terminal session, watchdog live monitor, and launches
pywebview native window (with browser fallback).
"""
import asyncio
import os
import secrets
import sys
import threading
import time
import webbrowser
from typing import Any, Dict, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend.gflow_tools import check_gflow_status
from backend.job_manager import JobManager
from backend.prompt_builder import build_fallback_command, build_film_prompt
from backend.pty_session import PtySession
from backend.watcher import JobMonitor

# Generate random startup token required for WebSockets and authenticated endpoints
STARTUP_TOKEN = secrets.token_urlsafe(32)

app = FastAPI(title="Film Studio")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

WORKSPACE_ROOT = os.path.abspath(os.path.dirname(__file__))
STATIC_DIR = os.path.join(WORKSPACE_ROOT, "static")

job_manager = JobManager(workspace_root=WORKSPACE_ROOT)
pty_session = PtySession(cwd=WORKSPACE_ROOT)
job_monitor = JobMonitor()

# Connected WebSocket sets
terminal_websockets: set[WebSocket] = set()
monitor_websockets: set[WebSocket] = set()

# Main asyncio loop reference for thread-safe websocket broadcasts
main_loop: Optional[asyncio.AbstractEventLoop] = None


class StartJobRequest(BaseModel):
    settings: Dict[str, Any]
    force: bool = False


class JobActionRequest(BaseModel):
    job_id: Optional[str] = None
    path: Optional[str] = None


class TerminalActionRequest(BaseModel):
    action: str  # "start", "stop", "restart", "clear"


def broadcast_terminal_output(chunk: str):
    """Thread-safe callback from PTY reader to terminal WebSockets."""
    if not main_loop or not terminal_websockets:
        return

    msg = {"type": "output", "data": chunk}
    for ws in list(terminal_websockets):
        try:
            asyncio.run_coroutine_threadsafe(ws.send_json(msg), main_loop)
        except Exception:
            pass


def broadcast_terminal_state(state: str):
    """Thread-safe callback from PTY state transitions."""
    if not main_loop or not terminal_websockets:
        return

    msg = {"type": "status", "data": pty_session.get_status()}
    for ws in list(terminal_websockets):
        try:
            asyncio.run_coroutine_threadsafe(ws.send_json(msg), main_loop)
        except Exception:
            pass


def broadcast_monitor_state(state: Dict[str, Any]):
    """Thread-safe callback from JobMonitor to monitor WebSockets."""
    if not main_loop or not monitor_websockets:
        return

    msg = {"type": "monitor", "data": state}
    for ws in list(monitor_websockets):
        try:
            asyncio.run_coroutine_threadsafe(ws.send_json(msg), main_loop)
        except Exception:
            pass


@app.on_event("startup")
async def startup_event():
    """Application startup initialization."""
    global main_loop
    main_loop = asyncio.get_running_loop()

    # Wire up listeners
    pty_session.add_output_listener(broadcast_terminal_output, replay_history=False)
    pty_session.add_state_listener(broadcast_terminal_state)
    job_monitor.add_listener(broadcast_monitor_state)

    # Start live monitor loop
    await job_monitor.start()

    # Terminal starts AUTOMATICALLY when the app opens, before any job is run
    threading.Thread(target=pty_session.start, daemon=True).start()


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup resources on shutdown."""
    job_monitor.stop()
    pty_session.stop()


# ---------------- API ROUTES ----------------

@app.get("/api/token")
async def get_startup_token():
    """Endpoint for web UI to retrieve current valid startup token."""
    return {"token": STARTUP_TOKEN}


@app.get("/api/settings")
async def get_settings():
    """Retrieve saved settings."""
    return job_manager.load_settings()


@app.post("/api/settings")
async def save_settings(settings: Dict[str, Any]):
    """Save user settings."""
    saved = job_manager.save_settings(settings)
    return {"status": "ok", "settings": saved}


@app.post("/api/gflow/check")
async def check_gflow():
    """Perform read-only diagnostic check of gflow auth and credits."""
    result = await check_gflow_status(timeout_seconds=25)
    return result


@app.get("/api/jobs")
async def list_jobs(root: Optional[str] = None):
    """Retrieve list of previous jobs."""
    jobs = job_manager.list_jobs(output_root=root)
    return {"jobs": jobs}


@app.post("/api/job/start")
async def start_job(req: StartJobRequest):
    """Start a new film generation job."""
    # Check if a job is actively running
    if job_manager.current_job and not req.force:
        curr_dir = job_manager.current_job.get("path")
        if curr_dir and job_manager.is_job_active(curr_dir):
            return JSONResponse(
                status_code=409,
                content={
                    "warning": "job_already_running",
                    "message": "A film generation job appears to still be actively running. Do you want to proceed anyway?"
                }
            )

    # Save latest settings
    job_manager.save_settings(req.settings)

    # Create unique folder and files
    job_info = job_manager.create_job(req.settings)
    job_folder = job_info["path"]

    # Point live monitor to new job
    job_monitor.set_job(
        job_dir=job_folder,
        expected_clips=job_info["expected_clips"],
        start_time=time.time()
    )

    # Ensure agy terminal is running
    if pty_session.state != "running":
        pty_session.start()
        # Non-blocking pause to allow shell readiness without freezing WebSockets
        await asyncio.sleep(0.5)

    # Read generated prompt
    prompt_file = os.path.join(job_folder, "prompt.md")
    with open(prompt_file, "r", encoding="utf-8") as pf:
        full_prompt = pf.read()

    fallback_cmd = build_fallback_command(job_folder)

    # Inject prompt into live agy session in background thread so event loop never stalls
    injected = await asyncio.to_thread(pty_session.send_prompt, full_prompt, fallback_cmd)

    return {
        "status": "ok",
        "job": job_info,
        "prompt_injected": injected
    }


@app.post("/api/job/select")
async def select_job(req: JobActionRequest):
    """Switch active monitor to an existing job."""
    if not req.path or not os.path.exists(req.path):
        raise HTTPException(status_code=404, detail="Job path not found")

    expected = 10
    job_json = os.path.join(req.path, "job.json")
    if os.path.exists(job_json):
        try:
            import json
            with open(job_json, "r", encoding="utf-8") as f:
                data = json.load(f)
                expected = data.get("expected_clips", 10)
        except Exception:
            pass

    job_monitor.set_job(req.path, expected_clips=expected)
    return {"status": "ok", "path": req.path}


@app.post("/api/job/resend")
async def resend_job_prompt(req: JobActionRequest):
    """Re-send prompt for an existing job to the agy terminal."""
    if not req.path or not os.path.exists(req.path):
        raise HTTPException(status_code=404, detail="Job path not found")

    prompt_file = os.path.join(req.path, "prompt.md")
    if not os.path.exists(prompt_file):
        raise HTTPException(status_code=404, detail="prompt.md not found in job directory")

    with open(prompt_file, "r", encoding="utf-8") as f:
        full_prompt = f.read()

    fallback_cmd = build_fallback_command(req.path)
    injected = await asyncio.to_thread(pty_session.send_prompt, full_prompt, fallback_cmd)
    return {"status": "ok", "prompt_injected": injected}


@app.post("/api/job/open-folder")
async def open_folder(req: JobActionRequest):
    """Open job folder in OS file explorer."""
    target_path = req.path or (job_monitor.job_dir if job_monitor else None)
    if not target_path or not os.path.exists(target_path):
        raise HTTPException(status_code=404, detail="Path does not exist")

    success = JobManager.open_folder_in_os(target_path)
    return {"status": "ok" if success else "failed"}


@app.post("/api/terminal/action")
async def terminal_action(req: TerminalActionRequest):
    """Execute terminal control action: start, stop, restart, clear."""
    action = req.action.lower()
    if action == "start":
        pty_session.start()
    elif action == "stop":
        pty_session.send_interrupt()
    elif action == "restart":
        pty_session.restart()
    elif action == "clear":
        pty_session.clear_history()
        # Broadcast clear code to frontend xterm
        broadcast_terminal_output("\x1b[2J\x1b[H")
    else:
        raise HTTPException(status_code=400, detail="Unknown action")

    return {"status": "ok", "terminal_status": pty_session.get_status()}


@app.get("/api/terminal/status")
async def terminal_status():
    """Retrieve terminal session status."""
    return pty_session.get_status()


@app.get("/api/media/{job_id}/{subpath:path}")
async def serve_media(job_id: str, subpath: str):
    """Safely stream video clips or final video files with proper range support."""
    # Find job folder from settings or default jobs directory
    settings = job_manager.load_settings()
    output_root = settings.get("output_root", "./jobs")
    if not os.path.isabs(output_root):
        output_root = os.path.join(WORKSPACE_ROOT, output_root)

    safe_base = os.path.abspath(output_root)
    requested_file = os.path.abspath(os.path.join(safe_base, job_id, subpath))

    # Path traversal protection
    if not requested_file.startswith(safe_base):
        raise HTTPException(status_code=403, detail="Forbidden")

    if not os.path.exists(requested_file) or not os.path.isfile(requested_file):
        raise HTTPException(status_code=404, detail="Media file not found")

    ext = os.path.splitext(requested_file)[1].lower()
    mime = "video/mp4" if ext == ".mp4" else ("audio/mpeg" if ext == ".mp3" else "application/octet-stream")

    return FileResponse(requested_file, media_type=mime, filename=os.path.basename(requested_file))


# ---------------- WEBSOCKETS ----------------

@app.websocket("/ws/terminal")
async def websocket_terminal(websocket: WebSocket, token: Optional[str] = Query(None)):
    """Interactive bidirectional terminal WebSocket for xterm.js."""
    if token != STARTUP_TOKEN:
        await websocket.close(code=4003, reason="Unauthorized token")
        return

    await websocket.accept()
    terminal_websockets.add(websocket)

    # Send current terminal status
    await websocket.send_json({"type": "status", "data": pty_session.get_status()})

    # Replay buffer history to new subscriber
    if pty_session._history_buffer:
        history = "".join(pty_session._history_buffer)
        await websocket.send_json({"type": "output", "data": history})

    try:
        while True:
            msg = await websocket.receive_json()
            msg_type = msg.get("type")
            if msg_type == "input":
                # Keystroke or input from xterm.js -> forward directly to PTY
                data = msg.get("data", "")
                pty_session.write(data)
            elif msg_type == "resize":
                # Window resize from fit addon
                cols = msg.get("cols", 80)
                rows = msg.get("rows", 24)
                pty_session.resize(cols, rows)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"Terminal websocket error: {e}")
    finally:
        terminal_websockets.discard(websocket)


@app.websocket("/ws/monitor")
async def websocket_monitor(websocket: WebSocket, token: Optional[str] = Query(None)):
    """Real-time live monitor WebSocket broadcasting clip and film progress."""
    if token != STARTUP_TOKEN:
        await websocket.close(code=4003, reason="Unauthorized token")
        return

    await websocket.accept()
    monitor_websockets.add(websocket)

    # Immediately send latest state
    if job_monitor.last_state:
        await websocket.send_json({"type": "monitor", "data": job_monitor.last_state})
    else:
        state = job_monitor.evaluate_state()
        await websocket.send_json({"type": "monitor", "data": state})

    try:
        while True:
            # Keepalive ping
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"Monitor websocket error: {e}")
    finally:
        monitor_websockets.discard(websocket)


# Mount static files
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def root_index():
    """Serve index.html."""
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return HTMLResponse("<h1>Film Studio - UI Loading...</h1>")


def run_server(port: int):
    """Run uvicorn server bound strictly to 127.0.0.1."""
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


def main():
    """Main desktop application entrypoint."""
    port = 8765
    server_url = f"http://127.0.0.1:{port}/?token={STARTUP_TOKEN}"

    # Start FastAPI server in background thread
    server_thread = threading.Thread(target=run_server, args=(port,), daemon=True)
    server_thread.start()

    # Wait for server to bind
    time.sleep(1.0)
    print(f"Film Studio server online at http://127.0.0.1:{port}")

    # Launch native window with pywebview, fallback to default browser
    use_browser = "--browser" in sys.argv or os.environ.get("FILM_STUDIO_BROWSER") == "1"

    if not use_browser:
        try:
            import webview
            print("Launching native window with pywebview...")
            window = webview.create_window(
                title="Film Studio - AI Video Director",
                url=server_url,
                width=1440,
                height=920,
                min_size=(1024, 680),
                background_color="#0e1113"
            )
            webview.start()
            return
        except Exception as e:
            print(f"pywebview failed ({e}). Falling back to default system browser.")

    # Fallback to browser
    print(f"Opening browser at {server_url}")
    webbrowser.open(server_url)

    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down Film Studio.")


if __name__ == "__main__":
    main()
