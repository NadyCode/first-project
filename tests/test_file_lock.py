"""
file_lock モジュールのユニットテスト
"""

import os
import tempfile
import unittest

from src.file_lock import FileLock


class TestFileLock(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.target = os.path.join(self.tmpdir, "test_file.txt")
        with open(self.target, "w") as f:
            f.write("test")

    def tearDown(self):
        for f in os.listdir(self.tmpdir):
            os.remove(os.path.join(self.tmpdir, f))
        os.rmdir(self.tmpdir)

    def test_lock_creates_lockfile(self):
        lock = FileLock(self.target, timeout=5)
        lock.acquire()
        self.assertTrue(os.path.exists(self.target + ".lock"))
        lock.release()
        self.assertFalse(os.path.exists(self.target + ".lock"))

    def test_context_manager(self):
        with FileLock(self.target, timeout=5):
            self.assertTrue(os.path.exists(self.target + ".lock"))
        self.assertFalse(os.path.exists(self.target + ".lock"))

    def test_double_release(self):
        lock = FileLock(self.target, timeout=5)
        lock.acquire()
        lock.release()
        lock.release()  # should not raise


if __name__ == "__main__":
    unittest.main()
