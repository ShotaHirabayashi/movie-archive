"""動画圧縮・GIFリサイズツール - Streamlit UI"""
from __future__ import annotations

import os
import shutil
import traceback

import streamlit as st

from compressor.bitrate_calculator import calculate_bitrate
from compressor.encoder import encode_video
from compressor.ffprobe import get_video_metadata
from compressor.gif_resizer import compress_gif, resize_gif
from config import (
    AUDIO_BITRATE_PRESETS,
    GIF_FPS_PRESETS,
    GIF_WIDTH_PRESETS,
    RESOLUTION_PRESETS,
)
from utils.file_manager import cleanup_file, get_output_path, save_uploaded_file

st.set_page_config(page_title="Movie Cut", page_icon="🎬", layout="wide")

if not shutil.which("ffmpeg"):
    st.error("FFmpegがインストールされていません。packages.txt を確認してください。")
    st.stop()


def render_video_compressor() -> None:
    st.title("Movie Cut")
    st.caption("動画を目標サイズに圧縮するツール")

    # --- セッション状態の初期化 ---
    for key, default in [
        ("compress_done", False),
        ("output_path", None),
        ("metadata", None),
    ]:
        if key not in st.session_state:
            st.session_state[key] = default

    # === セクションA: ファイルアップロード ===
    uploaded_file = st.file_uploader(
        "動画ファイルをアップロード",
        type=["mp4", "avi", "mov", "mkv", "webm", "flv", "wmv"],
    )

    if uploaded_file is None:
        st.info("動画ファイルをアップロードしてください（最大300MB）")
        st.stop()

    # ディスクに保存 & メタデータ取得（キャッシュ）
    input_path = save_uploaded_file(uploaded_file)

    if st.session_state["metadata"] is None:
        try:
            st.session_state["metadata"] = get_video_metadata(input_path)
        except Exception as e:
            st.error(f"動画の解析に失敗しました: {e}")
            st.stop()

    metadata = st.session_state["metadata"]

    # メタデータ表示
    col1, col2 = st.columns([1, 1])
    with col1:
        st.subheader("動画情報")
        st.markdown(f"""
| 項目 | 値 |
|------|------|
| ファイルサイズ | **{metadata.file_size_mb:.1f} MB** |
| 再生時間 | {metadata.duration_str} |
| 解像度 | {metadata.resolution_label} |
| 映像コーデック | {metadata.video_codec} |
| 映像ビットレート | {metadata.total_bitrate_kbps:.0f} kbps |
| 音声 | {"あり (" + metadata.audio_codec + ")" if metadata.has_audio else "なし"} |
""")

    with col2:
        st.subheader("プレビュー")
        st.video(input_path)

    st.divider()

    # === セクションB: 圧縮設定 ===
    st.subheader("圧縮設定")

    col_a, col_b, col_c = st.columns(3)

    with col_a:
        target_size_mb = st.number_input(
            "目標ファイルサイズ (MB)",
            min_value=1.0,
            max_value=metadata.file_size_mb,
            value=min(metadata.file_size_mb * 0.4, metadata.file_size_mb),
            step=1.0,
            format="%.1f",
        )

    with col_b:
        resolution_label = st.selectbox(
            "解像度",
            options=list(RESOLUTION_PRESETS.keys()),
        )
        resolution = RESOLUTION_PRESETS[resolution_label]

    with col_c:
        audio_label = st.selectbox(
            "音声品質",
            options=list(AUDIO_BITRATE_PRESETS.keys()),
            index=2,  # 128kbps
            disabled=not metadata.has_audio,
        )
        audio_bitrate_kbps = AUDIO_BITRATE_PRESETS[audio_label]

    # ビットレート計算
    bitrate_result = calculate_bitrate(
        target_size_mb=target_size_mb,
        duration_seconds=metadata.duration,
        audio_bitrate_kbps=audio_bitrate_kbps,
        has_audio=metadata.has_audio,
    )

    # ビットレート情報表示
    col_info1, col_info2, col_info3 = st.columns(3)
    col_info1.metric("映像ビットレート", f"{bitrate_result.video_bitrate_kbps:.0f} kbps")
    col_info2.metric("音声ビットレート", f"{bitrate_result.audio_bitrate_kbps:.0f} kbps")
    col_info3.metric("圧縮率", f"{target_size_mb / metadata.file_size_mb * 100:.0f}%")

    if bitrate_result.warning:
        st.warning(bitrate_result.warning)

    st.divider()

    # === セクションC / D: 圧縮実行 & 結果 ===

    if st.session_state["compress_done"] and st.session_state["output_path"]:
        output_path = st.session_state["output_path"]
        if os.path.exists(output_path):
            output_size = os.path.getsize(output_path)
            output_size_mb = output_size / (1024 * 1024)

            st.subheader("圧縮完了")

            col_r1, col_r2, col_r3 = st.columns(3)
            col_r1.metric("元のサイズ", f"{metadata.file_size_mb:.1f} MB")
            col_r2.metric("圧縮後サイズ", f"{output_size_mb:.1f} MB")
            col_r3.metric("削減率", f"{(1 - output_size_mb / metadata.file_size_mb) * 100:.1f}%")

            if output_size_mb > target_size_mb * 1.1:
                st.warning(f"出力サイズが目標 ({target_size_mb:.1f} MB) を超えています")
            else:
                st.success(f"目標サイズ ({target_size_mb:.1f} MB) 以内に圧縮できました")

            st.video(output_path)

            with open(output_path, "rb") as f:
                compressed_name = os.path.splitext(uploaded_file.name)[0] + "_compressed.mp4"
                st.download_button(
                    label="圧縮済みファイルをダウンロード",
                    data=f,
                    file_name=compressed_name,
                    mime="video/mp4",
                )

            if st.button("最初からやり直す"):
                cleanup_file(output_path)
                cleanup_file(input_path)
                st.session_state["compress_done"] = False
                st.session_state["output_path"] = None
                st.session_state["metadata"] = None
                for k in list(st.session_state.keys()):
                    if k.startswith("uploaded_path_"):
                        del st.session_state[k]
                st.rerun()
        else:
            st.error("出力ファイルが見つかりません")

    else:
        if st.button("圧縮開始", type="primary", disabled=not bitrate_result.is_feasible):
            output_path = get_output_path(uploaded_file.name)

            step_text = st.empty()
            progress_bar = st.progress(0.0)
            detail_text = st.empty()

            def update_progress(p: float):
                if p < 0.5:
                    pct = int(p * 200)
                    step_text.markdown("**Step 1/2** - 解析中")
                    progress_bar.progress(p * 2)
                    detail_text.caption(f"{pct}%")
                else:
                    pct = int((p - 0.5) * 200)
                    step_text.markdown("**Step 2/2** - エンコード中")
                    progress_bar.progress((p - 0.5) * 2)
                    detail_text.caption(f"{pct}%")

            try:
                step_text.markdown("**Step 1/2** - 解析中")
                detail_text.caption("0%")
                encode_video(
                    input_path=input_path,
                    output_path=output_path,
                    video_bitrate_kbps=bitrate_result.video_bitrate_kbps,
                    audio_bitrate_kbps=bitrate_result.audio_bitrate_kbps,
                    has_audio=metadata.has_audio,
                    duration_seconds=metadata.duration,
                    resolution=resolution,
                    progress_callback=update_progress,
                )
                progress_bar.progress(1.0)
                step_text.markdown("**完了!**")
                detail_text.caption("100%")
                st.session_state["compress_done"] = True
                st.session_state["output_path"] = output_path
                st.rerun()
            except Exception as e:
                st.error(f"圧縮中にエラーが発生しました: {e}")
                st.code(traceback.format_exc())


def render_gif_resizer() -> None:
    st.title("GIF Resize")
    st.caption("GIFをリサイズして軽量化するツール")

    # --- セッション状態の初期化 ---
    for key, default in [
        ("gif_done", False),
        ("gif_output_path", None),
        ("gif_metadata", None),
    ]:
        if key not in st.session_state:
            st.session_state[key] = default

    # === セクションA: ファイルアップロード ===
    uploaded_file = st.file_uploader(
        "GIFファイルをアップロード",
        type=["gif"],
    )

    if uploaded_file is None:
        st.info("GIFファイルをアップロードしてください（最大300MB）")
        st.stop()

    # ディスクに保存 & メタデータ取得（キャッシュ）
    input_path = save_uploaded_file(uploaded_file)

    if st.session_state["gif_metadata"] is None:
        try:
            st.session_state["gif_metadata"] = get_video_metadata(input_path)
        except Exception as e:
            st.error(f"GIFの解析に失敗しました: {e}")
            st.stop()

    metadata = st.session_state["gif_metadata"]

    # メタデータ表示
    col1, col2 = st.columns([1, 1])
    with col1:
        st.subheader("GIF情報")
        fps_str = f"{metadata.fps:.1f} fps" if metadata.fps else "不明"
        st.markdown(f"""
| 項目 | 値 |
|------|------|
| ファイルサイズ | **{metadata.file_size_mb:.1f} MB** |
| 再生時間 | {metadata.duration:.1f} 秒 |
| 解像度 | {metadata.resolution_label} |
| フレームレート | {fps_str} |
""")

    with col2:
        st.subheader("プレビュー")
        st.image(input_path)

    st.divider()

    # === セクションB: リサイズ設定 ===
    st.subheader("リサイズ設定")

    col_a, col_b = st.columns(2)

    with col_a:
        width_label = st.selectbox(
            "幅（縦横比は維持）",
            options=list(GIF_WIDTH_PRESETS.keys()),
            index=2,  # 640px
        )
        width = GIF_WIDTH_PRESETS[width_label]

    with col_b:
        fps_label = st.selectbox(
            "フレームレート",
            options=list(GIF_FPS_PRESETS.keys()),
        )
        fps = GIF_FPS_PRESETS[fps_label]

    if width is not None and width >= metadata.width:
        st.info("指定した幅が元のサイズ以上のため、解像度は変更されません（アップスケールは行いません）")

    st.divider()

    # === セクションC / D: リサイズ実行 & 結果 ===

    if st.session_state["gif_done"] and st.session_state["gif_output_path"]:
        output_path = st.session_state["gif_output_path"]
        if os.path.exists(output_path):
            output_size = os.path.getsize(output_path)
            output_size_mb = output_size / (1024 * 1024)

            st.subheader("リサイズ完了")

            col_r1, col_r2, col_r3 = st.columns(3)
            col_r1.metric("元のサイズ", f"{metadata.file_size_mb:.1f} MB")
            col_r2.metric("リサイズ後サイズ", f"{output_size_mb:.1f} MB")
            col_r3.metric("削減率", f"{(1 - output_size_mb / metadata.file_size_mb) * 100:.1f}%")

            st.image(output_path)

            with open(output_path, "rb") as f:
                resized_name = os.path.splitext(uploaded_file.name)[0] + "_resized.gif"
                st.download_button(
                    label="リサイズ済みGIFをダウンロード",
                    data=f,
                    file_name=resized_name,
                    mime="image/gif",
                )

            if st.button("最初からやり直す"):
                cleanup_file(output_path)
                cleanup_file(input_path)
                st.session_state["gif_done"] = False
                st.session_state["gif_output_path"] = None
                st.session_state["gif_metadata"] = None
                for k in list(st.session_state.keys()):
                    if k.startswith("uploaded_path_"):
                        del st.session_state[k]
                st.rerun()
        else:
            st.error("出力ファイルが見つかりません")

    else:
        if st.button("リサイズ開始", type="primary"):
            output_path = get_output_path(uploaded_file.name, suffix=".gif")

            step_text = st.empty()
            progress_bar = st.progress(0.0)
            detail_text = st.empty()

            def update_progress(p: float):
                if p < 0.5:
                    pct = int(p * 200)
                    step_text.markdown("**Step 1/2** - パレット生成中")
                    progress_bar.progress(p * 2)
                    detail_text.caption(f"{pct}%")
                else:
                    pct = int((p - 0.5) * 200)
                    step_text.markdown("**Step 2/2** - GIF生成中")
                    progress_bar.progress((p - 0.5) * 2)
                    detail_text.caption(f"{pct}%")

            try:
                step_text.markdown("**Step 1/2** - パレット生成中")
                detail_text.caption("0%")
                resize_gif(
                    input_path=input_path,
                    output_path=output_path,
                    duration_seconds=metadata.duration,
                    width=width,
                    fps=fps,
                    progress_callback=update_progress,
                )
                progress_bar.progress(1.0)
                step_text.markdown("**完了!**")
                detail_text.caption("100%")
                st.session_state["gif_done"] = True
                st.session_state["gif_output_path"] = output_path
                st.rerun()
            except Exception as e:
                st.error(f"リサイズ中にエラーが発生しました: {e}")
                st.code(traceback.format_exc())


def render_gif_compressor() -> None:
    st.title("GIF Compress")
    st.caption("GIFを目標ファイルサイズに圧縮するツール")

    # --- セッション状態の初期化 ---
    for key, default in [
        ("gifc_done", False),
        ("gifc_output_path", None),
        ("gifc_metadata", None),
    ]:
        if key not in st.session_state:
            st.session_state[key] = default

    # === セクションA: ファイルアップロード ===
    uploaded_file = st.file_uploader(
        "GIFファイルをアップロード",
        type=["gif"],
        key="gifc_uploader",
    )

    if uploaded_file is None:
        st.info("GIFファイルをアップロードしてください（最大300MB）")
        st.stop()

    # ディスクに保存 & メタデータ取得（キャッシュ）
    input_path = save_uploaded_file(uploaded_file)

    if st.session_state["gifc_metadata"] is None:
        try:
            st.session_state["gifc_metadata"] = get_video_metadata(input_path)
        except Exception as e:
            st.error(f"GIFの解析に失敗しました: {e}")
            st.stop()

    metadata = st.session_state["gifc_metadata"]

    # メタデータ表示
    col1, col2 = st.columns([1, 1])
    with col1:
        st.subheader("GIF情報")
        fps_str = f"{metadata.fps:.1f} fps" if metadata.fps else "不明"
        st.markdown(f"""
| 項目 | 値 |
|------|------|
| ファイルサイズ | **{metadata.file_size_mb:.1f} MB** |
| 再生時間 | {metadata.duration:.1f} 秒 |
| 解像度 | {metadata.resolution_label} |
| フレームレート | {fps_str} |
""")

    with col2:
        st.subheader("プレビュー")
        st.image(input_path)

    st.divider()

    # === セクションB: 圧縮設定 ===
    st.subheader("圧縮設定")

    target_size_mb = st.number_input(
        "目標ファイルサイズ (MB)",
        min_value=0.1,
        max_value=metadata.file_size_mb,
        value=max(metadata.file_size_mb * 0.5, 0.1),
        step=0.1,
        format="%.1f",
    )

    st.caption(
        "解像度・色数・フレームレートを自動調整しながら、目標サイズ以下になるまで最大5回試行します。"
        "圧縮率が高いほど画質・滑らかさは低下します。"
    )

    st.divider()

    # === セクションC / D: 圧縮実行 & 結果 ===

    if st.session_state["gifc_done"] and st.session_state["gifc_output_path"]:
        output_path = st.session_state["gifc_output_path"]
        if os.path.exists(output_path):
            output_size = os.path.getsize(output_path)
            output_size_mb = output_size / (1024 * 1024)

            st.subheader("圧縮完了")

            col_r1, col_r2, col_r3 = st.columns(3)
            col_r1.metric("元のサイズ", f"{metadata.file_size_mb:.1f} MB")
            col_r2.metric("圧縮後サイズ", f"{output_size_mb:.2f} MB")
            col_r3.metric("削減率", f"{(1 - output_size_mb / metadata.file_size_mb) * 100:.1f}%")

            if output_size_mb > target_size_mb:
                st.warning(f"出力サイズが目標 ({target_size_mb:.1f} MB) を超えています。目標サイズをさらに小さくできない場合があります")
            else:
                st.success(f"目標サイズ ({target_size_mb:.1f} MB) 以内に圧縮できました")

            st.image(output_path)

            with open(output_path, "rb") as f:
                compressed_name = os.path.splitext(uploaded_file.name)[0] + "_compressed.gif"
                st.download_button(
                    label="圧縮済みGIFをダウンロード",
                    data=f,
                    file_name=compressed_name,
                    mime="image/gif",
                )

            if st.button("最初からやり直す"):
                cleanup_file(output_path)
                cleanup_file(input_path)
                st.session_state["gifc_done"] = False
                st.session_state["gifc_output_path"] = None
                st.session_state["gifc_metadata"] = None
                for k in list(st.session_state.keys()):
                    if k.startswith("uploaded_path_"):
                        del st.session_state[k]
                st.rerun()
        else:
            st.error("出力ファイルが見つかりません")

    else:
        if st.button("圧縮開始", type="primary"):
            output_path = get_output_path(uploaded_file.name, suffix=".gif")

            attempt_text = st.empty()
            step_text = st.empty()
            progress_bar = st.progress(0.0)
            detail_text = st.empty()

            def on_attempt(n: int, total: int):
                attempt_text.markdown(f"**試行 {n}/{total} 回目**")

            def update_progress(p: float):
                if p < 0.5:
                    pct = int(p * 200)
                    step_text.markdown("**Step 1/2** - パレット生成中")
                    progress_bar.progress(p * 2)
                    detail_text.caption(f"{pct}%")
                else:
                    pct = int((p - 0.5) * 200)
                    step_text.markdown("**Step 2/2** - GIF生成中")
                    progress_bar.progress((p - 0.5) * 2)
                    detail_text.caption(f"{pct}%")

            try:
                step_text.markdown("**Step 1/2** - パレット生成中")
                detail_text.caption("0%")
                compress_gif(
                    input_path=input_path,
                    output_path=output_path,
                    target_size_mb=target_size_mb,
                    duration_seconds=metadata.duration,
                    original_width=metadata.width,
                    original_fps=metadata.fps,
                    progress_callback=update_progress,
                    attempt_callback=on_attempt,
                )
                progress_bar.progress(1.0)
                attempt_text.empty()
                step_text.markdown("**完了!**")
                detail_text.caption("100%")
                st.session_state["gifc_done"] = True
                st.session_state["gifc_output_path"] = output_path
                st.rerun()
            except Exception as e:
                st.error(f"圧縮中にエラーが発生しました: {e}")
                st.code(traceback.format_exc())


# === メニュー ===
mode = st.sidebar.radio("メニュー", ["動画圧縮", "GIFリサイズ", "GIF圧縮"])

if mode == "動画圧縮":
    render_video_compressor()
elif mode == "GIFリサイズ":
    render_gif_resizer()
else:
    render_gif_compressor()
