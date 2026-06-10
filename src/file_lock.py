"""
ファイルロック機構モジュール
複数端末から同時にファイルへ書き込む際のデータ破損を防ぐ。
ネットワーク共有フォルダ上での排他制御に対応。
"""

import os
import socket
import time

from src.config import LOCK_RETRY_INTERVAL, LOCK_TIMEOUT


class FileLock:
    """ロックファイルを用いた排他制御。コンテキストマネージャ対応。
    ネットワーク共有フォルダ上でも安全に動作するよう設計。
    """

    def __init__(self, target_path: str, timeout: float = LOCK_TIMEOUT):
        self.lock_path = target_path + ".lock"
        self.timeout = timeout
        self._fd = None

    def _lock_info(self) -> str:
        """ロックファイルに書き込む識別情報を生成する。"""
        pid = os.getpid()
        host = socket.gethostname()
        return f"{host}:{pid}:{time.time()}"

    def _is_stale(self) -> bool:
        """既存のロックが失効（stale）しているか判定する。"""
        try:
            with open(self.lock_path, "r") as f:
                content = f.read().strip()
            parts = content.split(":")
            if len(parts) >= 3:
                lock_time = float(parts[2])
                # ロック取得から2倍のタイムアウト時間が経過していたらstaleとみなす
                if time.time() - lock_time > self.timeout * 2:
                    return True
            return False
        except (OSError, ValueError):
            return True

    def acquire(self) -> None:
        start = time.time()
        while True:
            try:
                self._fd = os.open(
                    self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY
                )
                os.write(self._fd, self._lock_info().encode())
                return
            except FileExistsError:
                if time.time() - start > self.timeout:
                    if self._is_stale():
                        try:
                            os.remove(self.lock_path)
                        except OSError:
                            pass
                        start = time.time()
                        continue
                    raise TimeoutError(
                        f"ファイルロックの取得がタイムアウトしました: {self.lock_path}"
                    )
                time.sleep(LOCK_RETRY_INTERVAL)
            except OSError:
                # ネットワーク一時エラー時はリトライ
                if time.time() - start > self.timeout:
                    raise
                time.sleep(LOCK_RETRY_INTERVAL * 2)

    def release(self) -> None:
        if self._fd is not None:
            try:
                os.close(self._fd)
            except OSError:
                pass
            self._fd = None
        for _ in range(3):
            try:
                os.remove(self.lock_path)
                break
            except FileNotFoundError:
                break
            except OSError:
                time.sleep(0.1)

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
        return False
