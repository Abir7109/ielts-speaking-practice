"""Evaluation pipeline tests — fully offline (no API calls)."""
import asyncio
import io
import json
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
        self.assertEqual(result["_provider"], "heuristic")

    def test_long_answer_scored_higher(self):
        answer = " ".join(["word"] * 120)
        result = evaluation._heuristic_text_evaluation(answer)
        # Length earns the turn, but 120 words with zero connectives still loses half a
        # band — fluency is no longer a pure word-count ladder.
        self.assertEqual(result["band_scores"]["fluency_coherence"], 5.5)
        self.assertEqual(result["word_count"], 120)

    def test_length_does_not_drive_every_criterion(self):
        short_precise = (
            "Public transport ought to be subsidised, since it curbs congestion; "
            "whereas private cars exacerbate pollution. It is a double-edged sword."
        )
        long_rambling = " ".join(
            ["I think it is good and I like it a lot because it is nice"] * 6
        )
        precise = evaluation._heuristic_text_evaluation(short_precise)["band_scores"]
        rambling = evaluation._heuristic_text_evaluation(long_rambling)["band_scores"]
        self.assertGreater(
            precise["lexical_resource"], rambling["lexical_resource"]
        )

    def test_pronunciation_is_not_scored_from_text(self):
        with patch.dict(os.environ, _OFFLINE_ENV):
            ev = asyncio.run(
                evaluation.evaluate_answer("I like tea.", b"", 1, "Do you like tea?")
            )
        self.assertIsNone(ev["band_scores"]["pronunciation"])
        self.assertFalse(ev["pronunciation_assessed"])
        self.assertIn("pronunciation-unassessed", ev["degraded"])
        self.assertIn("Not assessed", ev["criterion_feedback"]["pronunciation"]["reason"])

    def test_heuristic_explains_every_criterion(self):
        answer = (
            "I really like cooking because it is relaxing. For example, last Sunday "
            "I made pasta for my family and everybody enjoyed it, although I am not "
            "a professional cook. In the future I want to learn more recipes."
        )
        result = evaluation._heuristic_text_evaluation(answer)
        for crit in rubric.CRITERIA:
            fb = result["criterion_feedback"][crit]
            self.assertTrue(fb["reason"], f"missing reason for {crit}")
            self.assertTrue(fb["next_step"], f"missing next_step for {crit}")
        self.assertTrue(result["why_band_summary"])
        self.assertNotEqual(
            result["criterion_feedback"]["fluency_coherence"]["reason"],
            result["criterion_feedback"]["lexical_resource"]["reason"],
        )

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
        self.assertIn("pronunciation-unassessed", ev["degraded"])
        self.assertEqual(ev["evaluator"], "heuristic")
        self.assertEqual(set(ev["criterion_feedback"].keys()), set(rubric.CRITERIA))
        self.assertTrue(ev["why_band_summary"])
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


class TestEvaluatePartOffline(unittest.TestCase):
    def test_part_merge_combines_all_answers(self):
        answers = [
            {"question": "Do you like reading?", "answer_text": "I enjoy reading because it helps me relax."},
            {"question": "What do you read?", "answer_text": "I usually read novels and history books in the evening."},
        ]
        with patch.dict(os.environ, _OFFLINE_ENV):
            ev = asyncio.run(evaluation.evaluate_part(answers, b"", 1))
        self.assertEqual(set(ev["band_scores"].keys()), set(rubric.CRITERIA))
        self.assertEqual(ev["part"], 1)
        self.assertIn("Do you like reading?", ev["question"])
        self.assertIn("text-evaluator-unavailable", ev["degraded"])

    def test_part_prompt_mentions_whole_part(self):
        from prompts import build_part_evaluation_prompt
        prompt = build_part_evaluation_prompt(
            [("Q1", "A one"), ("Q2", "A two")], 3
        )
        self.assertIn("WHOLE IELTS Speaking Part 3", prompt)
        self.assertIn("A one", prompt)
        self.assertIn("A two", prompt)
        self.assertIn("Do NOT default to Band 5.5", prompt)


class TestTextEvaluatorRouting(unittest.TestCase):
    def test_gemini_used_when_key_configured(self):
        payload = (
            '{"band_scores": {"fluency_coherence": 6.5, "lexical_resource": 6.5, '
            '"grammatical_range": 6.0, "pronunciation": 6.5}, '
            '"criterion_feedback": {}, "why_band_summary": "test", '
            '"strengths": [], "improvements": [], "grammar_errors": [], '
            '"band7_tip": "t", "filler_words_count": 0, "word_count": 10}'
        )

        async def fake_gemini(prompt, **kwargs):
            return payload

        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key", "DEEPSEEK_API_KEY": ""}), \
                patch.object(evaluation, "_gemini_json", side_effect=fake_gemini):
            ev = asyncio.run(
                evaluation.evaluate_answer(
                    "I enjoy reading books because they help me relax.",
                    b"", 1, "Do you like reading?",
                )
            )
        self.assertEqual(ev["evaluator"], "gemini")
        self.assertEqual(ev["band_scores"]["fluency_coherence"], 6.5)
        self.assertNotIn("text-evaluator-unavailable", ev.get("degraded", []))


class TestCloneGuard(unittest.TestCase):
    """The model must not be able to hand back one impression four times."""

    def _run_with_payload(self, criterion_feedback, answer="I like tea because it is warm."):
        payload = json.dumps({
            "band_scores": {
                "fluency_coherence": 6.0,
                "lexical_resource": 6.5,
                "grammatical_range": 5.5,
            },
            "criterion_feedback": criterion_feedback,
            "why_band_summary": "x", "strengths": [], "improvements": [],
            "grammar_errors": [], "band7_tip": "t",
            "filler_words_count": 0, "word_count": 8,
        })

        async def fake(prompt, **kwargs):
            return payload

        with patch.dict(os.environ, {"GEMINI_API_KEY": "k", "DEEPSEEK_API_KEY": ""}), \
                patch.object(evaluation, "_gemini_json", side_effect=fake):
            return asyncio.run(evaluation.evaluate_answer(answer, b"", 1, "Do you like tea?"))

    def test_identical_reasons_are_repaired(self):
        cloned = {
            c: {
                "reason": "The answers are too short and under-developed.",
                "evidence": "I like tea",
                "next_step": "Extend your answers.",
            }
            for c in rubric.TEXT_CRITERIA
        }
        ev = self._run_with_payload(cloned)
        reasons = [ev["criterion_feedback"][c]["reason"] for c in rubric.TEXT_CRITERIA]
        self.assertEqual(len(set(reasons)), 3, f"reasons still cloned: {reasons}")
        self.assertTrue(ev.get("repaired_criteria"))

    def test_text_evaluator_cannot_set_pronunciation(self):
        feedback = {
            c: {"reason": f"distinct reason {i}", "evidence": f"quote {i}", "next_step": "n"}
            for i, c in enumerate(rubric.TEXT_CRITERIA)
        }
        ev = self._run_with_payload(feedback)
        self.assertIsNone(ev["band_scores"]["pronunciation"])
        self.assertFalse(ev["pronunciation_assessed"])


class TestEvidenceGrounding(unittest.TestCase):
    def test_part_prompt_carries_measured_signals(self):
        from prompts import build_part_evaluation_prompt
        prompt = build_part_evaluation_prompt(
            [("Q1", "I like tea.")], 1, evidence="type-token ratio 0.52"
        )
        self.assertIn("MEASURED SIGNALS", prompt)
        self.assertIn("type-token ratio 0.52", prompt)
        self.assertIn("STRICT UNIQUENESS RULE", prompt)
        self.assertNotIn('"pronunciation": <0-9', prompt)

    def test_part_prompt_omits_evidence_block_when_absent(self):
        from prompts import build_part_evaluation_prompt
        prompt = build_part_evaluation_prompt([("Q1", "A")], 1)
        self.assertNotIn("MEASURED SIGNALS", prompt)

    def test_evidence_brief_splits_signals_by_criterion(self):
        brief = evaluation.build_evidence_brief(
            "I like tea because it is warm. For example, every morning I brew a cup.",
            pairs=[("Do you like tea?", "I like tea because it is warm.")],
            audio_seconds=12.0,
        )
        for section in (
            "FLUENCY & COHERENCE signals:",
            "LEXICAL RESOURCE signals:",
            "GRAMMATICAL RANGE & ACCURACY signals:",
        ):
            self.assertIn(section, brief)
        self.assertIn("words per minute", brief)

    def test_evidence_brief_defers_pronunciation_to_audio(self):
        brief = evaluation.build_evidence_brief("I like tea.", audio_seconds=0.0)
        self.assertIn("do not guess it from the transcript", brief)


class TestDescriptorShapedScoring(unittest.TestCase):
    """Each band has to move on its own descriptor, not on one overall impression."""

    ADVANCED = (
        "The film, which I'd been looking forward to for weeks, fell flat because "
        "the pacing was uneven; had the script been tighter, I think the ending "
        "would have landed. Although I enjoyed the acting, I'd say it wasn't worth "
        "the hype."
    )
    BASIC = (
        "I like travelling because I go to new place and I eat the food and I take "
        "the photo with my friend. It is very good and I am happy when I go there. "
        "Next time I want to go again to that place because it is cheap."
    )

    def test_repeated_because_is_not_a_range_of_structures(self):
        basic = evaluation._heuristic_text_evaluation(self.BASIC)["band_scores"]
        advanced = evaluation._heuristic_text_evaluation(self.ADVANCED)["band_scores"]
        # Band 7 needs "a variety of complex structures"; subordination alone
        # caps Grammatical Range at 6.0.
        self.assertEqual(basic["grammatical_range"], 6.0)
        self.assertGreater(advanced["grammatical_range"], basic["grammatical_range"])

    def test_connectives_prevent_a_false_fluency_penalty(self):
        reason = evaluation._heuristic_text_evaluation(
            self.ADVANCED)["criterion_feedback"]["fluency_coherence"]["reason"]
        self.assertNotIn("no connective or discourse marker", reason)

    def test_tiny_sample_earns_no_vocabulary_credit(self):
        # Every word in a five-word answer is unique by construction — TTR 1.0 is
        # an artifact of the sample size, not evidence of lexical resource.
        scores = evaluation._heuristic_text_evaluation(
            "Tea, coffee, milk, sugar.")["band_scores"]
        self.assertLess(scores["lexical_resource"], 6.0)

    def test_one_answer_is_one_speaking_turn(self):
        self.assertEqual(
            evaluation._text_metrics("I went home. It was late. I was tired.")["turns"],
            1,
        )
        part = "A1: I went home.\nA2: It was late, because I missed the bus."
        self.assertEqual(evaluation._text_metrics(part)["turns"], 2)

    def test_markers_match_whole_words(self):
        metrics = evaluation._text_metrics("This was difficult for me.")
        self.assertNotIn("if", metrics["advanced_hits"])


if __name__ == "__main__":
    unittest.main()
