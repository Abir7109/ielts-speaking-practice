"""Regression tests: examiner turn-taking — the mic gate and duplicate speech.

Both bugs came from the same place: `feed_browser_audio` dropped the candidate's
microphone while `_model_is_speaking` was set, and cleared the scripted-transcript
suppression on the first mic frame that got through.
"""
import asyncio
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from voice import (  # noqa: E402
    PREMATURE_CALL_SECONDS,
    VoiceSession,
)

FRAME = b"\x01\x02" * 160


class FakeSio:
    def __init__(self):
        self.emitted = []

    async def emit(self, event, data, room=None):
        self.emitted.append((event, data))


def make_session():
    vs = VoiceSession(FakeSio(), "sid-test", "")
    vs.audio_queue = asyncio.Queue(maxsize=10)
    return vs


class TestMicGate(unittest.TestCase):
    def setUp(self):
        self.vs = make_session()

    def test_mic_is_dropped_while_the_examiner_speaks(self):
        self.vs._model_is_speaking = True
        self.vs.feed_browser_audio(FRAME)
        self.assertTrue(self.vs.audio_queue.empty())

    def test_playback_drain_reopens_the_mic_immediately(self):
        self.vs._model_is_speaking = True
        self.vs.notify_playback_drained()
        self.assertFalse(self.vs._model_is_speaking)
        self.vs.feed_browser_audio(FRAME)
        self.assertFalse(self.vs.audio_queue.empty())

    def test_drain_is_a_no_op_when_already_idle(self):
        self.vs._model_is_speaking = False
        armed = self.vs._last_audio_time
        self.vs.notify_playback_drained()
        self.assertEqual(self.vs._last_audio_time, armed)

    def test_mic_frames_do_not_unmask_a_scripted_question(self):
        """The silence gap before generation starts used to leak the live text."""
        self.vs._script_transcript_active = True
        self.vs._script_transcript_at = time.monotonic()
        self.vs.feed_browser_audio(FRAME)
        self.assertTrue(self.vs._script_transcript_active)

    def test_drain_does_not_unmask_a_scripted_question(self):
        """A stalled network empties the browser queue mid-sentence."""
        self.vs._model_is_speaking = True
        self.vs._script_transcript_active = True
        self.vs._script_transcript_at = time.monotonic()
        self.vs.notify_playback_drained()
        self.assertTrue(self.vs._script_transcript_active)


class TestNoAnswerGuidance(unittest.TestCase):
    def setUp(self):
        self.vs = make_session()

    def test_call_right_after_the_question_asks_for_patience(self):
        self.vs._question_asked_at = time.monotonic()
        self.assertIn("Take your time.", self.vs._no_answer_guidance())

    def test_call_long_after_the_question_asks_for_an_answer(self):
        self.vs._question_asked_at = time.monotonic() - PREMATURE_CALL_SECONDS - 1
        self.assertIn("Nothing was recorded", self.vs._no_answer_guidance())

    def test_unknown_question_time_asks_for_an_answer(self):
        self.vs._question_asked_at = 0.0
        self.assertIn("Nothing was recorded", self.vs._no_answer_guidance())

    def test_never_tells_the_model_to_read_the_question_again(self):
        for asked in (time.monotonic(), time.monotonic() - 300, 0.0):
            self.vs._question_asked_at = asked
            text = self.vs._no_answer_guidance()
            self.assertNotIn("answer it again", text)
            self.assertIn("Do NOT repeat", text)


if __name__ == "__main__":
    unittest.main()
