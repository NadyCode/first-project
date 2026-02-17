"""
ファイルロック機構モジュール
複数端末から同時にファイルへ書き込む際のデータ破損を防ぐ。
ロックファイル（.lock）を用いた簡易排他制御を実装する。
"""

import os
import time

from src.config import LOCK_TIMEOUT, LOCK_RETRY_INTERVAL


class FileLock:
    """ロックファイルを用いた簡易排他制御。コンテキストマネージャ対応。"""

    def __init__(self, target_path: str, timeout: float = LOCK_TIMEOUT):
        self.lock_path = target_path + ".lock"
        self.timeout = timeout
        self._fd = None

    def acquire(self) -> None:
        start = time.time()
        while True:
            try:
                self._fd = os.open(
                    self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY
                )
                # ロックファイルにPIDを書き込む
                os.write(self._fd, str(os.getpid()).encode())
                return
            except FileExistsError:
                if time.time() - start > self.timeout:
                    # タイムアウト時はstaleロックとみなして強制削除
                    try:
                        os.remove(self.lock_path)
                    except OSError:
                        pass
                    continue
                time.sleep(LOCK_RETRY_INTERVAL)

    def release(self) -> None:
        if self._fd is not None:
            try:
                os.close(self._fd)
            except OSError:
                pass
            self._fd = None
        try:
            os.remove(self.lock_path)
        except OSError:
            pass

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
        return False
