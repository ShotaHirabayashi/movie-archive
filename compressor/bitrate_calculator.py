"""ビットレート計算モジュール"""
from __future__ import annotations

from dataclasses import dataclass

from config import CONTAINER_OVERHEAD, DEFAULT_AUDIO_BITRATE_KBPS, MIN_VIDEO_BITRATE_KBPS


@dataclass
class BitrateResult:
    video_bitrate_kbps: float
    audio_bitrate_kbps: float
    total_bitrate_kbps: float
    is_feasible: bool
    warning: str | None = None


def calculate_bitrate(
    target_size_mb: float,
    duration_seconds: float,
    audio_bitrate_kbps: float = DEFAULT_AUDIO_BITRATE_KBPS,
    has_audio: bool = True,
) -> BitrateResult:
    """目標サイズと動画長からビットレートを計算する

    計算式:
        video_bitrate = (target_size_bytes * 8 / (1 - overhead) / duration) - audio_bitrate
    """
    if duration_seconds <= 0:
        return BitrateResult(
            video_bitrate_kbps=0,
            audio_bitrate_kbps=0,
            total_bitrate_kbps=0,
            is_feasible=False,
            warning="動画の長さが0秒です",
        )

    target_size_bits = target_size_mb * 1024 * 1024 * 8
    effective_bitrate = target_size_bits / (1 - CONTAINER_OVERHEAD) / duration_seconds
    effective_bitrate_kbps = effective_bitrate / 1000

    actual_audio_kbps = audio_bitrate_kbps if has_audio else 0
    video_bitrate_kbps = effective_bitrate_kbps - actual_audio_kbps

    warning = None
    is_feasible = True

    if video_bitrate_kbps < MIN_VIDEO_BITRATE_KBPS:
        warning = (
            f"計算されたビットレート ({video_bitrate_kbps:.0f} kbps) が"
            f"最低ビットレート ({MIN_VIDEO_BITRATE_KBPS} kbps) を下回っています。"
            "目標サイズを大きくするか、音声ビットレートを下げてください。"
        )
        video_bitrate_kbps = MIN_VIDEO_BITRATE_KBPS
        is_feasible = False

    total_kbps = video_bitrate_kbps + actual_audio_kbps

    return BitrateResult(
        video_bitrate_kbps=video_bitrate_kbps,
        audio_bitrate_kbps=actual_audio_kbps,
        total_bitrate_kbps=total_kbps,
        is_feasible=is_feasible,
        warning=warning,
    )
