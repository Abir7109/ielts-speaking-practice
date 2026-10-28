"""Rubric + band rounding tests."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

import rubric


class TestRounding(unittest.TestCase):
    def test_ielts_rounding_table(self):
        cases = {
            6.0: 6.0,
            6.1: 6.0,
            6.24: 6.0,
            6.25: 6.5,
            6.4: 6.5,
            6.5: 6.5,
            6.625: 6.5,
            6.74: 6.5,
            6.75: 7.0,
            6.9: 7.0,
            0.25: 0.5,
            8.875: 9.0,
        }
        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(rubric.round_half_up(value), expected)

    def test_none_is_zero(self):
        self.assertEqual(rubric.round_half_up(None), 0.0)

    def test_overall_band_mean(self):
        scores = {
            "fluency_coherence": 6.0,
            "lexical_resource": 6.0,
            "grammatical_range": 6.0,
            "pronunciation": 7.0,
        }
        self.assertEqual(rubric.overall_band(scores), 6.5)

    def test_overall_band_ignores_missing(self):
        self.assertEqual(rubric.overall_band({"fluency_coherence": 8.0}), 2.0)


class TestClamp(unittest.TestCase):
    def test_clamp_bounds(self):
        self.assertEqual(rubric.clamp_band(-3), 0.0)
        self.assertEqual(rubric.clamp_band(12), 9.0)
        self.assertEqual(rubric.clamp_band("7.5"), 7.5)
        self.assertEqual(rubric.clamp_band(None), 0.0)
        self.assertEqual(rubric.clamp_band("nonsense"), 0.0)


class TestRubricPrompt(unittest.TestCase):
    def test_prompt_covers_all_criteria(self):
        self.assertIn("Fluency & Coherence", rubric.RUBRIC_PROMPT)
        self.assertIn("Lexical Resource", rubric.RUBRIC_PROMPT)
        self.assertIn("Grammatical Range & Accuracy", rubric.RUBRIC_PROMPT)
        self.assertIn("Pronunciation", rubric.RUBRIC_PROMPT)
        self.assertIn("Band 9", rubric.RUBRIC_PROMPT)
        self.assertIn("Band 0", rubric.RUBRIC_PROMPT)


if __name__ == "__main__":
    unittest.main()
