"""
アプリケーション設定モジュール
共有フォルダのパスやファイル名等の定数・パス解決関数を管理する。
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
        try:
            with open(LOCAL_SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return {}
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


# 共有データフォルダ（起動時に解決、reload_paths/set_data_dir で更新）
DATA_DIR = get_data_dir()


def set_data_dir(path: str) -> None:
    """共有データフォルダを変更し、ローカル設定に保存する。"""
    global DATA_DIR
    DATA_DIR = path
    settings = load_local_settings()
    settings["shared_data_dir"] = path
    save_local_settings(settings)


def reload_paths() -> None:
    """共有フォルダパスの変更を反映する。"""
    global DATA_DIR
    DATA_DIR = get_data_dir()


# ---------------------------------------------------------------------------
# パス解決関数（DATA_DIR を起点に都度算出。reload 後も最新を返す）
# ---------------------------------------------------------------------------

def master_user_path() -> str:
    return os.path.join(DATA_DIR, "master_user.csv")


def access_log_path() -> str:
    return os.path.join(DATA_DIR, "access_log.txt")


def app_config_path() -> str:
    return os.path.join(DATA_DIR, "app_config.json")


def version_file_path() -> str:
    return os.path.join(DATA_DIR, "version.json")


def surveys_dir() -> str:
    return os.path.join(DATA_DIR, "surveys")


def survey_dir(survey_id: str) -> str:
    return os.path.join(surveys_dir(), survey_id)


def survey_config_path(survey_id: str) -> str:
    return os.path.join(survey_dir(survey_id), "config.json")


def survey_answers_path(survey_id: str) -> str:
    return os.path.join(survey_dir(survey_id), "answers.csv")


def survey_backup_dir(survey_id: str) -> str:
    return os.path.join(survey_dir(survey_id), "backups")


def legacy_survey_config_path() -> str:
    return os.path.join(DATA_DIR, "survey_config.json")


def legacy_answers_path() -> str:
    return os.path.join(DATA_DIR, "answers.csv")


def updates_dir() -> str:
    return os.path.join(DATA_DIR, "updates")


# ロックファイル用タイムアウト（秒）- ネットワーク環境を考慮し長めに設定
LOCK_TIMEOUT = 30
LOCK_RETRY_INTERVAL = 0.3

# アプリケーション情報
APP_TITLE = "病院アンケートシステム"
APP_VERSION = "1.3.0"
