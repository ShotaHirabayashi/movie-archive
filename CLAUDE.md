# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## プロジェクト概要

Movie Cut - 動画を目標ファイルサイズに圧縮するWebツール。Python + Streamlit + FFmpeg（subprocess経由の2-pass encoding）で構成。

## コマンド

```bash
# ローカル起動（FFmpegが必要: brew install ffmpeg）
pip install -r requirements.txt
streamlit run app.py

# Docker起動
docker build -t movie-cut . && docker run -p 7860:7860 movie-cut
```

## デプロイ

**Hugging Face Spaces**（Docker SDK）にデプロイ中。
- Space: https://huggingface.co/spaces/Shota1005/movie-cut
- URL: https://shota1005-movie-cut.hf.space
- ポート: 7860（Dockerfile で指定）

ファイル更新時は `huggingface_hub` API でアップロードするか、HF Space側のGitリポジトリにpushする。

```python
from huggingface_hub import HfApi
api = HfApi()
api.upload_file(path_or_fileobj="app.py", path_in_repo="app.py", repo_id="Shota1005/movie-cut", repo_type="space")
```

GitHubリポジトリ: https://github.com/ShotaHirabayashi/movie-archive

## アーキテクチャ

**データフロー**: アップロード → ffprobeでメタデータ取得 → ビットレート計算 → FFmpeg 2-pass encode → ダウンロード

- `app.py` - Streamlit UI。同期的にFFmpegを実行し、`st.progress()` + `st.empty()` でリアルタイム進捗表示
- `compressor/encoder.py` - 2-pass encoding の本体。`-progress pipe:1` のstdout をパースして進捗コールバックを呼ぶ。stderrは一時ファイルに書き出す（PIPEデッドロック回避）。出力が目標サイズを5%超過した場合、95%ビットレートで最大2回リトライ
- `compressor/ffprobe.py` - `VideoMetadata` dataclass + ffprobe JSON出力パーサー
- `compressor/bitrate_calculator.py` - 目標サイズ(MB) + 動画長(秒) → ビットレート算出。コンテナオーバーヘッド5%考慮
- `compressor/progress.py` - FFmpegの `out_time_us` を進捗率(0.0-1.0)に変換。Pass1=0-0.5, Pass2=0.5-1.0。負値は0にクランプ
- `utils/file_manager.py` - アップロードファイルのチャンク書き込み保存、`st.session_state`でパスキャッシュ、一時ファイルクリーンアップ
- `config.py` - 解像度/音声プリセット、圧縮パラメータ定数

## 注意事項

- 全 `.py` ファイルに `from __future__ import annotations` が必要（Python 3.9互換のため）
- FFmpegの `-stats_period` オプションは `encoder.py` 内で自動検出（古いバージョン非対応）
- 2-passログは `tempfile.mkdtemp()` でユニークなディレクトリに作成（複数ユーザー同時利用の競合回避）
- FFmpegの `out_time_us` は負値を返すことがある → `progress.py` で `max(0.0, ...)` でクランプ済み
