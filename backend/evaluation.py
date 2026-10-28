"""Answer evaluation pipeline.

Two evaluations run in parallel:
  1. Text criteria (Fluency, Lexical, Grammar)  -> DeepSeek API
  2. Pronunciation from recorded audio          -> Gemini multimodal (WAV)

Both have independent fallbacks so a single provider outage never blocks the test.
"""
import asyncio
import io
import json
import os
import re
import wave

from dotenv import load_dotenv

load_dotenv()

import httpx
from google import genai
from google.genai import types

from logger import log
from prompts import build_pronunciation_prompt, build_text_evaluation_prompt
from rubric import CRITERIA, clamp_band, overall_band

DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
PRONUNCIATION_MODEL = os.getenv("PRONUNCIATION_MODEL", "gemini-2.5-flash")
SEND_SAMPLE_RATE = 16000
MIN_AUDIO_SECONDS = 2.0

_GEMINI_CLIENT = None


def _gemini_client():
    global _GEMINI_CLIENT
    if _GEMINI_CLIENT is None:
        _GEMINI_CLIENT = genai.Client(api_key=os.getenv("GEMINI_API_KEY", ""))
    return _GEMINI_CLIENT


def extract_json(text: str) -> dict | None:
    """Pull the first JSON object out of a model response (fenced or loose)."""
    if not text:
        return None
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if fence:
        text = fence.group(1)
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


async def _deepseek_chat(messages, temperature=0.4, max_tokens=1600) -> str:
    api_key = os.getenv("DEEPSEEK_API_KEY", "")
    if not api_key:
        return ""
    async with httpx.AsyncClient(timeout=45.0) as client:
        resp = await client.post(
            "https://api.deepseek.com/v1/chat/completions",
            json={
                "model": DEEPSEEK_MODEL,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
            headers={"Authorization": f"Bearer {api_key}"},
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("choices", [{}])[0].get("message", {}).get("content", "") or ""


def _pcm_to_wav(pcm: bytes) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SEND_SAMPLE_RATE)
        wf.writeframes(pcm)
    return buf.getvalue()


def _heuristic_text_evaluation(answer: str) -> dict:
    """Offline fallback when DeepSeek is unavailable."""
    wc = len(answer.split()) if answer else 0
    lower = (answer or "").lower()
    fillers = sum(lower.count(w) for w in [" um ", " uh ", " like ", "you know", "actually", "basically"])
    if wc < 20:
        base = 4.0
    elif wc < 50:
        base = 5.0
    elif wc < 100:
        base = 5.5
    elif wc < 180:
        base = 6.0
    else:
        base = 6.5
    if fillers > 5:
        base -= 0.5
    return {
        "band_scores": {
            "fluency_coherence": base,
            "lexical_resource": base,
            "grammatical_range": max(3.0, base - 0.5),
            "pronunciation": base,
        },
        "strengths": ["You attempted the full question with a complete answer"],
        "improvements": [{
            "issue": "Expand your answer with specific details, an example and a longer explanation",
            "example_from_response": answer[:120] if answer else "(no answer captured)",
            "better_version": "Add: a reason, a concrete example, and how it connects to the question",
            "band_impact": "More developed answers move you toward Band 6-7",
        }],
        "vocabulary_feedback": {"repetitions_found": [], "suggested_upgrades": []},
        "grammar_errors": [],
        "corrected_transcript": answer,
        "band7_tip": "Extend every answer: give a direct answer, one reason, one example, one closing thought.",
        "filler_words_count": fillers,
        "word_count": wc,
        "_degraded": "text-evaluator-unavailable",
    }


async def _text_evaluation(answer: str, part: int, question: str) -> dict:
    prompt = build_text_evaluation_prompt(answer, part, question)
    for attempt in range(2):
        try:
            raw = await _deepseek_chat(
                [{"role": "user", "content": prompt}],
                temperature=0.3 if attempt == 0 else 0.1,
            )
            parsed = extract_json(raw)
            if parsed and isinstance(parsed.get("band_scores"), dict):
                return parsed
            log.warning(f"[EVAL] text JSON parse failed (attempt {attempt + 1})")
        except Exception as e:
            log.warning(f"[EVAL] text evaluation failed (attempt {attempt + 1}): {e}")
            await asyncio.sleep(0.5)
    return _heuristic_text_evaluation(answer)


def _heuristic_pronunciation() -> dict:
    return {
        "pronunciation_band": None,
        "intelligibility": "unknown",
        "strengths": [],
        "issues": [],
        "notes": "Audio recording unavailable — pronunciation estimated from the transcript only.",
        "_degraded": "audio-unavailable",
    }


async def _pronunciation_evaluation(pcm: bytes, transcript: str, part: int) -> dict:
    if not pcm or len(pcm) < SEND_SAMPLE_RATE * 2 * MIN_AUDIO_SECONDS:
        return _heuristic_pronunciation()
    try:
        wav = _pcm_to_wav(pcm)
        prompt = build_pronunciation_prompt(transcript, part)
        client = _gemini_client().aio
        resp = await client.models.generate_content(
            model=PRONUNCIATION_MODEL,
            contents=[
                prompt,
                types.Part.from_bytes(data=wav, mime_type="audio/wav"),
            ],
        )
        parsed = extract_json(resp.text or "")
        if parsed and parsed.get("pronunciation_band") is not None:
            parsed["pronunciation_band"] = clamp_band(parsed["pronunciation_band"])
            return parsed
        log.warning("[EVAL] pronunciation JSON parse failed")
    except Exception as e:
        log.warning(f"[EVAL] pronunciation evaluation failed: {e}")
    return _heuristic_pronunciation()


async def evaluate_answer(answer: str, pcm: bytes, part: int, question: str) -> dict:
    """Run text + pronunciation evaluations in parallel and merge them."""
    text_task = _text_evaluation(answer or "", part, question or "")
    pron_task = _pronunciation_evaluation(pcm or b"", answer or "", part)
    text_result, pron_result = await asyncio.gather(text_task, pron_task)

    scores = {}
    for crit in CRITERIA:
        scores[crit] = clamp_band((text_result.get("band_scores") or {}).get(crit, 0))

    pron_band = pron_result.get("pronunciation_band")
    if pron_band is not None:
        scores["pronunciation"] = clamp_band(pron_band)
    elif isinstance(scores.get("pronunciation"), (int, float)) and scores["pronunciation"] == 0:
        scores["pronunciation"] = 5.0

    evaluation = {
        "band_scores": scores,
        "overall_band": overall_band(scores),
        "strengths": text_result.get("strengths") or [],
        "improvements": text_result.get("improvements") or [],
        "vocabulary_feedback": text_result.get("vocabulary_feedback") or {},
        "grammar_errors": text_result.get("grammar_errors") or [],
        "corrected_transcript": text_result.get("corrected_transcript") or answer or "",
        "band7_tip": text_result.get("band7_tip") or "",
        "filler_words_count": text_result.get("filler_words_count", 0),
        "word_count": text_result.get("word_count", len((answer or "").split())),
        "pronunciation_detail": pron_result,
        "part": part,
        "question": question,
    }
    degraded = []
    if text_result.get("_degraded"):
        degraded.append(text_result["_degraded"])
    if pron_result.get("_degraded"):
        degraded.append(pron_result["_degraded"])
    if degraded:
        evaluation["degraded"] = degraded
    return evaluation
