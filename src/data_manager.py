"""
データ管理モジュール
CSV/JSONファイルの読み書き、職員マスター・複数アンケート・回答・
アプリ設定・バージョン情報の管理を行う。
"""

import csv
import hashlib
import json
import os
import re
import shutil
from datetime import date, datetime
from typing import Any

import src.config as config
from src.file_lock import FileLock

ANONYMOUS_NAME = "(匿名)"


# ---------------------------------------------------------------------------
# 職員マスターデータ
# ---------------------------------------------------------------------------

def load_master_users(path: str | None = None) -> dict[str, list[str]]:
    """master_user.csv を読み込み、{部署: [氏名, ...]} の辞書を返す。"""
    path = path or config.master_user_path()
    departments: dict[str, list[str]] = {}
    if not os.path.exists(path):
        return departments
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            dept = (row.get("department") or "").strip()
            name = (row.get("name") or "").strip()
            if dept and name:
                departments.setdefault(dept, []).append(name)
    return departments


def get_all_staff(path: str | None = None) -> list[tuple[str, str]]:
    """全職員を (部署, 氏名) のリストで返す。"""
    path = path or config.master_user_path()
    staff: list[tuple[str, str]] = []
    if not os.path.exists(path):
        return staff
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            dept = (row.get("department") or "").strip()
            name = (row.get("name") or "").strip()
            if dept and name:
                staff.append((dept, name))
    return staff


def save_master_users(
    departments: dict[str, list[str]], path: str | None = None
) -> None:
    """部署-氏名辞書を master_user.csv に保存する。"""
    path = path or config.master_user_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with FileLock(path):
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["department", "name"])
            for dept, names in departments.items():
                for name in names:
                    writer.writerow([dept, name])


# ---------------------------------------------------------------------------
# グローバルアプリ設定（管理者パスワード・アクティブアンケート）
# ---------------------------------------------------------------------------

def load_app_config() -> dict[str, Any]:
    """app_config.json を読み込む。"""
    path = config.app_config_path()
    if not os.path.exists(path):
        return {"admin_password_hash": "", "active_survey_id": ""}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"admin_password_hash": "", "active_survey_id": ""}
    data.setdefault("admin_password_hash", "")
    data.setdefault("active_survey_id", "")
    return data


def save_app_config(cfg: dict[str, Any]) -> None:
    """app_config.json に保存する。"""
    path = config.app_config_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with FileLock(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)


def get_admin_password_hash() -> str:
    return load_app_config().get("admin_password_hash", "")


def set_admin_password(password: str) -> None:
    cfg = load_app_config()
    cfg["admin_password_hash"] = hash_password(password) if password else ""
    save_app_config(cfg)


def get_active_survey_id() -> str:
    return load_app_config().get("active_survey_id", "")


def set_active_survey_id(survey_id: str) -> None:
    cfg = load_app_config()
    cfg["active_survey_id"] = survey_id
    save_app_config(cfg)


# ---------------------------------------------------------------------------
# 複数アンケート管理
# ---------------------------------------------------------------------------

def _default_survey(survey_id: str = "", title: str = "") -> dict[str, Any]:
    return {
        "id": survey_id,
        "title": title,
        "description": "",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "start_date": "",
        "end_date": "",
        "anonymous": False,
        "status": "active",
        "questions": [],
        "reference_files": [],
    }


def _generate_survey_id() -> str:
    return "survey_" + datetime.now().strftime("%Y%m%d_%H%M%S")


def list_surveys(include_archived: bool = True) -> list[dict[str, Any]]:
    """全アンケートの設定を作成日時順で返す。"""
    base = config.surveys_dir()
    if not os.path.isdir(base):
        return []
    surveys: list[dict[str, Any]] = []
    for sid in os.listdir(base):
        cfg_path = config.survey_config_path(sid)
        if not os.path.exists(cfg_path):
            continue
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        cfg["id"] = sid
        cfg.setdefault("status", "active")
        if not include_archived and cfg.get("status") == "archived":
            continue
        surveys.append(cfg)
    surveys.sort(key=lambda c: c.get("created_at", ""))
    return surveys


def list_active_surveys() -> list[dict[str, Any]]:
    """回答可能な（公開中かつ期間内の）アンケート一覧を返す。"""
    return [c for c in list_surveys() if is_survey_open(c)]


def load_survey(survey_id: str) -> dict[str, Any]:
    """指定IDのアンケート設定を読み込む。"""
    path = config.survey_config_path(survey_id)
    if not os.path.exists(path):
        return _default_survey(survey_id)
    with open(path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    cfg["id"] = survey_id
    cfg.setdefault("status", "active")
    cfg.setdefault("anonymous", False)
    cfg.setdefault("start_date", "")
    cfg.setdefault("end_date", "")
    cfg.setdefault("questions", [])
    cfg.setdefault("reference_files", [])
    return cfg


def save_survey(cfg: dict[str, Any]) -> None:
    """アンケート設定を保存する。cfg['id'] を使用する。"""
    survey_id = cfg["id"]
    os.makedirs(config.survey_dir(survey_id), exist_ok=True)
    path = config.survey_config_path(survey_id)
    with FileLock(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)


def create_survey(title: str = "新しいアンケート") -> str:
    """新規アンケートを作成し、IDを返す。"""
    survey_id = _generate_survey_id()
    # 同一秒の重複を避ける
    suffix = 1
    base_id = survey_id
    while os.path.exists(config.survey_dir(survey_id)):
        survey_id = f"{base_id}_{suffix}"
        suffix += 1
    cfg = _default_survey(survey_id, title)
    save_survey(cfg)
    return survey_id


def archive_survey(survey_id: str) -> None:
    cfg = load_survey(survey_id)
    cfg["status"] = "archived"
    save_survey(cfg)


def unarchive_survey(survey_id: str) -> None:
    cfg = load_survey(survey_id)
    cfg["status"] = "active"
    save_survey(cfg)


def delete_survey(survey_id: str) -> None:
    """アンケートを回答データごと完全削除する。"""
    d = config.survey_dir(survey_id)
    if os.path.isdir(d):
        shutil.rmtree(d, ignore_errors=True)


def _parse_date(value: str) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


def is_survey_open(cfg: dict[str, Any], today: date | None = None) -> bool:
    """アンケートが回答可能か（公開中かつ期間内か）を判定する。"""
    if cfg.get("status") != "active":
        return False
    today = today or date.today()
    start = _parse_date(cfg.get("start_date", ""))
    end = _parse_date(cfg.get("end_date", ""))
    if start and today < start:
        return False
    if end and today > end:
        return False
    return True


def survey_open_reason(cfg: dict[str, Any], today: date | None = None) -> str:
    """回答不可の理由を返す。回答可能なら空文字。"""
    if cfg.get("status") != "active":
        return "このアンケートは公開されていません。"
    today = today or date.today()
    start = _parse_date(cfg.get("start_date", ""))
    end = _parse_date(cfg.get("end_date", ""))
    if start and today < start:
        return f"回答受付は {cfg['start_date']} から開始されます。"
    if end and today > end:
        return f"回答受付は {cfg['end_date']} に終了しました。"
    return ""


# ---------------------------------------------------------------------------
# 回答データ（アンケート単位）
# ---------------------------------------------------------------------------

def _read_answer_rows(path: str) -> list[dict[str, str]]:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _answer_fieldnames(rows: list[dict[str, str]]) -> list[str]:
    """回答行から列名（timestamp, department, name, q1, q2, ...）を構築する。"""
    q_ids: set[int] = set()
    for row in rows:
        for key in row:
            m = re.fullmatch(r"q(\d+)", key)
            if m:
                q_ids.add(int(m.group(1)))
    fields = ["timestamp", "department", "name"]
    fields += [f"q{i}" for i in sorted(q_ids)]
    return fields


def save_survey_answer(
    survey_id: str,
    department: str,
    name: str,
    answers: dict[int, str],
    anonymous: bool = False,
) -> None:
    """回答を保存する。匿名でない場合、同一人物の既存回答は置き換える（修正対応）。"""
    path = config.survey_answers_path(survey_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    stored_name = ANONYMOUS_NAME if anonymous else name

    new_row: dict[str, str] = {
        "timestamp": now,
        "department": department,
        "name": stored_name,
    }
    for q_id, val in answers.items():
        new_row[f"q{q_id}"] = val

    with FileLock(path):
        rows = _read_answer_rows(path)
        # 修正: 匿名でなければ同一(部署,氏名)の旧回答を除去
        if not anonymous:
            rows = [
                r
                for r in rows
                if not (
                    (r.get("department") or "").strip() == department
                    and (r.get("name") or "").strip() == name
                )
            ]
        rows.append(new_row)

        fieldnames = _answer_fieldnames(rows)
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for r in rows:
                writer.writerow({k: r.get(k, "") for k in fieldnames})

    # 日次バックアップ（1日1回）
    try:
        backup_survey_answers(survey_id, daily_only=True)
    except OSError:
        pass


def load_survey_answers(survey_id: str) -> list[dict[str, str]]:
    """指定アンケートの全回答を読み込む。"""
    return _read_answer_rows(config.survey_answers_path(survey_id))


def get_survey_respondents(survey_id: str) -> set[tuple[str, str]]:
    """回答済みの (部署, 氏名) のセットを返す。"""
    respondents: set[tuple[str, str]] = set()
    for row in load_survey_answers(survey_id):
        dept = (row.get("department") or "").strip()
        name = (row.get("name") or "").strip()
        if dept and name and name != ANONYMOUS_NAME:
            respondents.add((dept, name))
    return respondents


def backup_survey_answers(survey_id: str, daily_only: bool = False) -> str | None:
    """回答データを backups/ にタイムスタンプ付きでコピーする。
    daily_only=True の場合、当日のバックアップが既にあればスキップ。
    作成したバックアップのパスを返す（スキップ時は None）。
    """
    src = config.survey_answers_path(survey_id)
    if not os.path.exists(src):
        return None
    backup_dir = config.survey_backup_dir(survey_id)
    os.makedirs(backup_dir, exist_ok=True)

    if daily_only:
        today_str = datetime.now().strftime("%Y%m%d")
        for fname in os.listdir(backup_dir):
            if fname.startswith(f"answers_{today_str}"):
                return None

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = os.path.join(backup_dir, f"answers_{ts}.csv")
    shutil.copy2(src, dest)
    return dest


# ---------------------------------------------------------------------------
# 条件分岐の評価
# ---------------------------------------------------------------------------

def question_is_visible(question: dict[str, Any], answers: dict[int, str]) -> bool:
    """条件分岐を考慮し、設問を表示すべきか判定する。
    condition = {"question_id": int, "equals": "値"} の場合、
    対象設問の回答が値と一致するときのみ表示する。
    """
    cond = question.get("condition")
    if not cond or not cond.get("question_id"):
        return True
    target_id = cond["question_id"]
    expected = cond.get("equals", "")
    return answers.get(target_id, "") == expected


# ---------------------------------------------------------------------------
# バージョン情報（更新チェック）
# ---------------------------------------------------------------------------

def load_version_info() -> dict[str, Any]:
    """共有フォルダの version.json を読み込む。"""
    path = config.version_file_path()
    if not os.path.exists(path):
        return {"latest_version": "", "note": "", "exe_filename": ""}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"latest_version": "", "note": "", "exe_filename": ""}
    data.setdefault("latest_version", "")
    data.setdefault("note", "")
    data.setdefault("exe_filename", "")
    return data


def save_version_info(
    latest_version: str, note: str = "", exe_filename: str = ""
) -> None:
    """version.json に最新バージョン情報を書き込む。"""
    path = config.version_file_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with FileLock(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "latest_version": latest_version,
                    "note": note,
                    "exe_filename": exe_filename,
                    "updated_at": datetime.now().isoformat(timespec="seconds"),
                },
                f,
                ensure_ascii=False,
                indent=2,
            )


def get_update_exe_path() -> str | None:
    """共有フォルダの更新用exeパスを返す（存在しなければNone）。"""
    info = load_version_info()
    exe_name = info.get("exe_filename", "")
    if not exe_name:
        return None
    path = os.path.join(config.updates_dir(), exe_name)
    if os.path.isfile(path):
        return path
    return None


def _parse_version(v: str) -> tuple[int, ...]:
    parts = re.findall(r"\d+", v or "")
    return tuple(int(p) for p in parts) if parts else (0,)


def check_version_outdated(current: str | None = None) -> tuple[bool, str, str]:
    """現在のバージョンが最新より古いか判定する。
    戻り値: (古いか, 最新バージョン, 注記)
    """
    current = current or config.APP_VERSION
    info = load_version_info()
    latest = info.get("latest_version", "")
    if not latest:
        return (False, "", "")
    outdated = _parse_version(current) < _parse_version(latest)
    return (outdated, latest, info.get("note", ""))


# ---------------------------------------------------------------------------
# パスワード管理
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    """パスワードをSHA-256でハッシュ化する。"""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def verify_password(password: str, hashed: str) -> bool:
    """パスワードを検証する。未設定(空)なら常にTrue。"""
    if not hashed:
        return True
    return hash_password(password) == hashed


# ---------------------------------------------------------------------------
# データレイアウトの初期化・レガシー移行
# ---------------------------------------------------------------------------

def ensure_data_layout() -> None:
    """データフォルダ構成を初期化し、旧形式(単一アンケート)を移行する。"""
    os.makedirs(config.surveys_dir(), exist_ok=True)

    legacy_cfg = config.legacy_survey_config_path()
    if os.path.exists(legacy_cfg) and not list_surveys():
        _migrate_legacy(legacy_cfg)


def _migrate_legacy(legacy_cfg_path: str) -> None:
    """旧 survey_config.json / answers.csv を surveys/ 配下へ移行する。"""
    try:
        with open(legacy_cfg_path, "r", encoding="utf-8") as f:
            old = json.load(f)
    except (OSError, json.JSONDecodeError):
        return

    # 管理者パスワードはグローバル設定へ移行
    old_pw = old.get("admin_password_hash", "")
    if old_pw:
        app_cfg = load_app_config()
        if not app_cfg.get("admin_password_hash"):
            app_cfg["admin_password_hash"] = old_pw
            save_app_config(app_cfg)

    survey_id = _generate_survey_id()
    cfg = _default_survey(survey_id, old.get("title", "移行されたアンケート"))
    cfg["description"] = old.get("description", "")
    cfg["questions"] = old.get("questions", [])
    cfg["reference_files"] = old.get("reference_files", [])
    save_survey(cfg)

    legacy_answers = config.legacy_answers_path()
    if os.path.exists(legacy_answers):
        try:
            shutil.copy2(legacy_answers, config.survey_answers_path(survey_id))
        except OSError:
            pass

    # 旧設定をリネームして退避（再移行防止）
    try:
        os.rename(legacy_cfg_path, legacy_cfg_path + ".migrated")
    except OSError:
        pass
