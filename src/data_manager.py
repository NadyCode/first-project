"""
データ管理モジュール
CSV/JSONファイルの読み書き、職員マスターデータの管理を行う。
"""

import csv
import hashlib
import json
import os
from datetime import datetime
from typing import Any

from src.config import ANSWERS_FILE, MASTER_USER_FILE, SURVEY_CONFIG_FILE
from src.file_lock import FileLock


# ---------------------------------------------------------------------------
# 職員マスターデータ
# ---------------------------------------------------------------------------

def load_master_users(path: str = MASTER_USER_FILE) -> dict[str, list[str]]:
    """master_user.csv を読み込み、{部署: [氏名, ...]} の辞書を返す。"""
    departments: dict[str, list[str]] = {}
    if not os.path.exists(path):
        return departments
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            dept = row.get("department", "").strip()
            name = row.get("name", "").strip()
            if dept and name:
                departments.setdefault(dept, []).append(name)
    return departments


def get_all_staff(path: str = MASTER_USER_FILE) -> list[tuple[str, str]]:
    """全職員を (部署, 氏名) のリストで返す。"""
    staff: list[tuple[str, str]] = []
    if not os.path.exists(path):
        return staff
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            dept = row.get("department", "").strip()
            name = row.get("name", "").strip()
            if dept and name:
                staff.append((dept, name))
    return staff


def save_master_users(
    departments: dict[str, list[str]], path: str = MASTER_USER_FILE
) -> None:
    """部署-氏名辞書を master_user.csv に保存する。"""
    with FileLock(path):
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["department", "name"])
            for dept, names in departments.items():
                for name in names:
                    writer.writerow([dept, name])


# ---------------------------------------------------------------------------
# アンケート設定
# ---------------------------------------------------------------------------

def load_survey_config(path: str = SURVEY_CONFIG_FILE) -> dict[str, Any]:
    """survey_config.json を読み込む。"""
    if not os.path.exists(path):
        return {
            "title": "",
            "description": "",
            "created_at": "",
            "admin_password_hash": "",
            "questions": [],
            "reference_files": [],
        }
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_survey_config(
    config: dict[str, Any], path: str = SURVEY_CONFIG_FILE
) -> None:
    """survey_config.json に保存する。"""
    with FileLock(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# 回答データ
# ---------------------------------------------------------------------------

def save_answer(
    department: str,
    name: str,
    answers: dict[int, str],
    path: str = ANSWERS_FILE,
) -> None:
    """回答を answers.csv に追記する。"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    file_exists = os.path.exists(path)

    # 設問IDの最大値を取得して列数を確定
    max_q = max(answers.keys()) if answers else 0

    with FileLock(path):
        with open(path, "a", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            if not file_exists or os.path.getsize(path) == 0:
                header = ["timestamp", "department", "name"]
                header += [f"q{i}" for i in range(1, max_q + 1)]
                writer.writerow(header)
            row = [now, department, name]
            row += [answers.get(i, "") for i in range(1, max_q + 1)]
            writer.writerow(row)


def load_answers(path: str = ANSWERS_FILE) -> list[dict[str, str]]:
    """answers.csv から全回答を読み込む。"""
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return list(reader)


def get_respondents(path: str = ANSWERS_FILE) -> set[tuple[str, str]]:
    """回答済みの (部署, 氏名) のセットを返す。"""
    respondents: set[tuple[str, str]] = set()
    rows = load_answers(path)
    for row in rows:
        dept = row.get("department", "").strip()
        name = row.get("name", "").strip()
        if dept and name:
            respondents.add((dept, name))
    return respondents


# ---------------------------------------------------------------------------
# パスワード管理
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    """パスワードをSHA-256でハッシュ化する。"""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def verify_password(password: str, hashed: str) -> bool:
    """パスワードを検証する。"""
    if not hashed:
        return True  # パスワード未設定の場合は常にTrue
    return hash_password(password) == hashed
