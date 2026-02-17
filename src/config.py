"""
アプリケーション設定モジュール
共有フォルダのパスやファイル名等の定数を管理する。
"""

import os
import sys


def get_app_dir() -> str:
    """アプリケーションの実行ディレクトリを返す。"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# デフォルトのデータフォルダパス（共有フォルダとして想定）
DATA_DIR = os.path.join(get_app_dir(), "data")

# 各データファイルのパス
MASTER_USER_FILE = os.path.join(DATA_DIR, "master_user.csv")
SURVEY_CONFIG_FILE = os.path.join(DATA_DIR, "survey_config.json")
ANSWERS_FILE = os.path.join(DATA_DIR, "answers.csv")
ACCESS_LOG_FILE = os.path.join(DATA_DIR, "access_log.txt")

# ロックファイル用タイムアウト（秒）
LOCK_TIMEOUT = 10
LOCK_RETRY_INTERVAL = 0.2

# アプリケーション情報
APP_TITLE = "病院アンケートシステム"
APP_VERSION = "1.0.0"
