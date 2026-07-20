"""S3イベントで起動する圧縮ワーカー

uploads/{jobId}/input.{ext} のObjectCreatedで起動し、
既存のcompressorモジュール（ビルド時にリポルートからコピー）で圧縮して
outputs/{jobId}/output.{ext} に出力する。進捗はDynamoDBへ間引き書き込み。
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile
import time
import traceback
import urllib.parse
from decimal import Decimal

import boto3

from compressor.bitrate_calculator import calculate_bitrate
from compressor.encoder import encode_video
from compressor.ffprobe import get_video_metadata
from compressor.gif_resizer import compress_gif, resize_gif

logger = logging.getLogger()
logger.setLevel(logging.INFO)

TABLE_NAME = os.environ["TABLE_NAME"]

s3 = boto3.client("s3")
table = boto3.resource("dynamodb").Table(TABLE_NAME)

CONTENT_TYPES = {".mp4": "video/mp4", ".gif": "image/gif"}


class ProgressWriter:
    """進捗率をDynamoDBへ間引き書き込みする（2秒間隔または5%刻み）"""

    def __init__(self, job_id: str):
        self.job_id = job_id
        self._last_time = 0.0
        self._last_value = -1.0

    def __call__(self, progress: float) -> None:
        now = time.monotonic()
        if progress < 1.0 and now - self._last_time < 2.0 and progress - self._last_value < 0.05:
            return
        self._last_time = now
        self._last_value = progress
        _update(self.job_id, "SET progress = :p", {":p": Decimal(str(round(progress, 4)))})


def handler(event, context):
    for record in event.get("Records", []):
        bucket = record["s3"]["bucket"]["name"]
        key = urllib.parse.unquote_plus(record["s3"]["object"]["key"])
        _process(bucket, key)


def _process(bucket: str, key: str) -> None:
    parts = key.split("/")
    if len(parts) != 3 or parts[0] != "uploads":
        logger.warning("unexpected key: %s", key)
        return
    job_id = parts[1]

    item = table.get_item(Key={"jobId": job_id}).get("Item")
    if not item:
        logger.warning("job not found: %s", job_id)
        return
    if item.get("status") != "pending":
        # S3イベントの再送・二重配信対策
        logger.info("job %s already %s, skip", job_id, item.get("status"))
        return

    _update(job_id, "SET #s = :s, startedAt = :t",
            {":s": "processing", ":t": int(time.time())}, {"#s": "status"})

    work_dir = tempfile.mkdtemp(dir="/tmp", prefix=f"job_{job_id}_")
    try:
        in_path = os.path.join(work_dir, os.path.basename(key))
        s3.download_file(bucket, key, in_path)

        meta = get_video_metadata(in_path)
        mode = item["mode"]
        params = json.loads(item.get("paramsJson") or "{}")
        progress = ProgressWriter(job_id)

        if mode == "video":
            out_ext = ".mp4"
            out_path = os.path.join(work_dir, f"output{out_ext}")
            audio_kbps = float(params.get("audioBitrateKbps", 128))
            br = calculate_bitrate(
                target_size_mb=float(params["targetSizeMb"]),
                duration_seconds=meta.duration,
                audio_bitrate_kbps=audio_kbps,
                has_audio=meta.has_audio,
            )
            width = params.get("resolutionWidth")
            resolution = (int(width), 0) if width else None  # encoderはwidthのみ使用(scale=w:-2)
            encode_video(
                input_path=in_path,
                output_path=out_path,
                video_bitrate_kbps=br.video_bitrate_kbps,
                audio_bitrate_kbps=br.audio_bitrate_kbps,
                has_audio=meta.has_audio,
                duration_seconds=meta.duration,
                resolution=resolution,
                progress_callback=progress,
            )
        elif mode == "gif_resize":
            out_ext = ".gif"
            out_path = os.path.join(work_dir, f"output{out_ext}")
            width = params.get("gifWidth")
            fps = params.get("gifFps")
            resize_gif(
                input_path=in_path,
                output_path=out_path,
                duration_seconds=meta.duration,
                width=int(width) if width else None,
                fps=int(fps) if fps else None,
                progress_callback=progress,
            )
        elif mode == "gif_compress":
            out_ext = ".gif"
            out_path = os.path.join(work_dir, f"output{out_ext}")
            compress_gif(
                input_path=in_path,
                output_path=out_path,
                target_size_mb=float(params["targetSizeMb"]),
                duration_seconds=meta.duration,
                original_width=meta.width,
                original_fps=meta.fps,
                progress_callback=progress,
                attempt_callback=lambda a, m: _update(
                    job_id, "SET attempt = :a, maxAttempts = :m",
                    {":a": a, ":m": m}),
            )
        else:
            raise ValueError(f"未知のmode: {mode}")

        out_key = f"outputs/{job_id}/output{out_ext}"
        s3.upload_file(out_path, bucket, out_key,
                       ExtraArgs={"ContentType": CONTENT_TYPES[out_ext]})
        out_size = os.path.getsize(out_path)

        _update(job_id,
                "SET #s = :s, progress = :p, outputKey = :k, outputSizeBytes = :b, finishedAt = :t",
                {":s": "completed", ":p": Decimal(1), ":k": out_key,
                 ":b": out_size, ":t": int(time.time())},
                {"#s": "status"})
        logger.info("job %s completed: %s (%d bytes)", job_id, out_key, out_size)

    except Exception as e:
        logger.error("job %s failed: %s\n%s", job_id, e, traceback.format_exc())
        _update(job_id, "SET #s = :s, #e = :e",
                {":s": "failed", ":e": str(e)[:1000]},
                {"#s": "status", "#e": "error"})
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def _update(job_id: str, expr: str, values: dict, names: dict | None = None) -> None:
    kwargs = {
        "Key": {"jobId": job_id},
        "UpdateExpression": expr,
        "ExpressionAttributeValues": values,
    }
    if names:
        kwargs["ExpressionAttributeNames"] = names
    table.update_item(**kwargs)
