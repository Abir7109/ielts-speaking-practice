"""Answer evaluation pipeline.

Two evaluations run in parallel:
  1. Text criteria (Fluency, Lexical, Grammar)  -> Gemini (default) or DeepSeek
  2. Pronunciation from recorded audio          -> Gemini multimodal (WAV)

Pronunciation is scored ONLY from audio. Asking the text evaluator to guess it
produced a copy of the fluency reasoning, which is why every criterion used to
read the same. When there is no usable recording the band stays None (unassessed)
instead of being invented.

The text prompt is fed measured signals from the transcript so each criterion has
its own evidence to cite, and a post-merge guard repairs reasons/quotes the model
still manages to clone.
"""
import asyncio
import io
import json
import os
import re
import time
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
from rubric import CRITERIA, TEXT_CRITERIA, clamp_band, overall_band

DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
TEXT_EVAL_PROVIDER = (os.getenv("TEXT_EVAL_PROVIDER") or "gemini").strip().lower()
TEXT_EVAL_MODEL = os.getenv("TEXT_EVAL_MODEL", "gemini-2.5-flash")
TEXT_EVAL_FALLBACK_MODEL = os.getenv("TEXT_EVAL_FALLBACK_MODEL", "gemini-2.5-flash-lite")
PRONUNCIATION_MODEL = os.getenv("PRONUNCIATION_MODEL", "gemini-2.5-flash")
SEND_SAMPLE_RATE = 16000
MIN_AUDIO_SECONDS = 2.0

_GEMINI_CLIENT = None
_LAST_EVAL: dict = {}


def last_eval_status() -> dict:
    """Diagnostics for the last text-scoring attempt (safe for /status)."""
    return dict(_LAST_EVAL)


def _record_eval(**fields) -> None:
    _LAST_EVAL.clear()
    _LAST_EVAL.update(fields)
    _LAST_EVAL["at"] = time.time()

FILLER_PATTERNS = [
    r"\bum+\b", r"\buh+\b", r"\ber+\b", r"\bah+\b",
    r"\byou know\b", r"\bi mean\b", r"\bsort of\b", r"\bkind of\b",
    r"\bbasically\b", r"\bactually\b",
    # "like" is counted only when punctuation marks it as a filler — as a plain verb
    # ("I like cooking") it is the most common false positive and it skewed fluency.
    r",\s*like\b", r"\blike\s*,",
]

# Two tiers, because the band descriptors separate them: repeated "because"
# clauses are what a Band 5-6 speaker already does, while relative, conditional
# and contrast clauses are the "variety of complex structures" of Band 7+.
SUBORDINATION_MARKERS = [
    "because", "since", "so that", "as long as", "when", "once", "until",
    "before", "after", "as soon as",
]
ADVANCED_MARKERS = [
    "although", "though", "whereas", "while", "which", "who",
    "whose", "if", "unless", "in order to", "despite",
    "however", "therefore", "on the other hand", "whenever",
    "whether", "even though",
]
COMPLEX_MARKERS = SUBORDINATION_MARKERS + ADVANCED_MARKERS

DISCOURSE_MARKERS = [
    "first", "then", "next", "finally", "however", "for example",
    "in addition", "to be honest", "i suppose", "in my opinion", "actually",
    "on the other hand", "overall", "to sum up",
]

SELF_REPAIR_MARKERS = [
    "sorry", "i mean", "what i mean", "let me think", "how do you say",
    "how do i say", "again", "in other words", "i mean is",
]

# Words that push lexical resource into band 7+ territory when used accurately.
LESS_COMMON_LEXIS = [
    "inevitably", "considerable", "substantially", "reluctant", "crucial",
    "furthermore", "nevertheless", "albeit", "consequently", "predominantly",
    "sufficient", "enthusiastic", "comprehensive", "detrimental", "beneficial",
    "significantly", "approximately", "subsequently", "acknowledge",
    "anticipate", "compelling", "dilemma", "feasible", "hurdle", "mitigate",
    "notion", "profound", "reluctance", "tedious", "viable",
]

IDIOM_MARKERS = [
    "a drop in the ocean", "once in a blue moon", "see eye to eye",
    "on the fence", "a blessing in disguise", "cost an arm and a leg",
    "in two minds", "over the moon", "not my cup of tea", "at the drop of a hat",
    "burn the midnight oil", "a double-edged sword", "the best of both worlds",
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


async def _gemini_json(
    prompt: str, model: str | None = None, use_thinking_config: bool = True
) -> str:
    client = _gemini_client().aio
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        temperature=0.2,
        max_output_tokens=8192,
    )
    if use_thinking_config:
        # 2.5 Flash thinks by default; thinking tokens were truncating the
        # JSON verdict. Scoring is deterministic enough without them.
        config.thinking_config = types.ThinkingConfig(thinking_budget=0)
    resp = await client.models.generate_content(
        model=model or TEXT_EVAL_MODEL,
        contents=prompt,
        config=config,
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


def _audio_seconds(pcm: bytes) -> float:
    if not pcm:
        return 0.0
    return len(pcm) / (SEND_SAMPLE_RATE * 2)


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


def _marker_hits(text_lower: str, markers: list[str]) -> list[str]:
    """Whole-word marker match — "if" must not fire inside "difficult"."""
    return [m for m in markers if re.search(rf"\b{re.escape(m)}\b", text_lower)]


def _text_metrics(answer: str) -> dict:
    text = answer or ""
    lower = text.lower()
    words = re.findall(r"[A-Za-z']+", text)
    wc = len(words)
    sentences = [s for s in re.split(r"[.!?]+", text) if s.strip()]
    # ';' and ':' join independent clauses — the range descriptor counts those,
    # while sentence ends stay the speaking-turn proxy for fluency.
    clauses = [s for s in re.split(r"[.!?;:]+", text) if s.strip()]
    fillers = sum(len(re.findall(p, lower)) for p in FILLER_PATTERNS)
    self_repairs = sum(lower.count(m) for m in SELF_REPAIR_MARKERS)
    content = [w.lower() for w in words if w.lower() not in STOPWORDS]
    counts: dict[str, int] = {}
    for w in content:
        counts[w] = counts.get(w, 0) + 1
    reps = sorted(((w, c) for w, c in counts.items() if c >= 3), key=lambda x: -x[1])[:3]
    ttr = (len({w.lower() for w in words}) / wc) if wc else 0.0
    complex_hits = _marker_hits(lower, COMPLEX_MARKERS)
    advanced_hits = _marker_hits(lower, ADVANCED_MARKERS)
    discourse = _marker_hits(lower, DISCOURSE_MARKERS)
    less_common = [w for w in LESS_COMMON_LEXIS if re.search(rf"\b{w}\b", lower)]
    idioms = [p for p in IDIOM_MARKERS if p in lower]
    complex_clauses = [
        s for s in clauses if _marker_hits(s.lower(), COMPLEX_MARKERS)
    ]
    advanced_clauses = [
        s for s in clauses if _marker_hits(s.lower(), ADVANCED_MARKERS)
    ]
    reason_markers = [m for m in ("because", "since", "so that") if m in lower]
    if re.search(r"\bas\b", lower):
        reason_markers.append("as")
    example_markers = [m for m in ("for example", "for instance", "such as", "last ", "once ") if m in lower]
    # A part transcript is marked "A1:", "A2:" — those are the real speaking turns,
    # which is what the fluency descriptor measures. Sentences are not turns: one
    # 40-word answer is a single turn however many full stops it contains.
    turn_markers = re.findall(r"^A\d+:", text, flags=re.M)
    turns = len(turn_markers) or 1
    return {
        "words": words, "wc": wc, "sentences": sentences, "fillers": fillers,
        "self_repairs": self_repairs, "turns": turns,
        "reps": reps, "ttr": ttr, "complex_hits": complex_hits,
        "advanced_hits": advanced_hits,
        "clause_count": len(clauses),
        "complex_clauses": len(complex_clauses),
        "advanced_clauses": len(advanced_clauses),
        "less_common": less_common, "idioms": idioms,
        "discourse": discourse, "reason_markers": reason_markers,
        "example_markers": example_markers,
        "developed": bool(reason_markers) and bool(example_markers),
        "avg_sentence": round(wc / len(sentences), 1) if sentences else 0.0,
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


def _pct(part: int, whole: int) -> str:
    return f"{round(100 * part / whole)}%" if whole else "0%"


def build_evidence_brief(
    text: str, pairs: list[tuple[str, str]] | None = None, audio_seconds: float = 0.0
) -> str:
    """Per-criterion measured facts, so each band has its own evidence to cite.

    Without this the model only sees a wall of text and justifies all four
    criteria from one overall impression.
    """
    m = _text_metrics(text)
    errors = _find_grammar_errors(text or "")
    answers = [a for _q, a in (pairs or []) if a and a.strip()]
    n_answers = len(answers) or m["turns"] or 1
    developed = sum(
        1 for a in answers
        if any(r in a.lower() for r in ("because", "since", "so that"))
        and any(e in a.lower() for e in ("for example", "for instance", "such as"))
    )
    avg_words = round(m["wc"] / n_answers, 1)

    lines = ["FLUENCY & COHERENCE signals:"]
    lines.append(
        f"  - {m['wc']} words over {n_answers} answer turn(s) "
        f"(average {avg_words} words per turn)."
    )
    if audio_seconds >= MIN_AUDIO_SECONDS and m["wc"]:
        lines.append(
            f"  - approx {_audio_seconds_text(audio_seconds)} of speech "
            f"(~{round(m['wc'] / audio_seconds * 60)} words per minute)."
        )
    lines.append(
        f"  - {m['fillers']} filler items ({_pct(m['fillers'], m['wc'])} of words), "
        f"{m['self_repairs']} self-repair markers (sorry / I mean / in other words)."
    )
    lines.append(
        f"  - {developed} of {n_answers} turns contain both a reason and an example."
    )
    lines.append(
        f"  - discourse markers used: {', '.join(m['discourse'][:6]) or 'none detected'}."
    )

    lines.append("LEXICAL RESOURCE signals:")
    lines.append(
        f"  - type-token ratio {round(m['ttr'], 2)}; "
        f"{len({w.lower() for w in m['words']})} distinct word forms."
    )
    lines.append(
        f"  - over-used content words: "
        f"{', '.join(f'{w} x{c}' for w, c in m['reps']) or 'none'}."
    )
    lines.append(
        f"  - less common/academic items: "
        f"{', '.join(m['less_common'][:6]) or 'none detected'}."
    )
    lines.append(f"  - idiomatic phrases: {', '.join(m['idioms']) or 'none detected'}.")

    lines.append("GRAMMATICAL RANGE & ACCURACY signals:")
    lines.append(
        f"  - {m['complex_clauses']} of {m['clause_count']} clauses are complex "
        f"({_pct(m['complex_clauses'], m['clause_count'])}), of which "
        f"{m['advanced_clauses']} carry a relative, conditional or contrast clause."
    )
    lines.append(
        f"  - simple subordination seen: "
        f"{', '.join(sorted(set(m['complex_hits']) - set(m['advanced_hits']))) or 'none'}."
    )
    lines.append(
        f"  - advanced structures seen: {', '.join(m['advanced_hits'][:8]) or 'none'}."
    )
    lines.append(
        f"  - {len(errors)} detectable error(s) "
        f"({round(len(errors) / m['wc'] * 100, 1) if m['wc'] else 0} per 100 words): "
        f"{'; '.join(e['error'] for e in errors[:5]) or 'none'}."
    )
    if audio_seconds >= MIN_AUDIO_SECONDS:
        lines.append(
            "PRONUNCIATION: judged by the audio reviewer from the recording. "
            "Do not score or comment on it."
        )
    else:
        lines.append(
            "PRONUNCIATION: no usable recording for this part. Leave it unassessed; "
            "do not guess it from the transcript."
        )
    return "\n".join(lines)


def _audio_seconds_text(seconds: float) -> str:
    whole = int(seconds)
    if whole < 60:
        return f"{whole} seconds"
    return f"{whole // 60} min {whole % 60} s"


def _half_step(value: float) -> float:
    return round(max(2.5, min(8.5, round(value * 2) / 2)), 1)


def _fluency_band(m: dict, errors: list[dict], avg_words: float) -> tuple[float, str]:
    """Band + the single decisive factor, from fluency-shaped evidence only."""
    band = 5.0
    filler_rate = (m["fillers"] / m["wc"]) if m["wc"] else 0.0
    if avg_words >= 60:
        band += 1.0
        factor = f"they sustained {avg_words}-word turns without effort"
    elif avg_words >= 30:
        band += 0.5
        factor = f"turns run to {avg_words} words, so the answer is willing but not yet extended"
    elif avg_words >= 15:
        factor = "turns are short but complete"
    else:
        band -= 1.0
        factor = f"turns average only {avg_words} words, which cannot show fluent extended speech"

    if m["developed"]:
        band += 0.5
    if len(m["discourse"]) >= 3:
        band += 0.5
    elif len(m["discourse"]) == 0 and not m["complex_hits"] and avg_words >= 15:
        # Only meaningful once there is enough speech to have linked ideas; a four-word
        # answer is not penalised twice for missing connectives, and an answer linked by
        # "because/although" is not unlinked.
        band -= 0.5
        factor = "no connective or discourse marker links one idea to the next"
    if filler_rate > 0.10:
        band -= 1.0
        factor = f"fillers appear in {_pct(m['fillers'], m['wc'])} of words and break the flow"
    elif filler_rate > 0.05:
        band -= 0.5
        factor = f"{m['fillers']} fillers interrupt an otherwise even flow"
    if m["self_repairs"] >= 3:
        band -= 0.5
    return _half_step(band), factor


def _lexical_band(m: dict, avg_words: float) -> tuple[float, str]:
    band = 5.0
    if m["wc"] < 30:
        # Every word in a 15-word answer is unique by construction; TTR only
        # separates speakers once there is a sample to measure.
        factor = (
            f"only {m['wc']} words were produced, so the range of vocabulary "
            "cannot be measured"
        )
    elif m["ttr"] >= 0.70:
        band += 1.0
        factor = f"a type-token ratio of {round(m['ttr'], 2)} shows genuinely varied word choice"
    elif m["ttr"] >= 0.55:
        band += 0.5
        factor = f"vocabulary varies reasonably (TTR {round(m['ttr'], 2)})"
    elif m["ttr"] < 0.35 and m["wc"] >= 40:
        band -= 1.0
        factor = f"a type-token ratio of {round(m['ttr'], 2)} means words are recycled"

    if len(m["idioms"]) >= 1:
        band += 1.0
        factor = f"idiomatic language is attempted ('{m['idioms'][0]}')"
    if len(m["less_common"]) >= 5:
        band += 1.0
        factor = f"less common items appear throughout ({', '.join(m['less_common'][:3])})"
    elif len(m["less_common"]) >= 2:
        band += 0.5
        factor = f"some less common vocabulary ({', '.join(m['less_common'][:3])})"

    if m["reps"]:
        top_word, top_count = m["reps"][0]
        if top_count >= 5:
            band -= 1.0
            factor = f"'{top_word}' is used {top_count} times instead of being paraphrased"
        elif top_count >= 3:
            band -= 0.5
            factor = f"'{top_word}' recurs {top_count} times where paraphrase was needed"
    if avg_words < 15:
        band -= 0.5
    return _half_step(band), factor


def _grammar_band(m: dict, errors: list[dict]) -> tuple[float, str]:
    clauses = m["clause_count"]
    band = 5.0
    complex_ratio = (m["complex_clauses"] / clauses) if clauses else 0.0
    advanced_ratio = (m["advanced_clauses"] / clauses) if clauses else 0.0
    factor = ""
    if advanced_ratio >= 0.34:
        band += 1.5
        factor = (
            f"{m['advanced_clauses']} of {clauses} clauses carry a relative, "
            "conditional or contrast clause"
        )
    elif complex_ratio >= 0.5:
        band += 1.0
        factor = (
            f"{m['complex_clauses']} of {clauses} clauses are subordinated, "
            "but through 'because'/'when' links rather than varied structures"
        )
    elif complex_ratio >= 0.3:
        band += 0.5
        factor = (
            f"complex structures appear in {m['complex_clauses']} of {clauses} clauses"
        )
    elif complex_ratio == 0 and clauses >= 3:
        band -= 1.0
        factor = "every clause is simple — no range of structures is attempted"

    density = (len(errors) / m["wc"] * 100) if m["wc"] else 0.0
    if len(errors) >= 4:
        band -= 1.0
        factor = f"{len(errors)} errors, e.g. '{errors[0]['error']}', make accuracy the limiting factor"
    elif len(errors) >= 2:
        band -= 0.5
        factor = (
            f"errors such as '{errors[0]['error']}' survive even in the clauses where "
            "a complex structure is attempted"
        )
    elif not errors and clauses >= 3:
        band += 0.5
        if not factor:
            factor = "the clauses produced are accurate"
    if not factor:
        factor = "a mix of simple and complex clauses with no clear error pattern"
    if density > 5:
        band -= 0.5
    if not m["advanced_clauses"]:
        # No relative, conditional or contrast clause anywhere: the descriptor's
        # "variety of complex structures" is absent, so the band stops at 6.0.
        band = min(band, 6.0)
    return _half_step(band), factor


def _heuristic_text_evaluation(answer: str) -> dict:
    """Offline fallback when no text evaluator is reachable.

    Each criterion is scored from its OWN measured signal rather than one
    word-count-derived base, so a precise short answer is not punished below a
    long rambling one and the four reasons never read alike.
    """
    m = _text_metrics(answer)
    errors = _find_grammar_errors(answer or "")
    avg_words = round(m["wc"] / max(1, m["turns"]), 1)

    fc, fc_factor = _fluency_band(m, errors, avg_words)
    lr, lr_factor = _lexical_band(m, avg_words)
    gra, gra_factor = _grammar_band(m, errors)

    scores = {
        "fluency_coherence": fc,
        "lexical_resource": lr,
        "grammatical_range": gra,
        "pronunciation": None,
    }

    first_sentence = (m["sentences"][0][:140] if m["sentences"] else (answer or "")[:140]).strip()
    rep_word, rep_count = (m["reps"][0] if m["reps"] else ("", 0))

    criterion_feedback = {
        "fluency_coherence": {
            "reason": f"{fc_factor[:1].upper()}{fc_factor[1:]}.",
            "why_not_higher": (
                "the turns do not yet hold together long enough without hesitation"
                if fc < 8.5 else "hesitation is still audible in the transcript"
            ),
            "why_not_lower": f"the speech does not break down ({fc_factor}).",
            "evidence": first_sentence,
            "next_step": (
                "Answer with a direct response, one reason with 'because', and one "
                "example with 'for example' so each turn reaches two sentences."
            ),
        },
        "lexical_resource": {
            "reason": f"{lr_factor[:1].upper()}{lr_factor[1:]}.",
            "why_not_higher": (
                "no less common or idiomatic item is used accurately"
                if lr < 7 else "collocation is not always natural"
            ),
            "why_not_lower": f"meaning stays clear with {len({w.lower() for w in m['words']})} distinct word forms.",
            "evidence": f"'{rep_word}' x{rep_count}" if rep_word else first_sentence,
            "next_step": (
                f"Replace '{rep_word or 'good'}' with a precise alternative and add one "
                "idiomatic phrase."
            ),
        },
        "grammatical_range": {
            "reason": f"{gra_factor[:1].upper()}{gra_factor[1:]}.",
            "why_not_higher": (
                "most sentences stay simple, so the range is not yet flexible"
                if gra < 7 else "errors still survive in complex sentences"
            ),
            "why_not_lower": (
                "basic sentence forms are produced accurately"
                if errors else "the attempted complex structures hold up."
            ),
            "evidence": errors[0]["error"] if errors else first_sentence,
            "next_step": (
                f"Fix '{errors[0]['error']}' first."
                if errors else
                "Add one subordinate clause with 'although' or 'which' to each answer."
            ),
        },
        "pronunciation": {
            "reason": (
                "Not assessed — pronunciation is only ever scored from the recording, "
                "and no usable audio was available."
            ),
            "why_not_higher": "",
            "why_not_lower": "",
            "evidence": "",
            "next_step": (
                "Speak for at least 2 seconds per answer close to the microphone so the "
                "recording can be reviewed."
            ),
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
        strengths.append("You supported answers with a reason and an example.")
    if m["complex_clauses"] >= 2:
        strengths.append(
            f"{m['complex_clauses']} complex clauses were attempted."
        )
    if m["less_common"]:
        strengths.append(
            f"Less common vocabulary appeared ({', '.join(m['less_common'][:3])})."
        )
    if not errors and m["wc"] >= 40:
        strengths.append("No grammar error was detected in a substantial answer.")
    if not strengths:
        strengths.append("You responded directly to the question.")

    improvements = []
    if rep_word:
        improvements.append({
            "issue": "The same basic word is recycled instead of being paraphrased.",
            "criterion": "lexical_resource",
            "example_from_response": rep_word,
            "better_version": VOCAB_UPGRADES.get(rep_word, ("a more precise word",))[0],
            "band_impact": f"Lexical Resource: {lr} -> {min(9.0, lr + 0.5)}",
        })
    if errors:
        improvements.append({
            "issue": f"Accuracy breaks down in complex sentences ({errors[0]['type']}).",
            "criterion": "grammatical_range",
            "example_from_response": errors[0]["error"],
            "better_version": errors[0]["correction"],
            "band_impact": f"Grammatical Range & Accuracy: {gra} -> {min(9.0, gra + 0.5)}",
        })
    if not m["developed"]:
        improvements.append({
            "issue": "Answers stop at a bare opinion with no reason or example.",
            "criterion": "fluency_coherence",
            "example_from_response": first_sentence,
            "better_version": f"{first_sentence} because ... For example, ...",
            "band_impact": f"Fluency & Coherence: {fc} -> {min(9.0, fc + 0.5)}",
        })

    weakest = min(TEXT_CRITERIA, key=lambda c: scores[c])
    weakest_next = criterion_feedback[weakest]["next_step"]
    why_summary = (
        f"Band {overall_band(scores)} is capped by "
        f"{weakest.replace('_', ' ').title()} ({scores[weakest]}): "
        f"{criterion_feedback[weakest]['reason']} Fastest gain: {weakest_next}"
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
        "word_count": m["wc"],
        "_degraded": "text-evaluator-unavailable",
        "_provider": "heuristic",
    }


def _has_scored_bands(parsed) -> bool:
    """Reject partial JSON so a truncated response can never become Band 0."""
    if not isinstance(parsed, dict):
        return False
    scores = parsed.get("band_scores")
    if not isinstance(scores, dict):
        return False
    return all(isinstance(scores.get(c), (int, float)) for c in TEXT_CRITERIA)


def _gemini_attempts() -> list[tuple[str, bool]]:
    """Primary model first, then a cheaper fallback, with/without thinking config."""
    attempts: list[tuple[str, bool]] = []
    for model in (TEXT_EVAL_MODEL, TEXT_EVAL_FALLBACK_MODEL):
        if not model:
            continue
        for use_thinking in (True, False):
            item = (model, use_thinking)
            if item not in attempts:
                attempts.append(item)
    return attempts


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

    attempts_made = 0
    last_error = ""
    for provider in order:
        if provider == "gemini":
            variants = _gemini_attempts()
            for model, use_thinking in variants:
                attempts_made += 1
                try:
                    raw = await _gemini_json(
                        prompt, model=model, use_thinking_config=use_thinking
                    )
                    parsed = extract_json(raw)
                    if _has_scored_bands(parsed):
                        parsed["_provider"] = provider
                        _record_eval(
                            provider=provider, model=model, ok=True,
                            fallback=False, attempts=attempts_made, error="",
                        )
                        return parsed
                    last_error = (
                        f"JSON invalid (len={len(raw or '')}, "
                        f"thinking={use_thinking})"
                    )
                    log.warning(f"[EVAL] gemini {last_error}")
                except Exception as e:
                    last_error = f"{type(e).__name__}: {e}"
                    log.warning(
                        f"[EVAL] gemini failed (model={model}, "
                        f"thinking={use_thinking}): {last_error}"
                    )
                await asyncio.sleep(min(0.6 * attempts_made, 2.5))
        else:
            for attempt in range(2):
                attempts_made += 1
                try:
                    raw = await _deepseek_chat(
                        [{"role": "user", "content": prompt}],
                        temperature=0.2 if attempt == 0 else 0.0,
                    )
                    parsed = extract_json(raw)
                    if _has_scored_bands(parsed):
                        parsed["_provider"] = provider
                        _record_eval(
                            provider=provider, model=DEEPSEEK_MODEL, ok=True,
                            fallback=False, attempts=attempts_made, error="",
                        )
                        return parsed
                    last_error = f"JSON invalid (len={len(raw or '')})"
                    log.warning(f"[EVAL] deepseek {last_error}")
                except Exception as e:
                    last_error = f"{type(e).__name__}: {e}"
                    log.warning(
                        f"[EVAL] deepseek evaluation failed "
                        f"(attempt {attempt + 1}): {last_error}"
                    )
                    break
                await asyncio.sleep(0.4)

    log.warning(
        f"[EVAL] all text evaluators unavailable — using local analysis "
        f"(attempts={attempts_made}, last_error={last_error or 'none'})"
    )
    _record_eval(
        provider="heuristic", model="", ok=False, fallback=True,
        attempts=attempts_made, error=last_error or "no evaluator configured",
    )
    return _heuristic_text_evaluation(answer)


def _heuristic_pronunciation() -> dict:
    return {
        "pronunciation_band": None,
        "intelligibility": "unknown",
        "strengths": [],
        "issues": [],
        "notes": "No usable recording — pronunciation was left unassessed rather than guessed.",
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
            "why_not_higher": str(item.get("why_not_higher") or "").strip(),
            "why_not_lower": str(item.get("why_not_lower") or "").strip(),
            "evidence": str(item.get("evidence") or "").strip(),
            "next_step": str(item.get("next_step") or "").strip(),
        }
    return out


def _pronunciation_feedback(pron_result: dict, pron_band) -> dict:
    """Pronunciation feedback comes from the audio reviewer only."""
    if pron_band is None:
        return {
            "reason": (
                "Not assessed — pronunciation needs a clear recording of at least two "
                "seconds, and this part did not provide one."
            ),
            "why_not_higher": "",
            "why_not_lower": "",
            "evidence": "",
            "next_step": (
                "Answer aloud for at least a few seconds per question so the recording "
                "can be reviewed for stress and intonation."
            ),
        }
    issues = pron_result.get("issues") or []
    first = issues[0] if issues and isinstance(issues[0], dict) else {}
    strengths = pron_result.get("strengths") or []
    return {
        "reason": str(pron_result.get("notes") or "").strip() or (
            f"Band {pron_band} from the recording; intelligibility "
            f"{pron_result.get('intelligibility') or 'not stated'}."
        ),
        "why_not_higher": str(first.get("sound_or_feature") or "").strip(),
        "why_not_lower": str(strengths[0] if strengths else "").strip(),
        "evidence": str(first.get("example") or "").strip(),
        "next_step": str(first.get("fix") or "").strip() or (
            "Keep practising word stress in longer answers."
        ),
    }


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", (text or "").lower().strip())


def _repair_clones(feedback: dict, answer: str) -> list[str]:
    """Replace any reason/evidence the model cloned across criteria.

    The clone is overwritten with that criterion's own measured signal, so the
    repair is factual rather than invented filler.
    """
    metrics = _text_metrics(answer)
    errors = _find_grammar_errors(answer or "")
    avg_words = round(metrics["wc"] / max(1, metrics["turns"]), 1)
    fallback = {
        "fluency_coherence": (
            f"{metrics['fillers']} fillers and {avg_words}-word average turns shape the "
            "flow of this part.",
            f"{metrics['discourse'][0] if metrics['discourse'] else metrics['sentences'][0][:60] if metrics['sentences'] else ''}",
        ),
        "lexical_resource": (
            f"Type-token ratio {round(metrics['ttr'], 2)} with "
            f"{', '.join(f'{w} x{c}' for w, c in metrics['reps']) or 'no heavy repetition'} "
            "and "
            f"{len(metrics['less_common'])} less common item(s).",
            metrics["reps"][0][0] if metrics["reps"] else (
                metrics["less_common"][0] if metrics["less_common"] else ""
            ),
        ),
        "grammatical_range": (
            f"{metrics['complex_clauses']} of {metrics['clause_count']} clauses "
            f"are complex ({metrics['advanced_clauses']} with a relative, conditional "
            f"or contrast clause), with {len(errors)} detectable error(s).",
            errors[0]["error"] if errors else (
                metrics["advanced_hits"][0] if metrics["advanced_hits"] else (
                    metrics["complex_hits"][0] if metrics["complex_hits"] else ""
                )
            ),
        ),
    }

    repaired = []
    seen_reasons: dict[str, str] = {}
    seen_quotes: dict[str, str] = {}
    for crit in TEXT_CRITERIA:
        item = feedback.get(crit) or {}
        r_key = _norm(item.get("reason") or "")
        if not r_key or (r_key in seen_reasons):
            who = seen_reasons.get(r_key, "another criterion")
            item["reason"] = fallback[crit][0]
            repaired.append(crit)
            log.warning(
                f"[EVAL] cloned reason for {crit} (same as {who or 'missing'}) — "
                "replaced with measured signal"
            )
        else:
            seen_reasons[r_key] = crit
        q_key = _norm(item.get("evidence") or "")
        if q_key and q_key in seen_quotes:
            item["evidence"] = fallback[crit][1]
            log.warning(
                f"[EVAL] cloned evidence quote for {crit} (shared with "
                f"{seen_quotes[q_key]}) — replaced"
            )
            if crit not in repaired:
                repaired.append(crit)
        elif q_key:
            seen_quotes[q_key] = crit
        feedback[crit] = item
    return repaired


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
        if crit in TEXT_CRITERIA:
            scores[crit] = clamp_band((text_result.get("band_scores") or {}).get(crit, 0))
        else:
            # Never inherited from the text evaluator: an unrecorded pronunciation
            # is reported as unassessed, not guessed.
            scores[crit] = None

    pron_band = pron_result.get("pronunciation_band")
    pron_assessed = pron_band is not None
    if pron_assessed:
        scores["pronunciation"] = clamp_band(pron_band)

    criterion_feedback = _normalise_criterion_feedback(text_result.get("criterion_feedback"))
    for crit in TEXT_CRITERIA:
        if not criterion_feedback[crit]["reason"]:
            criterion_feedback[crit]["reason"] = (
                f"Band {scores[crit]} on the measured signals for this criterion."
            )
    repaired = _repair_clones(criterion_feedback, answer or "")
    criterion_feedback["pronunciation"] = _pronunciation_feedback(pron_result, pron_band)

    question_notes = [
        {"index": n.get("index"), "note": str(n.get("note") or "").strip()}
        for n in (text_result.get("question_notes") or [])
        if isinstance(n, dict) and str(n.get("note") or "").strip()
    ]

    evaluation = {
        "band_scores": scores,
        "overall_band": overall_band(scores),
        "criterion_feedback": criterion_feedback,
        "question_notes": question_notes,
        "pronunciation_assessed": pron_assessed,
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
    if repaired:
        evaluation["repaired_criteria"] = repaired
    degraded = []
    if text_result.get("_degraded"):
        degraded.append(text_result["_degraded"])
    if not pron_assessed:
        degraded.append("pronunciation-unassessed")
    elif pron_result.get("_degraded"):
        degraded.append(pron_result["_degraded"])
    if degraded:
        evaluation["degraded"] = degraded
    return evaluation


async def evaluate_answer(answer: str, pcm: bytes, part: int, question: str) -> dict:
    """Score a single answer (kept for targeted checks and tests)."""
    evidence = build_evidence_brief(answer or "", audio_seconds=_audio_seconds(pcm))
    return await _merge_evaluations(
        answer, pcm, part, question,
        build_text_evaluation_prompt(
            answer or "", part, question or "", evidence=evidence
        ),
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
    audio_seconds = _audio_seconds(pcm)
    evidence = build_evidence_brief(transcript, pairs=pairs, audio_seconds=audio_seconds)
    return await _merge_evaluations(
        transcript, pcm, part, questions,
        build_part_evaluation_prompt(pairs, part, evidence=evidence),
    )
