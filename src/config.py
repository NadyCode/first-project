"""
アプリケーション設定モジュール
共有フォルダのパスやファイル名等の定数を管理する。
ローカル設定ファイル（local_settings.json）で共有フォルダパスを管理する。
"""

import json
import os
import sys


def get_app_dir() -> str:
    """アプリケーションの実行ディレクトリを返す。"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


APP_DIR = get_app_dir()

# ローカル設定ファイル（exe と同じ階層に配置）
LOCAL_SETTINGS_FILE = os.path.join(APP_DIR, "local_settings.json")


def load_local_settings() -> dict:
    """ローカル設定を読み込む。"""
    if os.path.exists(LOCAL_SETTINGS_FILE):
        with open(LOCAL_SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_local_settings(settings: dict) -> None:
    """ローカル設定を保存する。"""
    with open(LOCAL_SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)


def get_data_dir() -> str:
    """共有データフォルダのパスを返す。
    優先順位: 環境変数 > local_settings.json > exe同階層/data
    """
    env = os.environ.get("HOSPITAL_SURVEY_DATA")
    if env and os.path.isdir(env):
        return env

    settings = load_local_settings()
    saved = settings.get("shared_data_dir", "")
    if saved and os.path.isdir(saved):
        return saved

    return os.path.join(APP_DIR, "data")


# 共有データフォルダ（起動時に解決）
DATA_DIR = get_data_dir()

# 各データファイルのパス
MASTER_USER_FILE = os.path.join(DATA_DIR, "master_user.csv")
SURVEY_CONFIG_FILE = os.path.join(DATA_DIR, "survey_config.json")
ANSWERS_FILE = os.path.join(DATA_DIR, "answers.csv")
ACCESS_LOG_FILE = os.path.join(DATA_DIR, "access_log.txt")

# ロックファイル用タイムアウト（秒）- ネットワーク環境を考慮し長めに設定
LOCK_TIMEOUT = 30
LOCK_RETRY_INTERVAL = 0.3

# アプリケーション情報
APP_TITLE = "病院アンケートシステム"
APP_VERSION = "1.1.0"


def reload_paths() -> None:
    """共有フォルダパスの変更を反映する。"""
    global DATA_DIR, MASTER_USER_FILE, SURVEY_CONFIG_FILE, ANSWERS_FILE, ACCESS_LOG_FILE
    DATA_DIR = get_data_dir()
    MASTER_USER_FILE = os.path.join(DATA_DIR, "master_user.csv")
    SURVEY_CONFIG_FILE = os.path.join(DATA_DIR, "survey_config.json")
    ANSWERS_FILE = os.path.join(DATA_DIR, "answers.csv")
    ACCESS_LOG_FILE = os.path.join(DATA_DIR, "access_log.txt")
