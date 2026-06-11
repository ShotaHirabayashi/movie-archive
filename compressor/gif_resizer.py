"""GIFリサイズモジュール（palettegen + paletteuse の2-pass）"""
from __future__ import annotations

import os
import shutil
import tempfile
from collections.abc import Callable

from compressor.encoder import _get_stats_period_args, _run_ffmpeg


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
    total_duration_us = duration_seconds * 1_000_000
    chain = _build_filter_chain(width, fps) or "null"

    palette_dir = tempfile.mkdtemp(prefix="gif_palette_")
    palette_path = os.path.join(palette_dir, "palette.png")

    try:
        pass1_cmd = [
            "ffmpeg", "-y",
            *_get_stats_period_args(),
            "-i", input_path,
            "-vf", f"{chain},palettegen=stats_mode=diff",
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
