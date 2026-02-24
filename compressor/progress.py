"""FFmpeg進捗パースモジュール"""
from __future__ import annotations


def parse_progress_line(line: str, total_duration_us: float, current_pass: int) -> float | None:
    """FFmpegの-progress出力行をパースして進捗率(0.0-1.0)を返す

    Pass 1 = 0.0-0.5, Pass 2 = 0.5-1.0 として計算
    """
    if not line.startswith("out_time_us="):
        return None

    try:
        out_time_us = int(line.split("=", 1)[1].strip())
    except (ValueError, IndexError):
        return None

    if total_duration_us <= 0:
        return None

    pass_progress = max(0.0, min(out_time_us / total_duration_us, 1.0))

    if current_pass == 1:
        return pass_progress * 0.5
    else:
        return 0.5 + pass_progress * 0.5
