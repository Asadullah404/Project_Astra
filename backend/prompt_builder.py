"""Prompt builder for Film Studio.

Generates the exact system instruction prompt for agy to produce AI films using gflow-cli.
"""
import math
import os
from typing import Any, Dict, List, Union


def format_characters(characters: Union[List[Dict[str, str]], str]) -> str:
    """Format character list into a comprehensive string with full visual descriptions."""
    if isinstance(characters, str):
        return characters.strip() or "None specified."
    
    if not characters:
        return "None specified."

    formatted = []
    for idx, c in enumerate(characters, start=1):
        name = c.get("name", "").strip() or f"Character {idx}"
        desc = c.get("description", "").strip()
        formatted.append(f"{name}: {desc}")
    
    return "; ".join(formatted)


def calculate_clips_count(minutes: Union[float, int], seconds_per_clip: Union[float, int] = 8) -> int:
    """Calculate expected clips count, rounding up."""
    total_seconds = float(minutes) * 60.0
    sec = max(1.0, float(seconds_per_clip))
    return max(1, math.ceil(total_seconds / sec))


def build_film_prompt(settings: Dict[str, Any], job_folder_abs: str) -> str:
    """Build the complete film generation prompt following the required template."""
    title = settings.get("title", "Untitled Film").strip()
    story = settings.get("story", "").strip() or "A captivating cinematic story."
    style = settings.get("style", "Cinematic photorealistic, dramatic cinematic lighting").strip()
    aspect = settings.get("aspect", "16:9").strip()
    resolution = settings.get("resolution", "1080p").strip()
    
    try:
        minutes = float(settings.get("duration_minutes", 1.0))
    except (ValueError, TypeError):
        minutes = 1.0

    try:
        sec = float(settings.get("seconds_per_clip", 8))
    except (ValueError, TypeError):
        sec = 8.0

    n_clips = calculate_clips_count(minutes, sec)

    characters_raw = settings.get("characters", [])
    characters_str = format_characters(characters_raw)

    narration_enabled = bool(settings.get("narration", True))
    voice = settings.get("voice", "en-US-ChristopherNeural")
    keep_audio_low = bool(settings.get("keep_clip_audio_low", True))

    if narration_enabled:
        narration_settings = f"Enabled with voice '{voice}' (edge-tts), keep clip audio low: {'yes' if keep_audio_low else 'no'}"
    else:
        narration_settings = "Disabled"

    music_enabled = bool(settings.get("background_music", True))
    music_setting = "Enabled" if music_enabled else "Disabled"

    budget = settings.get("budget", 50)
    approval_mode = bool(settings.get("approval_mode", True))

    if approval_mode:
        approval_mode_line = "Mode: Approval required before spending credits."
        approval_step_text = (
            "COST CHECK, STOP: tell me clips needed, credits per clip, total credits, "
            "my balance, then wait for my 'go'"
        )
        test_approval_text = "wait for my approval."
    else:
        approval_mode_line = "Mode: Automatic generation within budget (do not ask for confirmation)."
        approval_step_text = "Compute the cost; if it exceeds the budget, stop and tell me; otherwise continue"
        test_approval_text = "no waiting."

    norm_folder = os.path.abspath(job_folder_abs).replace("\\", "/")

    prompt = f"""---
PROJECT: Make a short AI film with gflow-cli (Google Flow / Veo), then stitch it into one MP4.
WORK FOLDER (all files go here, use absolute paths): {norm_folder}
TITLE: {title}
STORY: {story}
STYLE: {style} Aspect {aspect}, resolution {resolution}.
DURATION: {minutes} minutes = about {n_clips} clips of {int(sec) if sec.is_integer() else sec} seconds.
CHARACTERS (paste the full text into every scene prompt): {characters_str}
NARRATION: {narration_settings}. MUSIC: {music_setting}.
MAX CREDIT BUDGET: {budget}. {approval_mode_line}

RULES
- gflow is installed and logged in. Never run `gflow auth login`, never touch my password, never try to get around login, captcha or "verify it's you" screens; if one appears, STOP and tell me.
- Never buy credits or upgrade anything. Never exceed the max credit budget.
- Command for running gflow video generation:
  gflow video t2v "<prompt>" --aspect {aspect} -o ./clips/scene_001.mp4
  (Example: gflow video t2v "A calm lake at sunrise, slow cinematic pan" --aspect 16:9)
- Never guess flags: read `gflow --help`, `gflow video --help`, `gflow movie --help`, `gflow character --help` and the gflow-cli docs (AGENTS.md, docs/MOVIE.md, docs/CHARACTER.md at github.com/ffroliva/gflow-cli) first.
- Do not loop. If the same error repeats twice, STOP and show me. Do not resubmit on the same error (each clip costs credits).
- Keep updates short: status, next step, problems.

STEPS
1. Work only inside {norm_folder}. Run `ffmpeg -version` and `gflow credits user`; report the balance.
2. Write the full scene script (number, visual prompt with character text + style, camera move, one narration line). Save ./script/scenes.json and ./script/story.md.
3. {approval_step_text}
4. Create gflow Characters for recurring people, then generate scene 1-3 as a test with `gflow video t2v "<prompt>" --aspect {aspect} -o ./clips/scene_001.mp4` and save as ./clips/scene_001.mp4, scene_002.mp4 ... (exact names, zero-padded, 3 digits). {test_approval_text}
5. Generate the remaining scenes in order. Skip scenes whose file already exists. Log done/failed per scene to ./progress.log. Retry a failed scene once, then flag it and move on. Stop when credits are low or the budget is reached.
6. Narration (edge-tts) into ./audio, then ffmpeg concat + mix to ./final/final_film.mp4 (H.264). Check duration with ffprobe and report it and any missing scenes.
Start with step 1 now.
---"""
    return prompt.strip()


def build_fallback_command(job_folder_abs: str) -> str:
    """Build the short fallback command telling agy to read prompt.md."""
    prompt_file = os.path.abspath(os.path.join(job_folder_abs, "prompt.md")).replace("\\", "/")
    return f'Read "{prompt_file}" and follow it exactly'
