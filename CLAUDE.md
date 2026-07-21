# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## プロジェクト概要

Movie Cut - 動画を目標ファイルサイズに圧縮するWebツール。GIFのリサイズ・圧縮機能も搭載。圧縮ロジックはPython + FFmpeg（subprocess経由の2-pass encoding）で、AWSサーバーレス構成（本番）とStreamlit（ローカル用）の2つのフロントを持つ。

## コマンド

```bash
# ローカル起動（Streamlit版、FFmpegが必要: brew install ffmpeg）
pip install -r requirements.txt
streamlit run app.py

# フロントエンド開発（AWS版UI）
cd frontend && npm install && npm run dev

# AWS版フルデプロイ（Layer取得→共有コード同期→sam build/deploy→フロントsync→CF invalidation）
./aws/deploy.sh
```

## デプロイ（本番: AWS serverless）

- **AWSアカウント**: denwa-dev (553113730995) / **リージョン**: ap-northeast-1 / **スタック名**: movie-cut
- **URL**: https://d34kvdm47i1n8p.cloudfront.net
- **構成**: S3+CloudFront（UI配信）→ API Gateway HTTP API + Lambda（ジョブAPI）→ S3イベント + Lambda + FFmpeg Layer（圧縮ワーカー）→ DynamoDB（ジョブ状態）
- デプロイは `./aws/deploy.sh` 一発（samconfig.tomlにprofile/region設定済み）
- 旧Hugging Face Space（Shota1005/movie-cut）は一時停止中（GitHub Actions同期は削除済み。不要になったら削除してよい）

## アーキテクチャ

**共有圧縮ロジック**（Streamlit版とAWS版で共用。リポルートが正、AWSビルド時に `aws/src/worker/` へコピー）:

- `compressor/encoder.py` - 2-pass encoding の本体。`-progress pipe:1` のstdout をパースして進捗コールバックを呼ぶ。stderrは一時ファイルに書き出す（PIPEデッドロック回避）。出力が目標サイズを5%超過した場合、95%ビットレートで最大2回リトライ
- `compressor/gif_resizer.py` - GIFリサイズ（`resize_gif`）と GIF圧縮（`compress_gif`）。Pass1で `palettegen`、Pass2で `paletteuse` を適用（パレット最適化）。`scale=min(width\,iw)` でアップスケール防止。FFmpeg実行は `encoder._run_ffmpeg` を流用。圧縮はGIFにビットレート指定がないため、初回 `sqrt(目標/元サイズ)` で縮小率を見積もり、実測サイズで補正しながら解像度・色数・fpsを段階的に下げて最大5回試行（`config.py` のladder定数）。fpsは元fps未満の場合のみ適用（フレーム複製による肥大化防止）
- `compressor/ffprobe.py` - `VideoMetadata` dataclass + ffprobe JSON出力パーサー（GIFも解析可、`fps` フィールドあり）
- `compressor/bitrate_calculator.py` - 目標サイズ(MB) + 動画長(秒) → ビットレート算出。コンテナオーバーヘッド5%考慮
- `compressor/progress.py` - FFmpegの `out_time_us` を進捗率(0.0-1.0)に変換。Pass1=0-0.5, Pass2=0.5-1.0。負値は0にクランプ
- `config.py` - 解像度/音声プリセット、圧縮パラメータ定数

**AWS版**（`aws/` + `frontend/`）:

**データフロー**: フロントがPOST /api/jobs（パラメータ登録+presigned POST取得）→ ブラウザからS3へ直接アップロード → S3イベントでワーカーLambda起動 → 圧縮 → outputs/へ出力 → フロントは2秒ポーリングで進捗表示 → presigned GETでダウンロード

- `aws/template.yaml` - SAMテンプレート。CloudFrontは2オリジン構成（デフォルト→UIバケット(OAC)、`/api/*`→API GW）。ファイルバケットはライフサイクル1日で自動削除、presigned POSTの`content-length-range`で1GB上限。ワーカーは8192MB/900秒/ephemeral 10GB/同時実行3
- `aws/src/api/app.py` - ジョブ作成・ステータス取得。s3クライアントは**リージョナルエンドポイント+SigV4必須**（グローバルは307リダイレクトでブラウザアップロードが不安定）
- `aws/src/worker/app.py` - S3イベント起動。進捗をDynamoDBへ間引き書き込み（2秒or5%刻み）。二重配信はstatus=pendingチェックで防止。ffmpeg/ffprobeはLayerの`/opt/bin`（LambdaのPATHに含まれる）
- `aws/layers/ffmpeg/build.sh` - BtbN linuxarm64 static buildを取得（layer_content/はgit管理外）
- `frontend/` - React 19 + Vite + Tailwind v4 + Catalyst UIキット（`src/components/`にコピー済み）。APIは同一オリジン`/api/*`（CloudFront経由）なのでCORS不要。ジョブ状態は2秒ポーリング

**Streamlit版**（ローカル用）:

- `app.py` - Streamlit UI。サイドバーの `st.sidebar.radio` で「動画圧縮」「GIFリサイズ」「GIF圧縮」を切り替え。同期的にFFmpegを実行し、`st.progress()` + `st.empty()` でリアルタイム進捗表示
- `utils/file_manager.py` - アップロードファイルのチャンク書き込み保存、`st.session_state`でパスキャッシュ、一時ファイルクリーンアップ

## 注意事項

- 全 `.py` ファイルに `from __future__ import annotations` が必要（Python 3.9互換のため）
- FFmpegの `-stats_period` オプションは `encoder.py` 内で自動検出（古いバージョン非対応）
- 2-passログは `tempfile.mkdtemp()` でユニークなディレクトリに作成（複数ユーザー同時利用の競合回避）
- FFmpegの `out_time_us` は負値を返すことがある → `progress.py` で `max(0.0, ...)` でクランプ済み
- `aws/src/worker/compressor/` と `aws/src/worker/config.py` はビルド時コピー（git管理外）。圧縮ロジックの修正は必ずリポルート側で行う
- Lambdaの実行上限15分のため長尺・巨大動画は失敗しうる（フロントは20分でタイムアウト表示）。需要が出たらワーカーのみECSタスク化で対応可能
