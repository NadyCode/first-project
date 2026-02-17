"""
操作ログ収集モジュール
アプリ起動時に日時・端末名・IPアドレスを取得し、ログファイルに追記する。
"""

import socket
from datetime import datetime

from src.config import ACCESS_LOG_FILE
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


def write_access_log() -> None:
    """起動ログをアクセスログファイルに追記する。"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    terminal = get_terminal_name()
    ip = get_ip_address()
    line = f"{now}\t{terminal}\t{ip}\tアプリ起動\n"

    with FileLock(ACCESS_LOG_FILE):
        with open(ACCESS_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line)


def write_action_log(action: str) -> None:
    """任意のアクションをログに記録する。"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    terminal = get_terminal_name()
    ip = get_ip_address()
    line = f"{now}\t{terminal}\t{ip}\t{action}\n"

    with FileLock(ACCESS_LOG_FILE):
        with open(ACCESS_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line)
