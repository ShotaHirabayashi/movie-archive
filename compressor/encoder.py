"""FFmpeg 2-pass エンコードモジュール"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from collections.abc import Callable

from compressor.progress import parse_progress_line
from config import MAX_RETRY_COUNT, RETRY_BITRATE_FACTOR, TARGET_SIZE_TOLERANCE


def _ffmpeg_supports_stats_period() -> bool:
    """FFmpegが -stats_period をサポートしているか確認する"""
    try:
        r = subprocess.run(
            ["ffmpeg", "-stats_period", "1", "-f", "lavfi", "-i", "nullsrc=d=0", "-f", "null", "-"],
            capture_output=True, text=True, timeout=5,
        )
        return "Unrecognized option" not in r.stderr
    except Exception:
        return False


_HAS_STATS_PERIOD: bool | None = None


def _get_stats_period_args() -> list[str]:
    global _HAS_STATS_PERIOD
    if _HAS_STATS_PERIOD is None:
        _HAS_STATS_PERIOD = _ffmpeg_supports_stats_period()
    return ["-stats_period", "0.5"] if _HAS_STATS_PERIOD else []


def encode_video(
    input_path: str,
    output_path: str,
    video_bitrate_kbps: float,
    audio_bitrate_kbps: float,
    has_audio: bool,
    duration_seconds: float,
    resolution: tuple[int, int] | None = None,
    progress_callback: Callable[[float], None] | None = None,
) -> str:
    """2-pass エンコードを実行する

    Returns:
        出力ファイルのパス
    """
    passlog_prefix = os.path.join(tempfile.gettempdir(), "ffmpeg2pass")
    total_duration_us = duration_seconds * 1_000_000

    current_bitrate_kbps = video_bitrate_kbps

    for attempt in range(1 + MAX_RETRY_COUNT):
        _run_pass1(input_path, current_bitrate_kbps, resolution, passlog_prefix, total_duration_us, progress_callback)
        _run_pass2(input_path, output_path, current_bitrate_kbps, audio_bitrate_kbps, has_audio, resolution, passlog_prefix, total_duration_us, progress_callback)

        output_size = os.path.getsize(output_path)
        target_bits = (current_bitrate_kbps + (audio_bitrate_kbps if has_audio else 0)) * 1000 * duration_seconds
        target_bytes = target_bits / 8

        if output_size <= target_bytes * (1 + TARGET_SIZE_TOLERANCE):
            break

        if attempt < MAX_RETRY_COUNT:
            current_bitrate_kbps *= RETRY_BITRATE_FACTOR
            if progress_callback:
                progress_callback(0.0)

    _cleanup_passlog(passlog_prefix)
    return output_path


def _build_vf_filter(resolution: tuple[int, int] | None) -> list[str]:
    if resolution is None:
        return []
    w, h = resolution
    return ["-vf", f"scale={w}:-2"]


def _run_pass1(
    input_path: str,
    video_bitrate_kbps: float,
    resolution: tuple[int, int] | None,
    passlog_prefix: str,
    total_duration_us: float,
    progress_callback: Callable[[float], None] | None,
) -> None:
    vf = _build_vf_filter(resolution)
    cmd = [
        "ffmpeg", "-y",
        *_get_stats_period_args(),
        "-i", input_path,
        "-c:v", "libx264",
        "-b:v", f"{int(video_bitrate_kbps)}k",
        "-pass", "1",
        "-passlogfile", passlog_prefix,
        *vf,
        "-an",
        "-f", "null",
        "-progress", "pipe:1",
        os.devnull,
    ]
    _run_ffmpeg(cmd, total_duration_us, current_pass=1, progress_callback=progress_callback)


def _run_pass2(
    input_path: str,
    output_path: str,
    video_bitrate_kbps: float,
    audio_bitrate_kbps: float,
    has_audio: bool,
    resolution: tuple[int, int] | None,
    passlog_prefix: str,
    total_duration_us: float,
    progress_callback: Callable[[float], None] | None,
) -> None:
    vf = _build_vf_filter(resolution)
    audio_opts = ["-c:a", "aac", "-b:a", f"{int(audio_bitrate_kbps)}k"] if has_audio else ["-an"]
    cmd = [
        "ffmpeg", "-y",
        *_get_stats_period_args(),
        "-i", input_path,
        "-c:v", "libx264",
        "-b:v", f"{int(video_bitrate_kbps)}k",
        "-pass", "2",
        "-passlogfile", passlog_prefix,
        *vf,
        *audio_opts,
        "-progress", "pipe:1",
        output_path,
    ]
    _run_ffmpeg(cmd, total_duration_us, current_pass=2, progress_callback=progress_callback)


def _run_ffmpeg(
    cmd: list[str],
    total_duration_us: float,
    current_pass: int,
    progress_callback: Callable[[float], None] | None,
) -> None:
    stderr_log = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".log")
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=stderr_log,
        text=True,
    )

    if process.stdout:
        for line in process.stdout:
            line = line.strip()
            if progress_callback:
                progress = parse_progress_line(line, total_duration_us, current_pass)
                if progress is not None:
                    progress_callback(progress)

    returncode = process.wait()
    stderr_log.close()

    if returncode != 0:
        try:
            with open(stderr_log.name) as f:
                stderr_text = f.read()
        except OSError:
            stderr_text = "(ログ読み取り不可)"
        os.remove(stderr_log.name)
        raise RuntimeError(f"FFmpeg エラー (pass {current_pass}): {stderr_text}")

    os.remove(stderr_log.name)


def _cleanup_passlog(passlog_prefix: str) -> None:
    for suffix in ["-0.log", "-0.log.mbtree"]:
        path = passlog_prefix + suffix
        if os.path.exists(path):
            os.remove(path)
