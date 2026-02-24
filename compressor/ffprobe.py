"""動画メタデータ取得モジュール"""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass


@dataclass
class VideoMetadata:
    duration: float  # 秒
    width: int
    height: int
    video_codec: str
    video_bitrate: int  # bps
    file_size: int  # bytes
    has_audio: bool
    audio_codec: str | None = None
    audio_bitrate: int | None = None  # bps

    @property
    def resolution_label(self) -> str:
        return f"{self.width}x{self.height}"

    @property
    def file_size_mb(self) -> float:
        return self.file_size / (1024 * 1024)

    @property
    def duration_str(self) -> str:
        m, s = divmod(int(self.duration), 60)
        h, m = divmod(m, 60)
        if h > 0:
            return f"{h}時間{m}分{s}秒"
        return f"{m}分{s}秒"

    @property
    def total_bitrate_kbps(self) -> float:
        return self.video_bitrate / 1000


def get_video_metadata(file_path: str) -> VideoMetadata:
    """ffprobeで動画メタデータを取得する"""
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        file_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(result.stdout)

    video_stream = None
    audio_stream = None
    for stream in data.get("streams", []):
        if stream["codec_type"] == "video" and video_stream is None:
            video_stream = stream
        elif stream["codec_type"] == "audio" and audio_stream is None:
            audio_stream = stream

    if video_stream is None:
        raise ValueError("動画ストリームが見つかりません")

    fmt = data.get("format", {})
    file_size = int(fmt.get("size", 0))
    duration = float(fmt.get("duration", 0))

    video_bitrate = int(video_stream.get("bit_rate", 0))
    if video_bitrate == 0 and duration > 0:
        total_bitrate = int(fmt.get("bit_rate", 0))
        audio_br = int(audio_stream.get("bit_rate", 0)) if audio_stream else 0
        video_bitrate = max(total_bitrate - audio_br, 0)

    return VideoMetadata(
        duration=duration,
        width=int(video_stream.get("width", 0)),
        height=int(video_stream.get("height", 0)),
        video_codec=video_stream.get("codec_name", "unknown"),
        video_bitrate=video_bitrate,
        file_size=file_size,
        has_audio=audio_stream is not None,
        audio_codec=audio_stream.get("codec_name") if audio_stream else None,
        audio_bitrate=int(audio_stream.get("bit_rate", 0)) if audio_stream and audio_stream.get("bit_rate") else None,
    )
