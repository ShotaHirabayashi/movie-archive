"""一時ファイル管理モジュール"""
from __future__ import annotations

import os
import tempfile

import streamlit as st

from config import CHUNK_SIZE


def save_uploaded_file(uploaded_file) -> str:
    """アップロードファイルをチャンク書き込みでディスクに保存する

    st.session_stateでパスをキャッシュし、Streamlitリラン時の再保存を防止する。
    """
    cache_key = f"uploaded_path_{uploaded_file.name}"

    if cache_key in st.session_state and os.path.exists(st.session_state[cache_key]):
        return st.session_state[cache_key]

    suffix = os.path.splitext(uploaded_file.name)[1]
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix, prefix="movie_archive_")
    tmp_path = tmp.name

    uploaded_file.seek(0)
    while True:
        chunk = uploaded_file.read(CHUNK_SIZE)
        if not chunk:
            break
        tmp.write(chunk)
    tmp.close()

    st.session_state[cache_key] = tmp_path
    return tmp_path


def get_output_path(input_filename: str) -> str:
    """圧縮出力用の一時ファイルパスを生成する"""
    name, _ = os.path.splitext(input_filename)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4", prefix=f"{name}_compressed_")
    tmp.close()
    return tmp.name


def cleanup_file(path: str) -> None:
    """一時ファイルを安全に削除する"""
    if path and os.path.exists(path):
        os.remove(path)


def cleanup_session_files() -> None:
    """session_stateに保存された一時ファイルをすべて削除する"""
    keys_to_remove = []
    for key, value in st.session_state.items():
        if key.startswith("uploaded_path_") and isinstance(value, str):
            cleanup_file(value)
            keys_to_remove.append(key)

    for key in keys_to_remove:
        del st.session_state[key]

    if "output_path" in st.session_state:
        cleanup_file(st.session_state["output_path"])
        del st.session_state["output_path"]
