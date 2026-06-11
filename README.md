---
title: Movie Cut
emoji: 🎬
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# Movie Cut

動画を目標ファイルサイズに圧縮するWebツール。GIFのリサイズにも対応（サイドバーメニューで切り替え）。

- 動画圧縮: FFmpeg 2-passエンコードで目標サイズ(MB)に圧縮
- GIFリサイズ: palettegen + paletteuse で高画質を保ったまま縮小・軽量化

## ローカル起動

```bash
pip install -r requirements.txt
streamlit run app.py
```

FFmpegが必要です（`brew install ffmpeg` / `apt install ffmpeg`）。
