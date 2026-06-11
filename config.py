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

GIF_WIDTH_PRESETS: dict[str, int | None] = {
    "オリジナル": None,
    "800px": 800,
    "640px": 640,
    "480px": 480,
    "320px": 320,
}

GIF_FPS_PRESETS: dict[str, int | None] = {
    "オリジナル": None,
    "15 fps": 15,
    "12 fps": 12,
    "10 fps": 10,
    "8 fps": 8,
}

# GIF圧縮: 試行ごとに色数・fps上限を段階的に下げる
GIF_COMPRESS_MAX_ATTEMPTS = 5
GIF_COMPRESS_COLORS_LADDER = [256, 192, 128, 96, 64]
GIF_COMPRESS_FPS_LADDER = [15, 12, 10, 10, 8]
GIF_COMPRESS_MIN_WIDTH = 64
GIF_COMPRESS_SAFETY = 0.95  # 実測補正時の安全係数

CONTAINER_OVERHEAD = 0.05  # 5%
MIN_VIDEO_BITRATE_KBPS = 100
DEFAULT_AUDIO_BITRATE_KBPS = 128
MAX_RETRY_COUNT = 2
RETRY_BITRATE_FACTOR = 0.95
TARGET_SIZE_TOLERANCE = 0.05  # 5%
CHUNK_SIZE = 1024 * 1024  # 1MB
