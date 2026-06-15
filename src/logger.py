"""
操作ログ収集モジュール
アプリ起動時に日時・端末名・IPアドレスを取得し、ログファイルに追記する。
"""

import os
import socket
from datetime import datetime

import src.config as config
from src.file_lock import FileLock


def get_terminal_name() -> str:
    """端末名（ホスト名）を取得する。"""
    try:
        return socket.gethostname()
    except Exception:
        return "unknown"


def get_ip_address() -> str:
    """ローカルIPアドレスを取得する。"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.1)
        # LAN内のダミーアドレスへ接続してローカルIPを判定
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def _append_log(action: str) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    terminal = get_terminal_name()
    ip = get_ip_address()
    line = f"{now}\t{terminal}\t{ip}\t{action}\n"

    path = config.access_log_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with FileLock(path):
        with open(path, "a", encoding="utf-8") as f:
            f.write(line)


def write_access_log() -> None:
    """起動ログをアクセスログファイルに追記する。"""
    _append_log("アプリ起動")


def write_action_log(action: str) -> None:
    """任意のアクションをログに記録する。"""
    _append_log(action)
