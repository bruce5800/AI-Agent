"""Text-to-speech using Edge TTS with role-specific Chinese voices."""

import asyncio
import os
import re
import tempfile
import edge_tts


# Voice assignments — different voices for different debate roles
VOICE_MAP = {
    "正方": "zh-CN-YunxiNeural",       # Male, clear
    "反方": "zh-CN-YunyangNeural",      # Male, authoritative
    "主持人": "zh-CN-XiaoxiaoNeural",   # Female, professional
    "评委": "zh-CN-XiaoyiNeural",       # Female, calm
    "观众": "zh-CN-XiaochenNeural",     # Female, casual
}

DEFAULT_VOICE = "zh-CN-XiaoxiaoNeural"


def _clean_for_tts(text: str) -> str:
    """Remove markdown formatting that shouldn't be spoken."""
    # Remove markdown bold/italic
    text = re.sub(r'\*{1,3}([^*]+)\*{1,3}', r'\1', text)
    # Remove markdown tables
    text = re.sub(r'\|[^\n]+\|', '', text)
    text = re.sub(r'\|?[-:]+\|[-:|\s]+', '', text)
    # Remove markdown headers
    text = re.sub(r'#{1,6}\s*', '', text)
    # Remove markdown links
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    # Collapse whitespace
    text = re.sub(r'\n{2,}', '\n', text)
    return text.strip()


async def _tts_save(text: str, voice: str, path: str) -> None:
    """Generate TTS and save to file (includes proper file headers)."""
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(path)


def generate_speech(text: str, side: str = "") -> bytes | None:
    """Generate TTS audio for debate text.

    Args:
        text: The text to speak.
        side: The speaker's side ("正方", "反方", "主持人", "评委", "观众").

    Returns:
        MP3 audio bytes with proper headers, or None if generation fails.
    """
    cleaned = _clean_for_tts(text)
    if not cleaned:
        return None

    voice = VOICE_MAP.get(side, DEFAULT_VOICE)

    tmp_path = None
    try:
        fd, tmp_path = tempfile.mkstemp(suffix=".mp3")
        os.close(fd)

        loop = asyncio.new_event_loop()
        loop.run_until_complete(_tts_save(cleaned, voice, tmp_path))
        loop.close()

        with open(tmp_path, "rb") as f:
            audio_bytes = f.read()

        return audio_bytes if audio_bytes else None
    except Exception:
        return None
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


def estimate_duration(audio_bytes: bytes) -> float:
    """Estimate audio duration in seconds from MP3 bytes.

    edge-tts outputs 48kbps mono audio consistently.
    """
    return len(audio_bytes) / 6000  # 48kbps = 6000 bytes/sec
