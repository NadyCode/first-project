"""
data_manager モジュールのユニットテスト
"""

import csv
import json
import os
import tempfile
import unittest

from src.data_manager import (
    get_all_staff,
    get_respondents,
    hash_password,
    load_answers,
    load_master_users,
    load_survey_config,
    save_answer,
    save_master_users,
    save_survey_config,
    verify_password,
)


class TestMasterUsers(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.master_path = os.path.join(self.tmpdir, "master_user.csv")

    def tearDown(self):
        for f in os.listdir(self.tmpdir):
            os.remove(os.path.join(self.tmpdir, f))
        os.rmdir(self.tmpdir)

    def test_load_empty(self):
        result = load_master_users("/nonexistent/path.csv")
        self.assertEqual(result, {})

    def test_save_and_load(self):
        data = {"内科": ["田中太郎", "鈴木花子"], "外科": ["山田次郎"]}
        save_master_users(data, self.master_path)
        loaded = load_master_users(self.master_path)
        self.assertEqual(loaded["内科"], ["田中太郎", "鈴木花子"])
        self.assertEqual(loaded["外科"], ["山田次郎"])

    def test_get_all_staff(self):
        data = {"内科": ["田中太郎"], "外科": ["山田次郎"]}
        save_master_users(data, self.master_path)
        staff = get_all_staff(self.master_path)
        self.assertEqual(len(staff), 2)
        self.assertIn(("内科", "田中太郎"), staff)
        self.assertIn(("外科", "山田次郎"), staff)


class TestSurveyConfig(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.tmpdir, "survey_config.json")

    def tearDown(self):
        for f in os.listdir(self.tmpdir):
            os.remove(os.path.join(self.tmpdir, f))
        os.rmdir(self.tmpdir)

    def test_load_default(self):
        config = load_survey_config("/nonexistent/path.json")
        self.assertEqual(config["title"], "")
        self.assertEqual(config["questions"], [])

    def test_save_and_load(self):
        config = {
            "title": "テストアンケート",
            "description": "テスト用",
            "created_at": "2026-01-01",
            "admin_password_hash": "",
            "questions": [
                {"id": 1, "type": "single_choice", "required": True, "text": "Q1", "choices": ["A", "B"]},
            ],
            "reference_files": [],
        }
        save_survey_config(config, self.config_path)
        loaded = load_survey_config(self.config_path)
        self.assertEqual(loaded["title"], "テストアンケート")
        self.assertEqual(len(loaded["questions"]), 1)


class TestAnswers(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.answers_path = os.path.join(self.tmpdir, "answers.csv")

    def tearDown(self):
        for f in os.listdir(self.tmpdir):
            os.remove(os.path.join(self.tmpdir, f))
        os.rmdir(self.tmpdir)

    def test_save_and_load(self):
        save_answer("内科", "田中太郎", {1: "A", 2: "B"}, self.answers_path)
        answers = load_answers(self.answers_path)
        self.assertEqual(len(answers), 1)
        self.assertEqual(answers[0]["department"], "内科")
        self.assertEqual(answers[0]["name"], "田中太郎")
        self.assertEqual(answers[0]["q1"], "A")
        self.assertEqual(answers[0]["q2"], "B")

    def test_multiple_answers(self):
        save_answer("内科", "田中太郎", {1: "A"}, self.answers_path)
        save_answer("外科", "山田次郎", {1: "B"}, self.answers_path)
        answers = load_answers(self.answers_path)
        self.assertEqual(len(answers), 2)

    def test_get_respondents(self):
        save_answer("内科", "田中太郎", {1: "A"}, self.answers_path)
        save_answer("外科", "山田次郎", {1: "B"}, self.answers_path)
        respondents = get_respondents(self.answers_path)
        self.assertIn(("内科", "田中太郎"), respondents)
        self.assertIn(("外科", "山田次郎"), respondents)
        self.assertEqual(len(respondents), 2)


class TestPassword(unittest.TestCase):
    def test_hash_password(self):
        h = hash_password("test123")
        self.assertIsInstance(h, str)
        self.assertEqual(len(h), 64)  # SHA-256 hex digest

    def test_verify_password_correct(self):
        h = hash_password("test123")
        self.assertTrue(verify_password("test123", h))

    def test_verify_password_wrong(self):
        h = hash_password("test123")
        self.assertFalse(verify_password("wrong", h))

    def test_verify_password_empty_hash(self):
        self.assertTrue(verify_password("anything", ""))


if __name__ == "__main__":
    unittest.main()
