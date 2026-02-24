"""定数・プリセット定義"""
from __future__ import annotations

RESOLUTION_PRESETS: dict[str, tuple[int, int] | None] = {
    "オリジナル": None,
    "1080p (1920x1080)": (1920, 1080),
    "720p (1280x720)": (1280, 720),
    "480p (854x480)": (854, 480),
    "360p (640x360)": (640, 360),
}

AUDIO_BITRATE_PRESETS: dict[str, int] = {
    "64 kbps (低品質)": 64,
    "96 kbps": 96,
    "128 kbps (標準)": 128,
    "192 kbps (高品質)": 192,
    "256 kbps (最高品質)": 256,
}

CONTAINER_OVERHEAD = 0.05  # 5%
MIN_VIDEO_BITRATE_KBPS = 100
DEFAULT_AUDIO_BITRATE_KBPS = 128
MAX_RETRY_COUNT = 2
RETRY_BITRATE_FACTOR = 0.95
TARGET_SIZE_TOLERANCE = 0.05  # 5%
CHUNK_SIZE = 1024 * 1024  # 1MB
