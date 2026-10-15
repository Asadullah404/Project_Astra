"""Read-only helpers for gflow CLI inspection.

Strictly executes read-only diagnostic commands (auth status, credits user)
with strict timeouts. Never runs login or generation commands.
"""
import asyncio
import json
import os
import shutil
import subprocess
from typing import Any, Dict


def find_gflow_executable() -> str:
    """Locate gflow executable."""
    found = shutil.which("gflow")
    if found:
        return found
    # Common Windows user location
    local_path = os.path.expanduser("~/.local/bin/gflow.exe")
    if os.path.exists(local_path):
        return local_path
    return "gflow"


async def check_gflow_status(timeout_seconds: int = 30) -> Dict[str, Any]:
    """Execute read-only 'gflow auth status' and 'gflow credits user --json'."""
    exe = find_gflow_executable()

    auth_result: Dict[str, Any] = {
        "status": "unknown",
        "output": "",
        "exit_code": -1
    }
    credits_result: Dict[str, Any] = {
        "status": "unknown",
        "output": "",
        "data": None
    }

    # 1. Run gflow auth status
    try:
        proc = await asyncio.create_subprocess_exec(
            exe, "auth", "status",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout_seconds)
        output_text = stdout.decode("utf-8", errors="replace").strip()
        auth_result["output"] = output_text
        auth_result["exit_code"] = proc.returncode

        if proc.returncode == 0:
            auth_result["status"] = "ok"
        else:
            auth_result["status"] = "unauthenticated" if "not signed in" in output_text.lower() or "login" in output_text.lower() else "error"
    except asyncio.TimeoutError:
        auth_result["status"] = "timeout"
        auth_result["output"] = f"gflow auth status timed out after {timeout_seconds}s"
    except FileNotFoundError:
        auth_result["status"] = "not_found"
        auth_result["output"] = "gflow CLI executable not found in PATH or ~/.local/bin"
    except Exception as e:
        auth_result["status"] = "error"
        auth_result["output"] = str(e)

    # 2. Run gflow credits user --json
    try:
        proc = await asyncio.create_subprocess_exec(
            exe, "credits", "user", "--json",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout_seconds)
        raw_output = stdout.decode("utf-8", errors="replace").strip()
        credits_result["output"] = raw_output

        # Extract last JSON payload if multiple lines contain log entries
        json_obj = None
        for line in reversed(raw_output.splitlines()):
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                try:
                    json_obj = json.loads(line)
                    break
                except Exception:
                    continue

        if json_obj is None and "{" in raw_output:
            # Try parsing entire output or chunk
            start = raw_output.find("{")
            end = raw_output.rfind("}")
            if start != -1 and end != -1:
                try:
                    json_obj = json.loads(raw_output[start:end+1])
                except Exception:
                    pass

        if json_obj:
            credits_result["data"] = json_obj
            if json_obj.get("status") == "fail":
                credits_result["status"] = "fail"
                credits_result["message"] = json_obj.get("error", {}).get("remediation_hint", "Could not fetch credits")
            else:
                credits_result["status"] = "ok"
        else:
            credits_result["status"] = "ok" if proc.returncode == 0 else "error"
    except asyncio.TimeoutError:
        credits_result["status"] = "timeout"
        credits_result["output"] = f"gflow credits user timed out after {timeout_seconds}s"
    except FileNotFoundError:
        credits_result["status"] = "not_found"
        credits_result["output"] = "gflow CLI executable not found"
    except Exception as e:
        credits_result["status"] = "error"
        credits_result["output"] = str(e)

    return {
        "auth": auth_result,
        "credits": credits_result
    }
