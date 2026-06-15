"""
data_manager モジュールのユニットテスト（複数アンケート対応）
"""

import os
import shutil
import tempfile
import unittest
from datetime import date, timedelta

import src.config as config
from src import data_manager as dm


class _TempDataDir(unittest.TestCase):
    """共有データフォルダを一時ディレクトリに差し替える基底クラス。"""

    def setUp(self):
        self._orig_dir = config.DATA_DIR
        self.tmpdir = tempfile.mkdtemp()
        config.DATA_DIR = self.tmpdir
        dm.ensure_data_layout()

    def tearDown(self):
        config.DATA_DIR = self._orig_dir
        shutil.rmtree(self.tmpdir, ignore_errors=True)


class TestMasterUsers(_TempDataDir):
    def test_load_empty(self):
        self.assertEqual(dm.load_master_users(), {})

    def test_save_and_load(self):
        data = {"内科": ["田中太郎", "鈴木花子"], "外科": ["山田次郎"]}
        dm.save_master_users(data)
        loaded = dm.load_master_users()
        self.assertEqual(loaded["内科"], ["田中太郎", "鈴木花子"])
        self.assertEqual(loaded["外科"], ["山田次郎"])

    def test_get_all_staff(self):
        dm.save_master_users({"内科": ["田中太郎"], "外科": ["山田次郎"]})
        staff = dm.get_all_staff()
        self.assertEqual(len(staff), 2)
        self.assertIn(("内科", "田中太郎"), staff)


class TestSurveyManagement(_TempDataDir):
    def test_create_and_list(self):
        sid = dm.create_survey("テストアンケート")
        surveys = dm.list_surveys()
        self.assertEqual(len(surveys), 1)
        self.assertEqual(surveys[0]["id"], sid)
        self.assertEqual(surveys[0]["title"], "テストアンケート")

    def test_save_and_load_survey(self):
        sid = dm.create_survey("A")
        cfg = dm.load_survey(sid)
        cfg["title"] = "更新済み"
        cfg["questions"] = [
            {"id": 1, "type": "single_choice", "required": True, "text": "Q1", "choices": ["はい", "いいえ"]}
        ]
        dm.save_survey(cfg)
        reloaded = dm.load_survey(sid)
        self.assertEqual(reloaded["title"], "更新済み")
        self.assertEqual(len(reloaded["questions"]), 1)

    def test_archive_and_active(self):
        sid = dm.create_survey("A")
        self.assertEqual(len(dm.list_active_surveys()), 1)
        dm.archive_survey(sid)
        self.assertEqual(len(dm.list_active_surveys()), 0)
        self.assertEqual(len(dm.list_surveys()), 1)
        dm.unarchive_survey(sid)
        self.assertEqual(len(dm.list_active_surveys()), 1)

    def test_delete_survey(self):
        sid = dm.create_survey("A")
        dm.delete_survey(sid)
        self.assertEqual(len(dm.list_surveys()), 0)


class TestDeadline(_TempDataDir):
    def test_open_no_dates(self):
        cfg = dm.load_survey(dm.create_survey("A"))
        self.assertTrue(dm.is_survey_open(cfg))

    def test_before_start(self):
        sid = dm.create_survey("A")
        cfg = dm.load_survey(sid)
        cfg["start_date"] = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")
        dm.save_survey(cfg)
        self.assertFalse(dm.is_survey_open(cfg))
        self.assertIn("開始", dm.survey_open_reason(cfg))

    def test_after_end(self):
        sid = dm.create_survey("A")
        cfg = dm.load_survey(sid)
        cfg["end_date"] = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
        dm.save_survey(cfg)
        self.assertFalse(dm.is_survey_open(cfg))
        self.assertIn("終了", dm.survey_open_reason(cfg))

    def test_within_range(self):
        sid = dm.create_survey("A")
        cfg = dm.load_survey(sid)
        cfg["start_date"] = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
        cfg["end_date"] = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")
        dm.save_survey(cfg)
        self.assertTrue(dm.is_survey_open(cfg))


class TestAnswers(_TempDataDir):
    def setUp(self):
        super().setUp()
        self.sid = dm.create_survey("A")

    def test_save_and_load(self):
        dm.save_survey_answer(self.sid, "内科", "田中太郎", {1: "A", 2: "B"})
        answers = dm.load_survey_answers(self.sid)
        self.assertEqual(len(answers), 1)
        self.assertEqual(answers[0]["department"], "内科")
        self.assertEqual(answers[0]["name"], "田中太郎")
        self.assertEqual(answers[0]["q1"], "A")
        self.assertEqual(answers[0]["q2"], "B")

    def test_modify_replaces_existing(self):
        dm.save_survey_answer(self.sid, "内科", "田中太郎", {1: "A"})
        dm.save_survey_answer(self.sid, "内科", "田中太郎", {1: "B"})
        answers = dm.load_survey_answers(self.sid)
        self.assertEqual(len(answers), 1)  # 重複せず置き換え
        self.assertEqual(answers[0]["q1"], "B")

    def test_anonymous_appends(self):
        dm.save_survey_answer(self.sid, "内科", "田中太郎", {1: "A"}, anonymous=True)
        dm.save_survey_answer(self.sid, "内科", "鈴木花子", {1: "B"}, anonymous=True)
        answers = dm.load_survey_answers(self.sid)
        self.assertEqual(len(answers), 2)
        self.assertEqual(answers[0]["name"], dm.ANONYMOUS_NAME)
        # 匿名は回答者集合に含めない
        self.assertEqual(len(dm.get_survey_respondents(self.sid)), 0)

    def test_get_respondents(self):
        dm.save_survey_answer(self.sid, "内科", "田中太郎", {1: "A"})
        dm.save_survey_answer(self.sid, "外科", "山田次郎", {1: "B"})
        respondents = dm.get_survey_respondents(self.sid)
        self.assertIn(("内科", "田中太郎"), respondents)
        self.assertIn(("外科", "山田次郎"), respondents)

    def test_backup(self):
        dm.save_survey_answer(self.sid, "内科", "田中太郎", {1: "A"})
        path = dm.backup_survey_answers(self.sid)
        self.assertIsNotNone(path)
        self.assertTrue(os.path.exists(path))
        # daily_only は当日2回目スキップ
        self.assertIsNone(dm.backup_survey_answers(self.sid, daily_only=True))


class TestConditional(_TempDataDir):
    def test_no_condition_visible(self):
        q = {"id": 2, "type": "free_text", "text": "Q2"}
        self.assertTrue(dm.question_is_visible(q, {1: "はい"}))

    def test_condition_match(self):
        q = {"id": 2, "type": "free_text", "text": "Q2",
             "condition": {"question_id": 1, "equals": "はい"}}
        self.assertTrue(dm.question_is_visible(q, {1: "はい"}))
        self.assertFalse(dm.question_is_visible(q, {1: "いいえ"}))


class TestAppConfig(_TempDataDir):
    def test_admin_password(self):
        self.assertEqual(dm.get_admin_password_hash(), "")
        dm.set_admin_password("secret")
        self.assertTrue(dm.verify_password("secret", dm.get_admin_password_hash()))
        self.assertFalse(dm.verify_password("wrong", dm.get_admin_password_hash()))

    def test_active_survey_id(self):
        dm.set_active_survey_id("survey_x")
        self.assertEqual(dm.get_active_survey_id(), "survey_x")


class TestVersion(_TempDataDir):
    def test_no_version_file(self):
        outdated, latest, note = dm.check_version_outdated("1.0.0")
        self.assertFalse(outdated)

    def test_outdated(self):
        dm.save_version_info("2.0.0", "更新してください")
        outdated, latest, note = dm.check_version_outdated("1.0.0")
        self.assertTrue(outdated)
        self.assertEqual(latest, "2.0.0")
        self.assertEqual(note, "更新してください")

    def test_up_to_date(self):
        dm.save_version_info("1.0.0")
        outdated, _, _ = dm.check_version_outdated("1.0.0")
        self.assertFalse(outdated)
        outdated, _, _ = dm.check_version_outdated("1.2.0")
        self.assertFalse(outdated)


class TestPassword(unittest.TestCase):
    def test_hash_password(self):
        self.assertEqual(len(dm.hash_password("test123")), 64)

    def test_verify(self):
        h = dm.hash_password("test123")
        self.assertTrue(dm.verify_password("test123", h))
        self.assertFalse(dm.verify_password("wrong", h))
        self.assertTrue(dm.verify_password("anything", ""))


class TestMigration(_TempDataDir):
    def test_legacy_migration(self):
        import json
        # 旧形式ファイルを配置
        legacy_cfg = config.legacy_survey_config_path()
        with open(legacy_cfg, "w", encoding="utf-8") as f:
            json.dump({
                "title": "旧アンケート",
                "description": "説明",
                "admin_password_hash": dm.hash_password("oldpw"),
                "questions": [{"id": 1, "type": "free_text", "text": "Q1"}],
                "reference_files": [],
            }, f, ensure_ascii=False)
        legacy_ans = config.legacy_answers_path()
        with open(legacy_ans, "w", encoding="utf-8") as f:
            f.write("timestamp,department,name,q1\n2026-01-01,内科,田中,回答\n")

        dm.ensure_data_layout()

        surveys = dm.list_surveys()
        self.assertEqual(len(surveys), 1)
        self.assertEqual(surveys[0]["title"], "旧アンケート")
        # パスワードがグローバルへ移行
        self.assertTrue(dm.verify_password("oldpw", dm.get_admin_password_hash()))
        # 回答も移行
        answers = dm.load_survey_answers(surveys[0]["id"])
        self.assertEqual(len(answers), 1)


if __name__ == "__main__":
    unittest.main()
