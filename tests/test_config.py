"""
config モジュールのユニットテスト
"""

import json
import os
import tempfile
import unittest

from src import config


class TestLocalSettings(unittest.TestCase):
    def setUp(self):
        self._orig = config.LOCAL_SETTINGS_FILE
        self.tmpdir = tempfile.mkdtemp()
        config.LOCAL_SETTINGS_FILE = os.path.join(self.tmpdir, "local_settings.json")

    def tearDown(self):
        config.LOCAL_SETTINGS_FILE = self._orig
        for f in os.listdir(self.tmpdir):
            os.remove(os.path.join(self.tmpdir, f))
        os.rmdir(self.tmpdir)

    def test_load_empty(self):
        result = config.load_local_settings()
        self.assertEqual(result, {})

    def test_save_and_load(self):
        config.save_local_settings({"shared_data_dir": "/tmp/test"})
        loaded = config.load_local_settings()
        self.assertEqual(loaded["shared_data_dir"], "/tmp/test")

    def test_get_data_dir_from_settings(self):
        config.save_local_settings({"shared_data_dir": self.tmpdir})
        result = config.get_data_dir()
        self.assertEqual(result, self.tmpdir)


if __name__ == "__main__":
    unittest.main()
