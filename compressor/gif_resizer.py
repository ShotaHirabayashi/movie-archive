"""GIFリサイズ・圧縮モジュール（palettegen + paletteuse の2-pass）"""
from __future__ import annotations

import math
import os
import shutil
import tempfile
from collections.abc import Callable

from compressor.encoder import _get_stats_period_args, _run_ffmpeg
from config import (
    GIF_COMPRESS_COLORS_LADDER,
    GIF_COMPRESS_FPS_LADDER,
    GIF_COMPRESS_MAX_ATTEMPTS,
    GIF_COMPRESS_MIN_WIDTH,
    GIF_COMPRESS_SAFETY,
)


def resize_gif(
    input_path: str,
    output_path: str,
    duration_seconds: float,
    width: int | None = None,
    fps: int | None = None,
    progress_callback: Callable[[float], None] | None = None,
) -> str:
    """GIFをリサイズする

    Pass 1で最適カラーパレットを生成し、Pass 2でパレットを適用してGIFを出力する。
    widthがNoneなら元の解像度、fpsがNoneなら元のフレームレートを維持する。

    Returns:
        出力ファイルのパス
    """
    return _encode_gif(
        input_path, output_path, duration_seconds,
        width=width, fps=fps, progress_callback=progress_callback,
    )


def compress_gif(
    input_path: str,
    output_path: str,
    target_size_mb: float,
    duration_seconds: float,
    original_width: int,
    original_fps: float | None = None,
    progress_callback: Callable[[float], None] | None = None,
    attempt_callback: Callable[[int, int], None] | None = None,
) -> str:
    """GIFを目標ファイルサイズ以下に圧縮する

    GIFはビットレート指定ができないため、解像度・色数・フレームレートを
    段階的に下げながら目標サイズ以下になるまで最大GIF_COMPRESS_MAX_ATTEMPTS回試行する。
    初回の縮小率はGIFサイズが画素数にほぼ比例する性質からsqrt(目標/元サイズ)で見積もり、
    2回目以降は実測サイズとの比率で補正する。

    Returns:
        出力ファイルのパス（全試行で目標を超えた場合も最終結果を返す）
    """
    target_bytes = target_size_mb * 1024 * 1024
    original_size = os.path.getsize(input_path)
    ratio = target_bytes / original_size

    scale = min(1.0, math.sqrt(ratio))

    for attempt in range(GIF_COMPRESS_MAX_ATTEMPTS):
        if attempt_callback:
            attempt_callback(attempt + 1, GIF_COMPRESS_MAX_ATTEMPTS)

        width = max(GIF_COMPRESS_MIN_WIDTH, int(original_width * scale))
        max_colors = GIF_COMPRESS_COLORS_LADDER[min(attempt, len(GIF_COMPRESS_COLORS_LADDER) - 1)]
        fps_cap = GIF_COMPRESS_FPS_LADDER[min(attempt, len(GIF_COMPRESS_FPS_LADDER) - 1)]
        # 元fpsより高い値を指定するとフレーム複製で逆に肥大化するため、下げる場合のみ適用
        fps = fps_cap if original_fps is None or fps_cap < original_fps else None

        _encode_gif(
            input_path, output_path, duration_seconds,
            width=width, fps=fps, max_colors=max_colors,
            progress_callback=progress_callback,
        )

        output_size = os.path.getsize(output_path)
        if output_size <= target_bytes:
            break

        if width <= GIF_COMPRESS_MIN_WIDTH:
            break

        scale = min(scale, width / original_width)
        scale *= math.sqrt(target_bytes / output_size) * GIF_COMPRESS_SAFETY

    return output_path


def _encode_gif(
    input_path: str,
    output_path: str,
    duration_seconds: float,
    width: int | None = None,
    fps: int | None = None,
    max_colors: int = 256,
    progress_callback: Callable[[float], None] | None = None,
) -> str:
    total_duration_us = duration_seconds * 1_000_000
    chain = _build_filter_chain(width, fps) or "null"

    palette_dir = tempfile.mkdtemp(prefix="gif_palette_")
    palette_path = os.path.join(palette_dir, "palette.png")

    try:
        pass1_cmd = [
            "ffmpeg", "-y",
            *_get_stats_period_args(),
            "-i", input_path,
            "-vf", f"{chain},palettegen=stats_mode=diff:max_colors={max_colors}",
            "-progress", "pipe:1",
            palette_path,
        ]
        _run_ffmpeg(pass1_cmd, total_duration_us, current_pass=1, progress_callback=progress_callback)

        pass2_cmd = [
            "ffmpeg", "-y",
            *_get_stats_period_args(),
            "-i", input_path,
            "-i", palette_path,
            "-lavfi", f"[0:v]{chain}[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle",
            "-progress", "pipe:1",
            output_path,
        ]
        _run_ffmpeg(pass2_cmd, total_duration_us, current_pass=2, progress_callback=progress_callback)
    finally:
        shutil.rmtree(palette_dir, ignore_errors=True)

    return output_path


def _build_filter_chain(width: int | None, fps: int | None) -> str:
    parts = []
    if fps is not None:
        parts.append(f"fps={fps}")
    if width is not None:
        # min(width, iw) で元サイズより大きくしない（アップスケール防止）
        parts.append(f"scale=min({width}\\,iw):-1:flags=lanczos")
    return ",".join(parts)
