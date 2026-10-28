"""Evaluation pipeline tests — fully offline (no API calls)."""
import asyncio
import io
import os
import sys
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

import evaluation
import rubric

_OFFLINE_ENV = {"DEEPSEEK_API_KEY": "", "GEMINI_API_KEY": ""}


class TestExtractJson(unittest.TestCase):
    def test_fenced(self):
        text = 'sure!\n```json\n{"band_scores": {"a": 1}}\n```\nbye'
        self.assertEqual(evaluation.extract_json(text), {"band_scores": {"a": 1}})

    def test_loose(self):
        self.assertEqual(evaluation.extract_json('prefix {"x": 2} suffix'), {"x": 2})

    def test_garbage(self):
        self.assertIsNone(evaluation.extract_json("no json here"))
        self.assertIsNone(evaluation.extract_json(""))


class TestWav(unittest.TestCase):
    def test_pcm_to_wav_header(self):
        pcm = b"\x01\x00" * 16000
        wav = evaluation._pcm_to_wav(pcm)
        self.assertEqual(wav[:4], b"RIFF")
        with wave.open(io.BytesIO(wav), "rb") as wf:
            self.assertEqual(wf.getnchannels(), 1)
            self.assertEqual(wf.getsampwidth(), 2)
            self.assertEqual(wf.getframerate(), 16000)
            self.assertEqual(wf.getnframes(), 16000)


class TestHeuristics(unittest.TestCase):
    def test_short_answer_scored_low(self):
        result = evaluation._heuristic_text_evaluation("I like tea.")
        self.assertEqual(result["band_scores"]["fluency_coherence"], 4.0)
        self.assertIn("_degraded", result)

    def test_long_answer_scored_higher(self):
        answer = " ".join(["word"] * 120)
        result = evaluation._heuristic_text_evaluation(answer)
        self.assertEqual(result["band_scores"]["fluency_coherence"], 6.0)
        self.assertEqual(result["word_count"], 120)

    def test_pronunciation_heuristic_flag(self):
        result = evaluation._heuristic_pronunciation()
        self.assertIsNone(result["pronunciation_band"])
        self.assertEqual(result["_degraded"], "audio-unavailable")


class TestEvaluateAnswerOffline(unittest.TestCase):
    def test_offline_merge(self):
        answer = (
            "I really enjoy reading because it helps me relax after a long day "
            "and I usually read for about thirty minutes before sleeping."
        )
        with patch.dict(os.environ, _OFFLINE_ENV):
            ev = asyncio.run(
                evaluation.evaluate_answer(answer, b"", 1, "Do you like reading?")
            )
        self.assertEqual(set(ev["band_scores"].keys()), set(rubric.CRITERIA))
        self.assertGreaterEqual(ev["overall_band"], 3.0)
        self.assertLessEqual(ev["overall_band"], 9.0)
        self.assertIn("text-evaluator-unavailable", ev["degraded"])
        self.assertIn("audio-unavailable", ev["degraded"])
        self.assertEqual(ev["part"], 1)
        self.assertEqual(ev["question"], "Do you like reading?")
        self.assertTrue(ev["corrected_transcript"])

    def test_short_audio_skips_pronunciation_network(self):
        with patch.dict(os.environ, _OFFLINE_ENV):
            ev = asyncio.run(
                evaluation.evaluate_answer("hello", b"\x00\x00" * 100, 2, "Q")
            )
        # < 2s audio -> heuristic pronunciation, pronunciation score from text
        self.assertEqual(ev["pronunciation_detail"]["intelligibility"], "unknown")


if __name__ == "__main__":
    unittest.main()
