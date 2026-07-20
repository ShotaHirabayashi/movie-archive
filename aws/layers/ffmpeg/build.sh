#!/usr/bin/env bash
# ffmpeg/ffprobe static build (linux arm64) をLambda Layer用に配置する
# 取得済みならスキップ。強制再取得は layer_content/ を削除してから実行
set -euo pipefail
cd "$(dirname "$0")"

DEST="layer_content/bin"
if [[ -x "$DEST/ffmpeg" && -x "$DEST/ffprobe" ]]; then
  echo "ffmpeg layer already built: $DEST"
  exit 0
fi

mkdir -p "$DEST"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo "Downloading ffmpeg static build (BtbN linuxarm64)..."
if curl -fL --retry 3 -o "$TMP/ffmpeg.tar.xz" \
  "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linuxarm64-gpl.tar.xz"; then
  tar -xJf "$TMP/ffmpeg.tar.xz" -C "$TMP"
  SRC_DIR="$(find "$TMP" -maxdepth 1 -type d -name 'ffmpeg-*')"
  cp "$SRC_DIR/bin/ffmpeg" "$SRC_DIR/bin/ffprobe" "$DEST/"
else
  echo "BtbN failed, falling back to johnvansickle..."
  curl -fL --retry 3 -o "$TMP/ffmpeg.tar.xz" \
    "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-arm64-static.tar.xz"
  tar -xJf "$TMP/ffmpeg.tar.xz" -C "$TMP"
  SRC_DIR="$(find "$TMP" -maxdepth 1 -type d -name 'ffmpeg-*')"
  cp "$SRC_DIR/ffmpeg" "$SRC_DIR/ffprobe" "$DEST/"
fi

chmod +x "$DEST/ffmpeg" "$DEST/ffprobe"
echo "Layer content ready:"
ls -lh "$DEST"
