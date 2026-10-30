"""Gemini Live voice engine for the IELTS examiner.

Port of SODA's AudioLoop (backend/soda.py) stripped to: browser mic in, model
audio out, transcriptions, and the 7 IELTS examiner tools. One VoiceSession per
connected visitor — every emit is room-targeted to the owning sid so parallel
sessions never see each other's audio or panels.
"""
import asyncio
import base64
import math
import os
from datetime import date, datetime, timedelta
import struct
import time
import traceback

from dotenv import load_dotenv

load_dotenv()

import websockets.exceptions
from google import genai
from google.genai import types

import evaluation as eval_mod
import store
from examiner import Examiner, band_words
from ielts_tools import build_tools
from logger import log
from prompts import GREETING_START_MESSAGE, build_examiner_prompt

MODEL = os.getenv("LIVE_MODEL", "models/gemini-3.1-flash-live-preview")
SEND_SAMPLE_RATE = 16000
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE = 512
MAX_ANSWER_SECONDS = 300
MAX_ANSWER_BYTES = SEND_SAMPLE_RATE * 2 * MAX_ANSWER_SECONDS
MAX_PART_AUDIO_SECONDS = 240
MAX_PART_AUDIO_BYTES = SEND_SAMPLE_RATE * 2 * MAX_PART_AUDIO_SECONDS
MIN_ANSWER_AUDIO_BYTES = SEND_SAMPLE_RATE * 2  # 1s — below this is "no answer"
EVAL_LIMIT_PER_HOUR = 30
MAX_RETRIES = 10
SPEECH_TOOLS = {"start_test", "next_question", "repeat_question", "finish_test"}

_GEMINI_CLIENT = None


def _get_client():
    global _GEMINI_CLIENT
    if _GEMINI_CLIENT is None:
        _GEMINI_CLIENT = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    return _GEMINI_CLIENT


def _rms_level(data: bytes) -> float:
    count = len(data) // 2
    if count <= 0:
        return 0.0
    shorts = struct.unpack(f"<{count}h", data)
    rms = math.sqrt(sum(s * s for s in shorts) / count)
    return min(1.0, rms / 5000.0)


class VoiceSession:
    def __init__(self, sio, sid: str, client_id: str = ""):
        self.sio = sio
        self.sid = sid
        self.client_id = client_id or ""
        self.examiner = Examiner(self.client_id)
        self.start_message = GREETING_START_MESSAGE

        self.session = None
        self.task: asyncio.Task | None = None
        self.stop_event = asyncio.Event()
        self.audio_in_queue: asyncio.Queue | None = None   # model → playback
        self.audio_queue: asyncio.Queue | None = None      # mic → model

        self._model_is_speaking = False
        self._tools_running = False
        self._last_tool_start = 0.0
        self._processed_fc_ids: set = set()
        self._last_input_transcription = ""
        self._last_output_transcription = ""
        self._script_transcript_active = False
        self._script_transcript_seen = False

        # candidate answer capture (owned by backend, never model-supplied)
        self._answer_text = ""
        self._answer_pcm = bytearray()
        self._part_pcm = bytearray()   # audio for the current part (scored at part end)
        self._eval_times: list[float] = []

        self._prep_task: asyncio.Task | None = None
        self._last_mic_emit = 0.0
        self._last_report: dict | None = None
        self.tool_lock = asyncio.Lock()

    # ── lifecycle ────────────────────────────────────────────────

    def start(self):
        if self.task is None or self.task.done():
            self.task = asyncio.create_task(self.run())
        return self.task

    async def stop(self):
        self.stop_event.set()
        if self._prep_task and not self._prep_task.done():
            self._prep_task.cancel()
        if self.task and not self.task.done():
            self.task.cancel()
            try:
                await asyncio.wait_for(asyncio.shield(self.task), timeout=5)
            except (asyncio.CancelledError, asyncio.TimeoutError, Exception):
                pass

    async def _emit(self, event: str, data: dict):
        if not self.sio:
            return
        try:
            await self.sio.emit(event, data, room=self.sid)
        except Exception as e:
            log.debug(f"[EMIT] {event} failed: {e}")

    def _emit_now(self, event: str, data: dict):
        """Fire-and-forget emit from sync context."""
        if not self.sio:
            return
        try:
            asyncio.get_running_loop().create_task(self._emit(event, data))
        except RuntimeError:
            pass

    # ── mic input ───────────────────────────────────────────────

    def feed_browser_audio(self, data: bytes):
        """PCM chunk from browser mic → Gemini queue + answer buffer."""
        if not self.audio_queue or self.stop_event.is_set():
            return
        # echo-safe: drop mic while the model speaks
        if self._model_is_speaking or self._tools_running:
            return
        # A new candidate turn begins — stop suppressing model transcript text.
        self._script_transcript_active = False
        self._script_transcript_seen = False
        self._last_output_transcription = ""
        try:
            self.audio_queue.put_nowait({"data": data, "mime_type": "audio/pcm"})
        except asyncio.QueueFull:
            pass
        if self.examiner.awaiting_answer and len(self._answer_pcm) < MAX_ANSWER_BYTES:
            self._answer_pcm.extend(data)
        now = time.monotonic()
        if now - self._last_mic_emit >= 0.1:
            self._last_mic_emit = now
            self._emit_now("mic_level", {"level": _rms_level(data)})

    # ── answer capture ──────────────────────────────────────────

    def _capture_candidate_text(self, transcript: str) -> str:
        """Accumulate input transcription into the pending answer. Returns delta."""
        if transcript == self._last_input_transcription:
            return ""
        if transcript.startswith(self._last_input_transcription):
            delta = transcript[len(self._last_input_transcription):]
        else:
            delta = transcript
        self._last_input_transcription = transcript
        if delta and self.examiner.awaiting_answer:
            if self._answer_text and not self._answer_text.endswith(" "):
                self._answer_text += " "
            self._answer_text += delta
        return delta

    def _reset_answer_buffers(self):
        self._answer_text = ""
        self._answer_pcm.clear()
        self._last_input_transcription = ""

    def _eval_budget_ok(self) -> bool:
        cutoff = time.time() - 3600
        self._eval_times = [t for t in self._eval_times if t > cutoff]
        if len(self._eval_times) >= EVAL_LIMIT_PER_HOUR:
            return False
        self._eval_times.append(time.time())
        return True

    def _stash_current_answer(self, skip_if_empty: bool = True) -> bool:
        """Store the current answer + audio; scoring happens once per part."""
        ex = self.examiner
        if not ex.awaiting_answer:
            return False
        answer = self._answer_text.strip()
        pcm = bytes(self._answer_pcm)
        if not answer and len(pcm) < MIN_ANSWER_AUDIO_BYTES:
            if skip_if_empty:
                ex.skip_evaluation()
            self._reset_answer_buffers()
            return False
        ex.record_answer(answer)
        room = MAX_PART_AUDIO_BYTES - len(self._part_pcm)
        if room > 0 and pcm:
            self._part_pcm.extend(pcm[:room])
            gap = b"\x00\x00" * int(SEND_SAMPLE_RATE * 0.3)
            if len(self._part_pcm) + len(gap) <= MAX_PART_AUDIO_BYTES:
                self._part_pcm.extend(gap)
        self._reset_answer_buffers()
        return True

    async def _evaluate_current_part(self) -> dict | None:
        ex = self.examiner
        part = int(ex.part or 1)
        if part in ex.part_evaluations:
            return ex.part_evaluations[part]
        answers = ex.part_answers(part)
        if not answers:
            return None
        if not self._eval_budget_ok():
            return None
        await self._emit_state("evaluating")
        ev = await eval_mod.evaluate_part(answers, bytes(self._part_pcm), part)
        ex.record_part_evaluation(part, ev)
        self._part_pcm.clear()
        await self._emit("answer_evaluated", {"evaluation": ev})
        await self._emit_state("feedback")
        return ev

    # ── test state events ───────────────────────────────────────

    @staticmethod
    def _dashboard_data(progress: dict) -> dict:
        days = None
        exam_date = str(progress.get("exam_date") or "").strip()
        if exam_date:
            try:
                days = max(0, (date.fromisoformat(exam_date[:10]) - date.today()).days)
            except ValueError:
                days = None
        return {
            "progress": progress,
            "target_band": progress.get("target_band"),
            "days_until_exam": days,
        }

    def _test_state(self, phase: str, report: dict | None = None, prep_over: bool = False) -> dict:
        ex = self.examiner
        payload = ex.current_payload or {}
        prep_ends_at = None
        if (
            phase == "answering"
            and payload.get("kind") == "cue_card"
            and not prep_over
        ):
            seconds = int(payload.get("prep_time_seconds") or 60)
            prep_ends_at = (datetime.now() + timedelta(seconds=seconds)).isoformat()
        state = {
            "phase": phase,
            "mode": ex.mode,
            "part": payload.get("part", ex.part),
            "kind": payload.get("kind"),
            "question_index": payload.get("question_index"),
            "question_total": payload.get("question_total"),
            "payload": payload,
            "prep_ends_at": prep_ends_at,
            "answer_count": len(ex.answers),
        }
        if phase == "finished" and (report or self._last_report):
            state["report"] = report or self._last_report
        return state

    async def _emit_state(self, phase: str, report: dict | None = None):
        await self._emit("test_state", self._test_state(phase, report))

    # ── Gemini Live run loop ────────────────────────────────────

    async def run(self):
        if not os.getenv("GEMINI_API_KEY"):
            await self._emit("error", {"message": "GEMINI_API_KEY is not configured on the server."})
            await self._emit("connection_state", {"connected": False, "reason": "no_api_key"})
            return

        progress = None
        if self.client_id:
            try:
                progress = store.get_client(self.client_id)
            except Exception as e:
                log.warning(f"[RUN] progress load failed: {e}")
        system_prompt = build_examiner_prompt(progress)

        try:
            config = types.LiveConnectConfig(
                response_modalities=["AUDIO"],
                output_audio_transcription={},
                input_audio_transcription={},
                realtime_input_config=types.RealtimeInputConfig(
                    automatic_activity_detection=types.AutomaticActivityDetection(
                        # IELTS answers include thinking pauses — do not end the
                        # candidate's turn on a short gap. 2s of silence is the
                        # documented maximum and low sensitivity ignores breaths.
                        start_of_speech_sensitivity=types.StartSensitivity.START_SENSITIVITY_HIGH,
                        end_of_speech_sensitivity=types.EndSensitivity.END_SENSITIVITY_LOW,
                        prefix_padding_ms=500,
                        silence_duration_ms=2000,
                    )
                ),
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Charon")
                    )
                ),
                system_instruction=system_prompt,
                tools=build_tools(),
            )
        except Exception as e:
            log.error(f"[RUN] invalid Live config: {e}")
            await self._emit("error", {"message": f"Voice config error: {e}"})
            await self._emit("connection_state", {"connected": False, "reason": "config_error"})
            return

        retry_delay = 1
        is_reconnect = False
        _retry_count = 0

        while not self.stop_event.is_set():
            try:
                log.info(f"[RUN] connecting to Gemini Live ({self.sid[:8]})...")
                async with (
                    _get_client().aio.live.connect(model=MODEL, config=config) as session,
                    asyncio.TaskGroup() as tg,
                ):
                    self.session = session
                    self.audio_in_queue = asyncio.Queue(maxsize=200)
                    self.audio_queue = asyncio.Queue(maxsize=500)
                    self._model_is_speaking = False
                    self._tools_running = False
                    self._last_tool_start = 0.0
                    self._processed_fc_ids.clear()

                    tg.create_task(self.send_audio())
                    tg.create_task(self.receive_audio())
                    tg.create_task(self.play_audio())
                    tg.create_task(self._flag_watchdog())

                    if not is_reconnect and self.start_message:
                        await self.session.send_client_content(
                            turns=types.Content(
                                role="user",
                                parts=[types.Part(text=self.start_message)],
                            ),
                            turn_complete=True,
                        )
                        await self._emit_state("idle")

                    retry_delay = 1
                    _retry_count = 0
                    await self._emit("connection_state", {
                        "connected": True,
                        "reason": "reconnected" if is_reconnect else "connected",
                    })
                    await self._emit("speaking_state", {"state": "idle"})
                    await self.stop_event.wait()

            except asyncio.CancelledError:
                break
            except Exception as e:
                _retry_count += 1
                if self.stop_event.is_set():
                    break
                log.error(f"[RUN] connection error (attempt {_retry_count}/{MAX_RETRIES}): {e}")
                traceback.print_exc()
                self._model_is_speaking = False
                self._tools_running = False

                if _retry_count >= MAX_RETRIES:
                    log.error(f"[RUN] circuit breaker — giving up after {MAX_RETRIES} attempts")
                    await self._emit("error", {
                        "message": "Voice connection failed after several attempts. Check the API key and try again."
                    })
                    await self._emit("connection_state", {"connected": False, "reason": "circuit_breaker"})
                    await self._emit("speaking_state", {"state": "idle"})
                    break

                await self._emit("connection_state", {
                    "connected": False,
                    "reason": "reconnecting",
                    "attempt": _retry_count,
                    "max_retries": MAX_RETRIES,
                    "next_retry_in": retry_delay,
                })
                await self._emit("speaking_state", {"state": "idle"})

                import random
                actual = retry_delay + random.uniform(0, retry_delay * 0.3)
                await asyncio.sleep(actual)
                retry_delay = min(retry_delay * 2, 30)
                is_reconnect = True

    async def _flag_watchdog(self):
        while not self.stop_event.is_set():
            await asyncio.sleep(15)
            if self._tools_running and self._last_tool_start > 0 and time.time() - self._last_tool_start > 30:
                log.warning("[WATCHDOG] _tools_running stuck >30s — force-resetting")
                self._tools_running = False
                self._model_is_speaking = False
                self._last_tool_start = 0.0

    # ── mic → model ─────────────────────────────────────────────

    async def send_audio(self):
        consecutive_errors = 0
        while not self.stop_event.is_set():
            try:
                try:
                    msg = await asyncio.wait_for(self.audio_queue.get(), timeout=0.1)
                    await asyncio.wait_for(
                        self.session.send_realtime_input(
                            audio=types.Blob(data=msg["data"], mime_type=msg["mime_type"])
                        ),
                        timeout=5.0,
                    )
                    consecutive_errors = 0
                except asyncio.TimeoutError:
                    pass
            except (websockets.exceptions.ConnectionClosedError,
                    websockets.exceptions.ConnectionClosed) as e:
                log.warning(f"[SEND] session dead ({e}) — stopping")
                raise
            except Exception as e:
                consecutive_errors += 1
                if consecutive_errors >= 5:
                    log.warning(f"[SEND] {consecutive_errors} consecutive errors — stopping")
                    raise
                log.error(f"[SEND] error ({consecutive_errors}): {e}")
                await asyncio.sleep(0.1)

    # ── model → candidate ───────────────────────────────────────

    async def play_audio(self):
        _batch_buf = bytearray()
        _BATCH_TARGET = 4800
        _BATCH_MAX_WAIT = 0.08
        _last_flush = asyncio.get_event_loop().time()
        _last_audio_time = time.monotonic()
        _SILENCE_THRESHOLD = 4.0
        was_tools_running = False

        while not self.stop_event.is_set():
            try:
                data = await asyncio.wait_for(self.audio_in_queue.get(), timeout=0.1)
                _last_audio_time = time.monotonic()
                was_tools_running = bool(self._tools_running)
                await self._emit("mic_level", {"level": _rms_level(data)})
                _batch_buf.extend(data)
                now = asyncio.get_event_loop().time()
                if len(_batch_buf) >= _BATCH_TARGET or (now - _last_flush) >= _BATCH_MAX_WAIT:
                    if _batch_buf:
                        await self._emit("audio_data", {"data": base64.b64encode(bytes(_batch_buf)).decode()})
                        _batch_buf.clear()
                        _last_flush = now
            except asyncio.TimeoutError:
                if _batch_buf:
                    await self._emit("audio_data", {"data": base64.b64encode(bytes(_batch_buf)).decode()})
                    _batch_buf.clear()
                    _last_flush = asyncio.get_event_loop().time()

                elapsed_silence = time.monotonic() - _last_audio_time
                if self._tools_running:
                    was_tools_running = True
                elif was_tools_running and elapsed_silence > 1.0:
                    was_tools_running = False
                elif self._model_is_speaking and elapsed_silence >= _SILENCE_THRESHOLD:
                    self._model_is_speaking = False
                    await self._emit("speaking_state", {"state": "idle"})

    # ── model output: transcriptions + tools ────────────────────

    async def receive_audio(self):
        self._model_is_speaking = False
        try:
            while not self.stop_event.is_set():
                turn = self.session.receive()
                async for response in turn:
                    if self.stop_event.is_set():
                        break

                    if data := response.data:
                        if not self._model_is_speaking:
                            self._model_is_speaking = True
                            await self._emit("speaking_state", {"state": "model"})
                        try:
                            self.audio_in_queue.put_nowait(data)
                        except asyncio.QueueFull:
                            try:
                                self.audio_in_queue.get_nowait()
                            except asyncio.QueueEmpty:
                                pass
                            self.audio_in_queue.put_nowait(data)

                    if response.server_content:
                        if response.server_content.input_transcription:
                            if not self._model_is_speaking:
                                await self._emit("speaking_state", {"state": "user"})
                            transcript = response.server_content.input_transcription.text
                            delta = self._capture_candidate_text(transcript) if transcript else ""
                            if delta:
                                await self._emit("transcription", {"sender": "Candidate", "text": delta})

                        if response.server_content.output_transcription:
                            transcript = response.server_content.output_transcription.text
                            if self._script_transcript_active:
                                # The exact tool script was already emitted; the model is
                                # now speaking it. Suppress the duplicate live transcript.
                                self._script_transcript_seen = True
                            elif transcript and transcript != self._last_output_transcription:
                                delta = transcript
                                if transcript.startswith(self._last_output_transcription):
                                    delta = transcript[len(self._last_output_transcription):]
                                self._last_output_transcription = transcript
                                if delta:
                                    await self._emit("transcription", {"sender": "Examiner", "text": delta})

                        if response.server_content.turn_complete:
                            if self._script_transcript_active and self._script_transcript_seen:
                                self._script_transcript_active = False
                                self._script_transcript_seen = False
                                self._last_output_transcription = ""
                            elif not self._script_transcript_active:
                                self._last_output_transcription = ""

                    if response.tool_call:
                        function_responses = []
                        tasks = []
                        pending_fcs = []
                        for fc in response.tool_call.function_calls:
                            if fc.id in self._processed_fc_ids:
                                continue
                            self._processed_fc_ids.add(fc.id)
                            tasks.append(self._dispatch_tool(fc))
                            pending_fcs.append(fc)

                        if tasks:
                            self._tools_running = True
                            self._last_tool_start = time.time()
                            try:
                                raw = await asyncio.wait_for(
                                    asyncio.gather(*tasks, return_exceptions=True),
                                    timeout=120,
                                )
                            except asyncio.TimeoutError:
                                raw = [
                                    types.FunctionResponse(
                                        id=fc.id, name=fc.name,
                                        response={"success": False, "error": f"Tool {fc.name} timed out."},
                                    )
                                    for fc in pending_fcs
                                ]
                            for fc, result in zip(pending_fcs, raw):
                                if isinstance(result, Exception):
                                    log.error(f"[TOOL] {fc.name} failed: {result}", exc_info=result)
                                    result = types.FunctionResponse(
                                        id=fc.id, name=fc.name,
                                        response={"success": False, "error": f"Tool {fc.name} failed: {result}"},
                                    )
                                if result is None:
                                    result = types.FunctionResponse(
                                        id=fc.id, name=fc.name,
                                        response={"success": False, "error": f"Tool {fc.name} returned nothing."},
                                    )
                                function_responses.append(result)

                        if function_responses:
                            script_text = " ".join(
                                str(fr.response.get("result") or "").strip()
                                for fc, fr in zip(pending_fcs, function_responses)
                                if fc.name in SPEECH_TOOLS
                                and isinstance(fr.response, dict)
                                and fr.response.get("success")
                                and str(fr.response.get("result") or "").strip()
                            ).strip()
                            if script_text:
                                await self._emit("transcription", {
                                    "sender": "Examiner", "text": script_text, "final": True,
                                })
                                self._script_transcript_active = True
                                self._last_output_transcription = ""
                            try:
                                await asyncio.wait_for(
                                    self.session.send_tool_response(function_responses=function_responses),
                                    timeout=10,
                                )
                            except Exception as e:
                                log.error(f"[TOOL] send_tool_response failed: {e}")
                                self._model_is_speaking = False
                                self._tools_running = False
                                break
                            self._model_is_speaking = True
                            self._tools_running = False
                        else:
                            self._tools_running = False

        except (websockets.exceptions.ConnectionClosedError,
                websockets.exceptions.ConnectionClosed) as e:
            log.warning(f"[RECV] session disconnected: {e}")
            self._model_is_speaking = False
            self._tools_running = False
            raise
        except Exception as e:
            log.error(f"[RECV] error: {e}")
            traceback.print_exc()
            self._model_is_speaking = False
            self._tools_running = False
            raise

    # ── tool dispatch (the 7 examiner tools only) ───────────────

    async def _dispatch_tool(self, fc) -> types.FunctionResponse:
        name = fc.name
        args = fc.args or {}
        started = time.monotonic()
        await self._emit("tool_status", {"tool": name, "status": "start"})
        try:
            async with self.tool_lock:
                result_text = await self._run_tool(name, args)
            await self._emit("tool_status", {
                "tool": name, "status": "done",
                "duration_ms": int((time.monotonic() - started) * 1000),
            })
            return types.FunctionResponse(
                id=fc.id, name=name,
                response={"success": True, "result": result_text},
            )
        except Exception as e:
            log.error(f"[TOOL] {name} error: {e}")
            traceback.print_exc()
            await self._emit("tool_status", {"tool": name, "status": "error"})
            return types.FunctionResponse(
                id=fc.id, name=name,
                response={"success": False, "error": str(e)},
            )

    async def run_ui_tool(self, name: str, args: dict) -> dict:
        """Execute an interface-triggered tool, then have the model narrate it."""
        if self.stop_event.is_set():
            return {"ok": False, "error": "session_stopped"}
        try:
            async with self.tool_lock:
                text = await self._run_tool(name, args)
        except Exception as e:
            log.error(f"[UI TOOL] {name} failed: {e}")
            return {"ok": False, "error": str(e)}
        if text and self.session and not self.stop_event.is_set():
            await self.inject_text(
                f"SYSTEM: The candidate pressed the '{name}' control. "
                f"Read this aloud word for word, then continue: \"{text}\""
            )
        return {"ok": True, "result": text}

    async def _run_tool(self, name: str, args: dict) -> str:
        ex = self.examiner

        if name == "start_test":
            payload = ex.start(args.get("mode", "full"), args.get("topic"))
            if not payload:
                return "No questions available for that topic. Tell the candidate to try a different topic."
            self._reset_answer_buffers()
            self._part_pcm.clear()
            self._last_report = None
            await self._emit_state("answering")
            self._maybe_start_prep_timer(payload)
            return ex.spoken_question(payload)

        if name == "next_question":
            if ex.awaiting_answer and not self._stash_current_answer(skip_if_empty=False):
                return (
                    "I didn't catch a clear answer to that question. "
                    "Ask the candidate to answer it again — do NOT move on."
                )
            feedback = ""
            if ex.current_part_finished() and ex.part not in ex.part_evaluations:
                ev = await self._evaluate_current_part()
                if ev:
                    feedback = ex.spoken_feedback(ev)
            payload = ex.advance()
            if payload:
                self._reset_answer_buffers()
                await self._emit_state("answering")
                self._maybe_start_prep_timer(payload)
                return (feedback + " " + ex.spoken_question(payload)).strip()
            return await self._finish_inner()

        if name == "repeat_question":
            if ex.current_payload is None:
                return "No test is running yet. Greet the candidate and ask what kind of test they want."
            return ex.spoken_repeat()

        if name == "finish_test":
            self._stash_current_answer()
            if ex.part and ex.part not in ex.part_evaluations:
                await self._evaluate_current_part()
            return await self._finish_inner()

        if name == "set_goal":
            info = ex.set_goal(args.get("target_band"), args.get("exam_date"))
            progress = ex.get_progress() if ex.client_id else {}
            await self._emit("client_progress", {"progress": progress})
            return (
                f"Tell the candidate you've noted their target band of "
                f"{band_words(info.get('target_band'))} and exam date "
                f"{info.get('exam_date') or 'not set yet'}, then continue the test naturally."
            )

        if name == "get_progress":
            progress = ex.get_progress()
            if self._last_report:
                avg = progress.get("average_bands") or {}
                if not avg.get("speaking"):
                    avg["speaking"] = self._last_report.get("overall_band")
                    avg["overall"] = avg["speaking"]
                    progress["average_bands"] = avg
                if not progress.get("weak_areas") and self._last_report.get("weakest_criterion"):
                    progress["weak_areas"] = [self._last_report["weakest_criterion"]]
            await self._emit("client_progress", {"progress": progress})
            await self._emit("panel_open", {
                "panelType": "IELTSDashboard", "direction": "right",
                "data": self._dashboard_data(progress),
            })
            avg_band = (progress.get("average_bands") or {}).get("speaking")
            target = band_words(progress.get("target_band", 7.0))
            streak = int(progress.get("streak_days") or 0)
            streak_txt = (
                f"a streak of {streak} days" if streak else "no practice streak yet"
            )
            weak = ", ".join(progress.get("weak_areas") or [])
            if avg_band:
                summary = (
                    f"Tell the candidate, warmly: their speaking average is band "
                    f"{band_words(avg_band)} out of nine, their target is {target}, "
                    f"{streak_txt}, and the area to work on is {weak or 'not identified yet'}."
                )
            else:
                summary = (
                    "Tell the candidate, warmly, that this is their first scored session, "
                    f"so there is no average yet. Their target is {target} and they have "
                    f"{streak_txt}. "
                )
            return summary + " The dashboard is open on screen. Then continue naturally with the test."

        return f"Unknown tool: {name}"

    async def _finish_inner(self) -> str:
        ex = self.examiner
        if self._last_report:
            report = self._last_report
        else:
            report = ex.build_report()
            try:
                ex.save(report)
            except Exception as e:
                log.warning(f"[FINISH] save failed: {e}")
            self._last_report = report
        await self._emit("report_ready", {"report": report})
        await self._emit("panel_open", {
            "panelType": "IELTSReport", "direction": "right", "data": report,
        })
        await self._emit_state("finished", report)
        return ex.spoken_report(report)

    def _maybe_start_prep_timer(self, payload: dict):
        if payload.get("kind") != "cue_card":
            return
        if self._prep_task and not self._prep_task.done():
            self._prep_task.cancel()
        seconds = int(payload.get("prep_time_seconds") or 60)
        self._prep_task = asyncio.create_task(self._prep_timer(seconds))

    async def _prep_timer(self, seconds: int):
        try:
            await asyncio.sleep(seconds)
        except asyncio.CancelledError:
            return
        if self.stop_event.is_set():
            return
        state = self._test_state("answering", prep_over=True)
        state["prep_over"] = True
        await self._emit("test_state", state)
        await self.inject_text(
            "SYSTEM: The candidate's one minute of preparation time has ended. "
            "Immediately read aloud EXACTLY: 'Your preparation time is now over. "
            "You have two minutes to speak. Please begin.' Then stay silent while "
            "the candidate speaks."
        )

    async def inject_text(self, text: str) -> bool:
        if not self.session or self.stop_event.is_set():
            return False
        try:
            await asyncio.wait_for(
                self.session.send_client_content(
                    turns=types.Content(role="user", parts=[types.Part(text=text)]),
                    turn_complete=True,
                ),
                timeout=10,
            )
            return True
        except Exception as e:
            log.warning(f"[INJECT] failed: {e}")
            return False
