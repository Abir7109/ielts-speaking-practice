"""Store tests — force JSONL fallback with a temp data dir."""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

import store


class TestStoreFileFallback(unittest.TestCase):
    def setUp(self):
        self._orig_dir = store.DATA_DIR
        self._orig_conn = store._CONN
        self._orig_ready = store._READY
        self.tmp = Path(tempfile.mkdtemp(prefix="ielts_store_"))
        store.DATA_DIR = self.tmp
        store._CONN = None
        store._READY = True

    def tearDown(self):
        store.DATA_DIR = self._orig_dir
        store._CONN = self._orig_conn
        store._READY = self._orig_ready
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_db_inactive(self):
        self.assertFalse(store.db_active())

    def test_upsert_and_get(self):
        store.upsert_client("c1", {"target_band": 7.5})
        client = store.get_client("c1")
        self.assertEqual(client["target_band"], 7.5)

    def test_upsert_merges_latest(self):
        store.upsert_client("c1", {"target_band": 7.0})
        store.upsert_client("c1", {"target_band": 8.0, "streak_days": 3})
        client = store.get_client("c1")
        self.assertEqual(client["target_band"], 8.0)
        self.assertEqual(client["streak_days"], 3)

    def test_get_missing_client(self):
        self.assertIsNone(store.get_client("nobody"))

    def test_save_session_file_mode(self):
        sid = store.save_session(
            {
                "client_id": "c1",
                "mode": "full",
                "part_scores": {"1": 6.0},
                "overall_band": 6.5,
                "started_at": "2026-10-29T10:00:00",
                "report": {"overall_band": 6.5},
            },
            [
                {"part": 1, "question": "Q", "answer_text": "A", "overall_band": 6.0},
                {"part": 2, "question": "Q2", "answer_text": "B", "overall_band": 7.0},
            ],
        )
        self.assertIsNone(sid)
        lines = (self.tmp / "sessions.jsonl").read_text().strip().splitlines()
        self.assertEqual(len(lines), 1)
        saved = json.loads(lines[0])
        self.assertEqual(saved["client_id"], "c1")
        self.assertEqual(saved["answers"], 2)

    def test_history_roundtrip(self):
        store.save_session(
            {"client_id": "c9", "mode": "part1", "overall_band": 6.0, "report": {}}, []
        )
        store.save_session(
            {"client_id": "c9", "mode": "part1", "overall_band": 7.0, "report": {}}, []
        )
        store.save_session(
            {"client_id": "other", "mode": "part1", "overall_band": 5.0, "report": {}}, []
        )
        history = store.get_history("c9", 10)
        self.assertEqual(len(history), 2)
        self.assertTrue(all(h["client_id"] == "c9" for h in history))

    def test_init_without_url_uses_fallback(self):
        store._READY = False
        # hermetic: never touch a real database even if DATABASE_URL is in env
        with patch.object(store, "_connect", return_value=None):
            self.assertFalse(store.init())
        self.assertTrue((self.tmp).exists())


if __name__ == "__main__":
    unittest.main()
