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
        lock.release()

    def test_lock_file_contains_info(self):
        lock = FileLock(self.target, timeout=5)
        lock.acquire()
        with open(self.target + ".lock", "r") as f:
            content = f.read()
        parts = content.split(":")
        self.assertEqual(len(parts), 3)
        self.assertEqual(parts[1], str(os.getpid()))
        lock.release()

    def test_stale_lock_detection(self):
        # 古いロックファイルを手動作成
        with open(self.target + ".lock", "w") as f:
            f.write(f"otherhost:99999:0")  # timestamp=0 は確実に古い
        lock = FileLock(self.target, timeout=1)
        lock.acquire()
        self.assertTrue(os.path.exists(self.target + ".lock"))
        lock.release()


if __name__ == "__main__":
    unittest.main()
