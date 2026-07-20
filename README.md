# Movie Cut

動画を目標ファイルサイズに圧縮するWebツール。GIFのリサイズ・圧縮にも対応。

- 動画圧縮: FFmpeg 2-passエンコードで目標サイズ(MB)に圧縮
- GIFリサイズ: palettegen + paletteuse で高画質を保ったまま縮小
- GIF圧縮: 解像度・色数・fpsを段階的に下げて目標サイズ以下へ自動調整

## 本番（AWS serverless）

https://d34kvdm47i1n8p.cloudfront.net

```
ブラウザ ── CloudFront ─┬─ S3 (React UI)
                        └─ /api/* → API Gateway + Lambda ── DynamoDB
ブラウザ ←→ S3 (presigned POST/GET, 1GB上限, 24hで自動削除)
                └─ S3イベント → Lambda (FFmpeg Layer, 2-pass encode)
```

デプロイ:

```bash
./aws/deploy.sh   # sam build/deploy + フロントビルド/sync + CF invalidation
```

## ローカル起動（Streamlit版）

```bash
pip install -r requirements.txt
streamlit run app.py
```

FFmpegが必要です（`brew install ffmpeg` / `apt install ffmpeg`）。
