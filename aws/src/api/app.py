"""ジョブ作成・ステータス取得API（API Gateway HTTP API v2）"""
from __future__ import annotations

import json
import os
import time
import urllib.parse
import uuid
from decimal import Decimal

import boto3

TABLE_NAME = os.environ["TABLE_NAME"]
FILES_BUCKET = os.environ["FILES_BUCKET"]
MAX_UPLOAD_BYTES = int(os.environ["MAX_UPLOAD_BYTES"])

VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"}
GIF_EXTS = {".gif"}
MODES = {"video", "gif_resize", "gif_compress"}
JOB_TTL_SECONDS = 24 * 3600
DOWNLOAD_URL_EXPIRES = 900
UPLOAD_URL_EXPIRES = 3600

s3 = boto3.client("s3")
table = boto3.resource("dynamodb").Table(TABLE_NAME)


def handler(event, context):
    route = event.get("routeKey", "")
    try:
        if route == "POST /api/jobs":
            return _create_job(event)
        if route == "GET /api/jobs/{jobId}":
            return _get_job(event)
        return _resp(404, {"error": "not found"})
    except ValueError as e:
        return _resp(400, {"error": str(e)})


def _create_job(event) -> dict:
    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        raise ValueError("リクエストボディが不正です")

    mode = body.get("mode")
    if mode not in MODES:
        raise ValueError(f"modeは {sorted(MODES)} のいずれかを指定してください")

    filename = str(body.get("filename") or "")
    ext = os.path.splitext(filename)[1].lower()
    allowed = GIF_EXTS if mode.startswith("gif") else VIDEO_EXTS
    if ext not in allowed:
        raise ValueError(f"対応していない拡張子です: {ext or '(なし)'}（対応: {sorted(allowed)}）")

    params = _validate_params(mode, body)

    job_id = uuid.uuid4().hex
    input_key = f"uploads/{job_id}/input{ext}"
    now = int(time.time())

    table.put_item(Item={
        "jobId": job_id,
        "status": "pending",
        "mode": mode,
        "paramsJson": json.dumps(params),
        "filename": filename,
        "inputKey": input_key,
        "progress": Decimal(0),
        "createdAt": now,
        "ttl": now + JOB_TTL_SECONDS,
    })

    post = s3.generate_presigned_post(
        Bucket=FILES_BUCKET,
        Key=input_key,
        Conditions=[["content-length-range", 1, MAX_UPLOAD_BYTES]],
        ExpiresIn=UPLOAD_URL_EXPIRES,
    )

    return _resp(200, {"jobId": job_id, "upload": post, "maxUploadBytes": MAX_UPLOAD_BYTES})


def _validate_params(mode: str, body: dict) -> dict:
    params: dict = {}

    if mode in ("video", "gif_compress"):
        target = body.get("targetSizeMb")
        if not isinstance(target, (int, float)) or not (0.1 <= target <= 2048):
            raise ValueError("targetSizeMbは0.1〜2048の数値で指定してください")
        params["targetSizeMb"] = float(target)

    if mode == "video":
        width = body.get("resolutionWidth")
        if width is not None and (not isinstance(width, int) or not (64 <= width <= 3840)):
            raise ValueError("resolutionWidthは64〜3840の整数かnullで指定してください")
        params["resolutionWidth"] = width

        audio = body.get("audioBitrateKbps", 128)
        if not isinstance(audio, (int, float)) or not (32 <= audio <= 320):
            raise ValueError("audioBitrateKbpsは32〜320で指定してください")
        params["audioBitrateKbps"] = float(audio)

    if mode == "gif_resize":
        width = body.get("gifWidth")
        if width is not None and (not isinstance(width, int) or not (64 <= width <= 1920)):
            raise ValueError("gifWidthは64〜1920の整数かnullで指定してください")
        params["gifWidth"] = width

        fps = body.get("gifFps")
        if fps is not None and (not isinstance(fps, int) or not (1 <= fps <= 60)):
            raise ValueError("gifFpsは1〜60の整数かnullで指定してください")
        params["gifFps"] = fps

    return params


def _get_job(event) -> dict:
    job_id = (event.get("pathParameters") or {}).get("jobId", "")
    if not job_id:
        raise ValueError("jobIdがありません")

    item = table.get_item(Key={"jobId": job_id}).get("Item")
    if not item:
        return _resp(404, {"error": "ジョブが見つかりません"})

    result = {
        "jobId": job_id,
        "status": item.get("status"),
        "mode": item.get("mode"),
        "filename": item.get("filename"),
        "progress": float(item.get("progress", 0)),
    }
    if item.get("error"):
        result["error"] = item["error"]
    if item.get("attempt"):
        result["attempt"] = int(item["attempt"])
        result["maxAttempts"] = int(item.get("maxAttempts", 0))
    if item.get("outputSizeBytes") is not None:
        result["outputSizeBytes"] = int(item["outputSizeBytes"])

    if item.get("status") == "completed" and item.get("outputKey"):
        out_ext = os.path.splitext(item["outputKey"])[1]
        base = os.path.splitext(str(item.get("filename") or "output"))[0]
        download_name = f"{base}_compressed{out_ext}"
        disposition = f"attachment; filename*=UTF-8''{urllib.parse.quote(download_name)}"
        result["downloadUrl"] = s3.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": FILES_BUCKET,
                "Key": item["outputKey"],
                "ResponseContentDisposition": disposition,
            },
            ExpiresIn=DOWNLOAD_URL_EXPIRES,
        )

    return _resp(200, result)


def _resp(status: int, body: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(body, ensure_ascii=False),
    }
