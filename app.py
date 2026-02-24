"""動画圧縮ツール - Streamlit UI"""
from __future__ import annotations

import os

import streamlit as st

from compressor.bitrate_calculator import calculate_bitrate
from compressor.encoder import encode_video
from compressor.ffprobe import get_video_metadata
from config import AUDIO_BITRATE_PRESETS, RESOLUTION_PRESETS
from utils.file_manager import cleanup_file, get_output_path, save_uploaded_file

st.set_page_config(page_title="Movie Cut", page_icon="🎬", layout="wide")
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
            st.session_state["compress_done"] = False
            st.session_state["output_path"] = None
            st.session_state["metadata"] = None
            st.rerun()
    else:
        st.error("出力ファイルが見つかりません")

else:
    if st.button("圧縮開始", type="primary", disabled=not bitrate_result.is_feasible):
        output_path = get_output_path(uploaded_file.name)

        progress_bar = st.progress(0.0)
        status_text = st.empty()

        def update_progress(p: float):
            progress_bar.progress(p)
            if p < 0.5:
                status_text.caption(f"Pass 1/2 - 解析中... ({p * 200:.0f}%)")
            else:
                status_text.caption(f"Pass 2/2 - エンコード中... ({(p - 0.5) * 200:.0f}%)")

        try:
            status_text.caption("Pass 1/2 - 解析中... (0%)")
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
            status_text.caption("完了!")
            st.session_state["compress_done"] = True
            st.session_state["output_path"] = output_path
            st.rerun()
        except Exception as e:
            st.error(f"圧縮中にエラーが発生しました: {e}")
