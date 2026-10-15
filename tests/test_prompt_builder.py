"""Unit tests for prompt builder."""
import os
import pytest
from backend.prompt_builder import (
    build_fallback_command,
    build_film_prompt,
    calculate_clips_count,
    format_characters,
)


def test_calculate_clips_count():
    # 1.0 minute = 60s / 8s = 7.5 -> 8 clips
    assert calculate_clips_count(1.0, 8.0) == 8
    # 0.5 minute = 30s / 8s = 3.75 -> 4 clips
    assert calculate_clips_count(0.5, 8.0) == 4
    # Exact division: 2 minutes = 120s / 10s = 12 clips
    assert calculate_clips_count(2.0, 10.0) == 12
    # Edge case: zero or negative clamped to at least 1
    assert calculate_clips_count(0.1, 8.0) >= 1


def test_format_characters():
    chars = [
        {"name": "Kira", "description": "Cyberpunk runner with teal optics."},
        {"name": "Vance", "description": "Enforcer in matte black exo-suit."}
    ]
    formatted = format_characters(chars)
    assert "Kira: Cyberpunk runner with teal optics." in formatted
    assert "Vance: Enforcer in matte black exo-suit." in formatted

    # Empty cases
    assert format_characters([]) == "None specified."
    assert format_characters("") == "None specified."


def test_build_film_prompt_approval_on():
    settings = {
        "title": "Neon Horizons",
        "story": "A fast paced chase through Neo-Tokyo.",
        "style": "Cyberpunk anamorphic",
        "duration_minutes": 1.0,
        "seconds_per_clip": 8.0,
        "aspect": "16:9",
        "resolution": "1080p",
        "characters": [{"name": "Kira", "description": "Teal eyes"}],
        "narration": True,
        "voice": "en-US-ChristopherNeural",
        "keep_clip_audio_low": True,
        "background_music": True,
        "budget": 50,
        "approval_mode": True
    }
    job_folder = r"C:\fake\job_test"
    prompt = build_film_prompt(settings, job_folder)

    # Check key header lines
    assert "PROJECT: Make a short AI film with gflow-cli" in prompt
    assert "WORK FOLDER (all files go here, use absolute paths): C:/fake/job_test" in prompt
    assert "TITLE: Neon Horizons" in prompt
    assert "DURATION: 1.0 minutes = about 8 clips of 8 seconds." in prompt
    assert "MAX CREDIT BUDGET: 50." in prompt
    assert "Mode: Approval required before spending credits." in prompt

    # Check approval mode text in steps
    assert "COST CHECK, STOP: tell me clips needed, credits per clip, total credits, my balance, then wait for my 'go'" in prompt
    assert "wait for my approval." in prompt


def test_build_film_prompt_approval_off():
    settings = {
        "title": "Autonomous Short",
        "story": "An autonomous probe explores a ruined city.",
        "style": "Documentary realism",
        "duration_minutes": 0.5,
        "seconds_per_clip": 6.0,
        "aspect": "9:16",
        "resolution": "720p",
        "characters": [],
        "narration": False,
        "background_music": False,
        "budget": 30,
        "approval_mode": False
    }
    job_folder = r"C:\fake\job_autonomous"
    prompt = build_film_prompt(settings, job_folder)

    assert "Mode: Automatic generation within budget (do not ask for confirmation)." in prompt
    assert "Compute the cost; if it exceeds the budget, stop and tell me; otherwise continue" in prompt
    assert "no waiting." in prompt
    assert "NARRATION: Disabled" in prompt
    assert "MUSIC: Disabled" in prompt


def test_build_fallback_command():
    folder = r"C:\Jobs\job_123"
    cmd = build_fallback_command(folder)
    assert 'Read "C:/Jobs/job_123/prompt.md" and follow it exactly' in cmd
