"""Examiner state-machine tests (no network, no DB)."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from examiner import Examiner


def _fake_eval(band=6.0, part=1, question="Q"):
    return {
        "band_scores": {
            "fluency_coherence": band,
            "lexical_resource": band,
            "grammatical_range": band,
            "pronunciation": band,
        },
        "overall_band": band,
        "strengths": ["clear answer"],
        "improvements": [{"issue": "expand", "better_version": "add an example"}],
        "grammar_errors": [{"error": "he go", "correction": "he goes", "type": "tense"}],
        "band7_tip": "Add a concrete example.",
        "part": part,
        "question": question,
    }


class TestStart(unittest.TestCase):
    def test_part1_payload(self):
        ex = Examiner("")
        payload = ex.start("part1")
        self.assertEqual(payload["kind"], "question")
        self.assertEqual(payload["part"], 1)
        self.assertTrue(payload["question"])
        self.assertTrue(ex.awaiting_answer)

    def test_part2_is_cue_card(self):
        ex = Examiner("")
        payload = ex.start("part2")
        self.assertEqual(payload["kind"], "cue_card")
        self.assertEqual(payload["part"], 2)
        self.assertEqual(payload["prep_time_seconds"], 60)
        self.assertTrue(payload["bullet_points"])

    def test_unknown_mode_defaults_full(self):
        ex = Examiner("")
        payload = ex.start("banana")
        self.assertEqual(ex.mode, "full")
        self.assertEqual(payload["part"], 1)

    def test_spoken_first_question_has_part_intro(self):
        ex = Examiner("")
        payload = ex.start("part1")
        spoken = ex.spoken_question(payload)
        self.assertIn("Part 1", spoken)
        self.assertIn(payload["question"], spoken)

    def test_repeat_does_not_repeat_part_intro(self):
        ex = Examiner("")
        payload = ex.start("part1")
        ex.spoken_question(payload)
        repeated = ex.spoken_repeat()
        self.assertNotIn("Let's begin Part 1", repeated)
        self.assertIn(payload["question"], repeated)

    def test_cue_card_spoken_mentions_prep_time(self):
        ex = Examiner("")
        payload = ex.start("part2")
        spoken = ex.spoken_question(payload)
        self.assertIn("one minute", spoken.lower())
        self.assertIn("Part 2", spoken)


class TestFlow(unittest.TestCase):
    def test_full_test_reaches_all_parts_and_ends(self):
        ex = Examiner("")
        payload = ex.start("full")
        parts_seen = []
        steps = 0
        while payload and steps < 30:
            parts_seen.append(payload["part"])
            ex.skip_evaluation()
            payload = ex.advance()
            steps += 1
        self.assertIsNone(payload)
        self.assertEqual(parts_seen[0], 1)
        self.assertIn(2, parts_seen)
        self.assertIn(3, parts_seen)
        self.assertEqual(parts_seen, sorted(parts_seen))

    def test_part1_mode_is_short(self):
        ex = Examiner("")
        payload = ex.start("part1")
        count = 0
        while payload:
            count += 1
            ex.skip_evaluation()
            payload = ex.advance()
        self.assertGreaterEqual(count, 3)
        self.assertLessEqual(count, 5)

    def test_record_answer_and_no_double_pending(self):
        ex = Examiner("")
        ex.start("part1")
        self.assertTrue(ex.awaiting_answer)
        ex.record_answer("my answer", _fake_eval())
        self.assertFalse(ex.awaiting_answer)
        self.assertEqual(len(ex.answers), 1)


class TestReport(unittest.TestCase):
    def test_report_math(self):
        ex = Examiner("")
        payload = ex.start("part1")
        ex.record_answer("first", _fake_eval(6.0, 1, payload["question"]))
        ex.skip_evaluation()
        payload = ex.advance()
        ex.record_answer("second", _fake_eval(7.0, 1, payload["question"]))

        report = ex.build_report()
        self.assertEqual(report["overall_band"], 6.5)  # mean 6.5
        self.assertEqual(report["band_scores"]["pronunciation"], 6.5)
        self.assertEqual(report["answer_count"], 2)
        self.assertTrue(report["disclaimer"])
        self.assertEqual(len(report["corrections"]), 2)
        self.assertTrue(ex.finished)

    def test_report_without_answers(self):
        ex = Examiner("")
        report = ex.build_report()
        self.assertEqual(report["overall_band"], 0.0)
        self.assertEqual(report["answer_count"], 0)

    def test_spoken_report_mentions_band_and_disclaimer_context(self):
        ex = Examiner("")
        ex.start("part1")
        ex.record_answer("x", _fake_eval(6.5))
        report = ex.build_report()
        spoken = ex.spoken_report(report)
        self.assertIn("6.5", spoken)
        self.assertIn("Pronunciation", spoken)


class TestProgressNoClient(unittest.TestCase):
    def test_get_progress_defaults(self):
        ex = Examiner("")
        p = ex.get_progress()
        self.assertEqual(p["target_band"], 7.0)
        self.assertEqual(p["history"], [])

    def test_set_goal_without_client(self):
        ex = Examiner("")
        info = ex.set_goal(7.5, "2026-12-01")
        self.assertEqual(info["target_band"], 7.5)
        self.assertEqual(info["exam_date"], "2026-12-01")

    def test_save_calls_store(self):
        ex = Examiner("client-123")
        ex.start("part1")
        ex.record_answer("hello", _fake_eval(6.0))
        with patch("store.save_session", return_value=42) as save, \
             patch("store.get_client", return_value=None), \
             patch("store.upsert_client") as upsert:
            sid = ex.save(ex.build_report())
        self.assertEqual(sid, 42)
        save.assert_called_once()
        upsert.assert_called_once()
        fields = upsert.call_args[0][1]
        self.assertEqual(fields["total_sessions"], 1)
        self.assertIn("speaking", fields["average_bands"])


if __name__ == "__main__":
    unittest.main()
