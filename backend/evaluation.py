"""Answer evaluation pipeline.

Two evaluations run in parallel:
  1. Text criteria (Fluency, Lexical, Grammar)  -> Gemini (default) or DeepSeek
  2. Pronunciation from recorded audio          -> Gemini multimodal (WAV)

Gemini is the default text scorer because the app already requires a working
GEMINI_API_KEY (voice + pronunciation), so scoring never silently degrades to
word-count heuristics. DeepSeek is used only when TEXT_EVAL_PROVIDER=deepseek
and a key is configured. Both providers have independent fallbacks.
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
from prompts import (
    build_part_evaluation_prompt,
    build_pronunciation_prompt,
    build_text_evaluation_prompt,
)
from rubric import CRITERIA, clamp_band, overall_band

DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
TEXT_EVAL_PROVIDER = (os.getenv("TEXT_EVAL_PROVIDER") or "gemini").strip().lower()
TEXT_EVAL_MODEL = os.getenv("TEXT_EVAL_MODEL", "gemini-2.5-flash")
PRONUNCIATION_MODEL = os.getenv("PRONUNCIATION_MODEL", "gemini-2.5-flash")
SEND_SAMPLE_RATE = 16000
MIN_AUDIO_SECONDS = 2.0

_GEMINI_CLIENT = None

FILLER_PATTERNS = [
    r"\bum+\b", r"\buh+\b", r"\ber+\b", r"\bah+\b", r"\blike\b",
    r"\byou know\b", r"\bi mean\b", r"\bsort of\b", r"\bkind of\b",
    r"\bbasically\b", r"\bactually\b",
]

COMPLEX_MARKERS = [
    "because", "although", "though", "whereas", "while", "which", "who",
    "whose", "if", "unless", "since", "so that", "in order to", "despite",
    "however", "therefore", "for example", "on the other hand", "whenever",
    "whether", "even though", "as long as",
]

DISCOURSE_MARKERS = [
    "first", "then", "next", "finally", "however", "for example",
    "in addition", "to be honest", "i suppose", "in my opinion", "actually",
    "on the other hand", "overall", "to sum up",
]

STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "so", "to", "of", "in", "on", "at",
    "for", "with", "by", "from", "as", "is", "am", "are", "was", "were", "be",
    "been", "being", "do", "does", "did", "have", "has", "had", "i", "you",
    "he", "she", "it", "we", "they", "me", "him", "her", "us", "them", "my",
    "your", "his", "her", "its", "our", "their", "this", "that", "these",
    "those", "there", "here", "not", "no", "yes", "very", "quite", "just",
    "really", "also", "can", "could", "would", "should", "will", "shall",
    "may", "might", "must", "about", "like", "well", "think", "know", "go",
    "get", "make", "much", "many", "lot", "thing", "things", "one", "two",
    "some", "any", "all", "more", "most", "other", "than", "too", "only",
    "then", "now", "when", "what", "who", "how", "why", "where", "if",
}


def _gemini_client():
    global _GEMINI_CLIENT
    if _GEMINI_CLIENT is None:
        _GEMINI_CLIENT = genai.Client(api_key=os.getenv("GEMINI_API_KEY", ""))
    return _GEMINI_CLIENT


def eval_mode() -> str:
    """Which engine will score text right now: gemini | deepseek | heuristic."""
    has_gemini = bool(os.getenv("GEMINI_API_KEY"))
    has_deepseek = bool(os.getenv("DEEPSEEK_API_KEY"))
    if TEXT_EVAL_PROVIDER == "deepseek":
        if has_deepseek:
            return "deepseek"
        return "gemini" if has_gemini else "heuristic"
    if has_gemini:
        return "gemini"
    return "deepseek" if has_deepseek else "heuristic"


async def _gemini_json(prompt: str) -> str:
    client = _gemini_client().aio
    resp = await client.models.generate_content(
        model=TEXT_EVAL_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.2,
            max_output_tokens=8192,
            # 2.5 Flash thinks by default; thinking tokens were truncating the
            # JSON verdict. Scoring is deterministic enough without them.
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )
    return resp.text or ""


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


async def _deepseek_chat(messages, temperature=0.4, max_tokens=4096) -> str:
    api_key = os.getenv("DEEPSEEK_API_KEY", "")
    if not api_key:
        return ""
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            "https://api.deepseek.com/v1/chat/completions",
            json={
                "model": DEEPSEEK_MODEL,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "response_format": {"type": "json_object"},
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


GRAMMAR_PATTERNS = [
    (r"\bi am agree\b", "I agree", "verb form"),
    (r"\b(he|she|it) don't\b", r"\1 doesn't", "subject-verb agreement"),
    (r"\b(they|we|i) has\b", r"\1 have", "subject-verb agreement"),
    (r"\b(i|you|we|they) doesn't\b", r"\1 don't", "subject-verb agreement"),
    (r"\bpeoples\b", "people", "word formation"),
    (r"\binformations\b", "information", "word formation"),
    (r"\badvices\b", "advice", "word formation"),
    (r"\bmore better\b", "better", "comparative"),
    (r"\bmost easiest\b", "easiest", "superlative"),
    (r"\bdidn't went\b", "didn't go", "past tense"),
    (r"\bthere is many\b", "there are many", "agreement"),
    (r"\bthere was many\b", "there were many", "agreement"),
    (r"\bcan able to\b", "can / be able to", "double modal"),
    (r"\bdiscuss about\b", "discuss", "preposition"),
    (r"\bexplain me\b", "explain to me", "preposition"),
    (r"\bdepends of\b", "depends on", "preposition"),
    (r"\binterested about\b", "interested in", "preposition"),
    (r"\bin the same time\b", "at the same time", "preposition"),
    (r"\bon the other side\b", "on the other hand", "phrase"),
]

VOCAB_UPGRADES = {
    "good": ("decent", "impressive"),
    "very": ("particularly", "exceptionally"),
    "big": ("substantial", "considerable"),
    "nice": ("pleasant", "delightful"),
    "thing": ("aspect", "element"),
    "bad": ("poor", "problematic"),
    "really": ("genuinely", "particularly"),
    "happy": ("pleased", "thrilled"),
    "like": ("enjoy", "appreciate"),
    "important": ("significant", "crucial"),
}


def _text_metrics(answer: str) -> dict:
    text = answer or ""
    lower = text.lower()
    words = re.findall(r"[A-Za-z']+", text)
    wc = len(words)
    sentences = [s for s in re.split(r"[.!?]+", text) if s.strip()]
    fillers = sum(len(re.findall(p, lower)) for p in FILLER_PATTERNS)
    content = [w.lower() for w in words if w.lower() not in STOPWORDS]
    counts: dict[str, int] = {}
    for w in content:
        counts[w] = counts.get(w, 0) + 1
    reps = sorted(((w, c) for w, c in counts.items() if c >= 3), key=lambda x: -x[1])[:3]
    ttr = (len({w.lower() for w in words}) / wc) if wc else 0.0
    complex_hits = [m for m in COMPLEX_MARKERS if m in lower]
    discourse = [m for m in DISCOURSE_MARKERS if m in lower]
    reason_markers = [m for m in ("because", "since", "so that") if m in lower]
    if re.search(r"\bas\b", lower):
        reason_markers.append("as")
    example_markers = [m for m in ("for example", "for instance", "such as", "last ", "once ") if m in lower]
    return {
        "words": words, "wc": wc, "sentences": sentences, "fillers": fillers,
        "reps": reps, "ttr": ttr, "complex_hits": complex_hits,
        "discourse": discourse, "reason_markers": reason_markers,
        "example_markers": example_markers,
        "developed": bool(reason_markers) and bool(example_markers),
    }


def _find_grammar_errors(answer: str) -> list[dict]:
    errors = []
    for pattern, replacement, kind in GRAMMAR_PATTERNS:
        m = re.search(pattern, answer or "", flags=re.I)
        if not m:
            continue
        snippet = m.group(0)
        correction = re.sub(pattern, replacement, snippet, flags=re.I)
        errors.append({"error": snippet, "correction": correction, "type": kind})
        if len(errors) >= 8:
            break
    return errors


def _heuristic_text_evaluation(answer: str) -> dict:
    """Offline fallback when no text evaluator is reachable.

    Still produces per-criterion reasons and next steps from the actual answer
    (never a bare word-count verdict), and flags itself as degraded.
    """
    m = _text_metrics(answer)
    wc = m["wc"]
    errors = _find_grammar_errors(answer or "")

    if wc < 15:
        base = 4.0
    elif wc < 30:
        base = 4.5
    elif wc < 50:
        base = 5.0
    elif wc < 80:
        base = 5.5
    elif wc < 120:
        base = 6.0
    else:
        base = 6.5

    if m["developed"] and wc >= 50:
        base += 0.5
    if len(m["complex_hits"]) >= 3 and len(errors) <= 2:
        base += 0.5
    if wc >= 20 and (m["fillers"] >= 5 or m["fillers"] / wc > 0.08):
        base -= 0.5
    if m["reps"] and m["reps"][0][1] >= max(4, wc * 0.08):
        base -= 0.5
    base = max(3.0, min(7.5, base))

    fc = base
    lr = base - (0.5 if (m["ttr"] < 0.35 or len(m["reps"]) >= 2) else 0.0)
    gra = base - (0.5 if len(errors) >= 3 else 0.0) + (0.5 if len(m["complex_hits"]) >= 2 else 0.0)
    if wc < 20:
        gra -= 0.5
    pr = base

    scores = {
        "fluency_coherence": round(clamp_band(fc) * 2) / 2,
        "lexical_resource": round(clamp_band(lr) * 2) / 2,
        "grammatical_range": round(clamp_band(gra) * 2) / 2,
        "pronunciation": round(clamp_band(pr) * 2) / 2,
    }

    first_sentence = (m["sentences"][0][:140] if m["sentences"] else (answer or "")[:140]).strip()
    rep_word, rep_count = (m["reps"][0] if m["reps"] else ("", 0))
    top_err = errors[0] if errors else None
    filler_rate = (m["fillers"] / wc) if wc else 0.0

    def _next(band):
        return f"{min(9.0, band + 0.5):.1f}"

    if m["fillers"] >= 5:
        fc_reason = (
            f"{m['fillers']} filler words or hesitation sounds in {wc} words "
            f"interrupt the flow of the answer."
        )
        fc_evidence = first_sentence
    elif wc < 50:
        fc_reason = (
            f"The answer is only {wc} words, so it does not sustain a longer turn "
            f"or fully develop the topic."
        )
        fc_evidence = first_sentence
    else:
        fc_reason = (
            "The answer is coherent, but limited linking and development hold it "
            f"below Band {_next(scores['fluency_coherence'])}."
        )
        fc_evidence = first_sentence

    if rep_word:
        lr_reason = (
            f"'{rep_word}' is repeated {rep_count} times, so the vocabulary range "
            "stays basic."
        )
        lr_evidence = first_sentence
    elif m["ttr"] < 0.4:
        lr_reason = (
            "Vocabulary is repetitive and mostly everyday words; there are no less "
            "common or idiomatic items."
        )
        lr_evidence = first_sentence
    else:
        lr_reason = (
            "Vocabulary is adequate for the topic, but precision and less common "
            "word choices are limited."
        )
        lr_evidence = first_sentence

    if top_err:
        gra_reason = (
            f"{len(errors)} clear grammar error(s), e.g. '{top_err['error']}', limit "
            "accuracy and the range of structures."
        )
        gra_evidence = top_err["error"]
    elif len(m["complex_hits"]) < 2:
        gra_reason = (
            "No clear grammar errors were found, but the answer uses mostly simple "
            "structures."
        )
        gra_evidence = first_sentence
    else:
        gra_reason = (
            "Grammar is mostly accurate with some complex structures; a few errors "
            f"keep it below Band {_next(scores['grammatical_range'])}."
        )
        gra_evidence = first_sentence

    pr_reason = (
        "No audio was analysed, so pronunciation is a text-only estimate; the real "
        "score comes from the recording."
    )
    pr_next = (
        "Speak for at least 10 seconds close to the microphone so pronunciation can "
        "be scored from the recording."
    )

    criterion_feedback = {
        "fluency_coherence": {
            "reason": fc_reason,
            "evidence": fc_evidence,
            "next_step": "Plan 2-3 sentences: direct answer, one reason with 'because', one example with 'for example'.",
        },
        "lexical_resource": {
            "reason": lr_reason,
            "evidence": lr_evidence,
            "next_step": (
                f"Replace basic words such as '{rep_word or 'good'}' with one precise "
                "alternative and add one idiomatic phrase."
            ),
        },
        "grammatical_range": {
            "reason": gra_reason,
            "evidence": gra_evidence,
            "next_step": (
                f"Fix '{top_err['error']}' and add one complex sentence with "
                "'although', 'which' or 'if'."
                if top_err else
                "Add one complex sentence with 'although' or 'which' to each answer."
            ),
        },
        "pronunciation": {
            "reason": pr_reason,
            "evidence": "",
            "next_step": pr_next,
        },
    }

    upgrades = []
    lowered = (answer or "").lower()
    for word, (better, best) in VOCAB_UPGRADES.items():
        if re.search(rf"\b{re.escape(word)}\b", lowered):
            upgrades.append({"used": word, "better": better, "best": best})
        if len(upgrades) >= 3:
            break

    strengths = []
    if m["developed"]:
        strengths.append("You supported your answer with a reason and an example.")
    if len(m["complex_hits"]) >= 2:
        strengths.append(
            f"You attempted complex structures ({', '.join(m['complex_hits'][:3])})."
        )
    if m["ttr"] >= 0.5 and wc >= 40:
        strengths.append("Your vocabulary varied across the answer.")
    if not errors and wc >= 40:
        strengths.append("No clear grammar errors were detected.")
    if not strengths:
        strengths.append("You responded directly to the question.")

    improvements = []
    if rep_word:
        improvements.append({
            "issue": "You repeat the same basic word instead of paraphrasing.",
            "example_from_response": rep_word,
            "better_version": f"{rep_word} -> {VOCAB_UPGRADES.get(rep_word, ('a more precise word', 'a sophisticated alternative'))[0]}",
            "band_impact": "Lexical Resource: +0.5 by paraphrasing",
        })
    if top_err:
        improvements.append({
            "issue": f"Grammar error ({top_err['type']}).",
            "example_from_response": top_err["error"],
            "better_version": top_err["correction"],
            "band_impact": "Grammatical Range & Accuracy: +0.5 with accuracy fixes",
        })
    if not m["developed"] or wc < 60:
        improvements.append({
            "issue": "The answer is under-developed — it needs a reason and an example.",
            "example_from_response": first_sentence,
            "better_version": f"{first_sentence} because ... For example, ...",
            "band_impact": "Fluency & Coherence: +0.5 by extending the turn",
        })
    if not improvements:
        improvements.append({
            "issue": "Push for more precision and range.",
            "example_from_response": first_sentence,
            "better_version": "Swap two basic words for precise alternatives and add one idiomatic phrase.",
            "band_impact": "Lexical Resource: +0.5",
        })

    weakest = min(scores, key=lambda c: scores[c])
    weakest_next = criterion_feedback[weakest]["next_step"]
    why_summary = (
        f"Your Band {overall_band(scores)} is limited mainly by {weakest.replace('_', ' ')} "
        f"({scores[weakest]:.1f}). Fastest gain: {weakest_next}"
    )

    corrected = answer or ""
    for pattern, replacement, _kind in GRAMMAR_PATTERNS:
        corrected = re.sub(pattern, replacement, corrected, flags=re.I)

    return {
        "band_scores": scores,
        "criterion_feedback": criterion_feedback,
        "why_band_summary": why_summary,
        "strengths": strengths[:3],
        "improvements": improvements[:3],
        "vocabulary_feedback": {
            "repetitions_found": [w for w, _c in m["reps"]],
            "suggested_upgrades": upgrades,
        },
        "grammar_errors": errors,
        "corrected_transcript": corrected,
        "band7_tip": weakest_next,
        "filler_words_count": m["fillers"],
        "word_count": wc,
        "_degraded": "text-evaluator-unavailable",
        "_provider": "heuristic",
    }


async def _text_evaluation(
    answer: str, part: int, question: str, prompt: str | None = None
) -> dict:
    prompt = prompt or build_text_evaluation_prompt(answer, part, question)
    primary = eval_mode()
    if primary == "gemini":
        order = ["gemini", "deepseek"]
    elif primary == "deepseek":
        order = ["deepseek", "gemini"]
    else:
        order = []

    for provider in order:
        for attempt in range(2):
            try:
                if provider == "gemini":
                    raw = await _gemini_json(prompt)
                else:
                    raw = await _deepseek_chat(
                        [{"role": "user", "content": prompt}],
                        temperature=0.2 if attempt == 0 else 0.0,
                    )
                parsed = extract_json(raw)
                if parsed and isinstance(parsed.get("band_scores"), dict):
                    parsed["_provider"] = provider
                    return parsed
                log.warning(
                    f"[EVAL] {provider} JSON parse failed "
                    f"(attempt {attempt + 1}, len={len(raw or '')})"
                )
            except Exception as e:
                log.warning(f"[EVAL] {provider} evaluation failed (attempt {attempt + 1}): {e}")
                break
            await asyncio.sleep(0.4)

    log.warning("[EVAL] all text evaluators unavailable — using local analysis")
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


def _normalise_criterion_feedback(raw) -> dict:
    raw = raw if isinstance(raw, dict) else {}
    out = {}
    for crit in CRITERIA:
        item = raw.get(crit) if isinstance(raw.get(crit), dict) else {}
        out[crit] = {
            "reason": str(item.get("reason") or "").strip(),
            "evidence": str(item.get("evidence") or "").strip(),
            "next_step": str(item.get("next_step") or "").strip(),
        }
    return out


async def _merge_evaluations(
    answer: str,
    pcm: bytes,
    part: int,
    question: str,
    prompt: str,
) -> dict:
    """Run text + pronunciation evaluations in parallel and merge them."""
    text_task = _text_evaluation(answer or "", part, question or "", prompt=prompt)
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

    criterion_feedback = _normalise_criterion_feedback(text_result.get("criterion_feedback"))
    if pron_band is not None:
        pron_cf = criterion_feedback["pronunciation"]
        if pron_result.get("notes"):
            pron_cf["reason"] = str(pron_result["notes"]).strip()
        issues = pron_result.get("issues") or []
        if issues and isinstance(issues[0], dict):
            pron_cf["evidence"] = str(issues[0].get("example") or pron_cf["evidence"]).strip()
            pron_cf["next_step"] = str(issues[0].get("fix") or pron_cf["next_step"]).strip()

    evaluation = {
        "band_scores": scores,
        "overall_band": overall_band(scores),
        "criterion_feedback": criterion_feedback,
        "why_band_summary": str(text_result.get("why_band_summary") or "").strip(),
        "strengths": text_result.get("strengths") or [],
        "improvements": text_result.get("improvements") or [],
        "vocabulary_feedback": text_result.get("vocabulary_feedback") or {},
        "grammar_errors": text_result.get("grammar_errors") or [],
        "corrected_transcript": text_result.get("corrected_transcript") or answer or "",
        "band7_tip": text_result.get("band7_tip") or "",
        "filler_words_count": text_result.get("filler_words_count", 0),
        "word_count": text_result.get("word_count", len((answer or "").split())),
        "pronunciation_detail": pron_result,
        "evaluator": text_result.get("_provider") or eval_mode(),
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


async def evaluate_answer(answer: str, pcm: bytes, part: int, question: str) -> dict:
    """Score a single answer (kept for targeted checks and tests)."""
    return await _merge_evaluations(
        answer, pcm, part, question,
        build_text_evaluation_prompt(answer or "", part, question or ""),
    )


async def evaluate_part(answers: list[dict], pcm: bytes, part: int) -> dict:
    """Score a whole IELTS part (all Q/A turns) as one performance."""
    pairs = [
        (
            str(a.get("question") or "").strip(),
            str(a.get("answer_text") or "").strip(),
        )
        for a in answers
        if str(a.get("answer_text") or "").strip()
    ]
    if not pairs:
        pairs = [("", "")]
    transcript = "\n\n".join(
        f"Q{i + 1}: {q or '(question not captured)'}\nA{i + 1}: {a}"
        for i, (q, a) in enumerate(pairs)
    )
    questions = " | ".join(q for q, _a in pairs if q)
    return await _merge_evaluations(
        transcript, pcm, part, questions,
        build_part_evaluation_prompt(pairs, part),
    )
