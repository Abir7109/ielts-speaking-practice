"""Official IELTS Speaking public band descriptors (0-9) and band arithmetic.

Criteria are weighted equally (25% each). Descriptors for Bands 5-9 follow the
official public descriptor wording; lower bands are summarised.
"""


DESCRIPTORS = {
    "fluency_coherence": {
        9: "Speaks fluently with only rare repetition or self-correction. Any hesitation is content-related rather than searching for language. Speaks coherently with fully appropriate cohesive features. Develops topics fully and appropriately.",
        8: "Speaks fluently with only occasional repetition or self-correction; hesitation is usually content-related and rarely to search for language. Develops topics coherently and appropriately.",
        7: "Speaks at length without noticeable effort or loss of coherence. May demonstrate language-related hesitation at times, or some repetition/self-correction. Uses a range of connectives and discourse markers with some flexibility.",
        6: "Is willing to speak at length, though may lose coherence at times due to occasional repetition, self-correction, or hesitation. Uses a range of connectives and discourse markers, but not always appropriately.",
        5: "Usually maintains flow of speech but uses repetition, self-correction, and/or slow speech to keep going. May over-use certain connectives and discourse markers. Produces simple speech fluently, but complex communication causes hesitation.",
        4: "Cannot respond without noticeable pauses. May need to repeat what the examiner says to show understanding. Speaks in short, disconnected utterances with frequent loss of coherence.",
        3: "Speaks with frequent pauses that impede the flow of communication. May rely heavily on repetition or rephrasing to continue.",
        2: "Pauses before responses are so long that the flow of conversation breaks down.",
        1: "Unable to produce more than isolated words or short formulaic phrases.",
        0: "Does not attend. Unable to produce any response.",
    },
    "lexical_resource": {
        9: "Uses vocabulary with full flexibility and precision across all topics. Uses idiomatic language naturally and accurately.",
        8: "Uses a wide vocabulary resource readily and flexibly to convey precise meaning. Uses less common and idiomatic vocabulary skilfully, with occasional inaccuracies. Uses paraphrase effectively as required.",
        7: "Uses vocabulary resource flexibly to discuss a variety of topics. Uses some less common and idiomatic vocabulary and shows awareness of style and collocation, with some inappropriate choices. Paraphrases effectively.",
        6: "Has a wide enough vocabulary to discuss topics at length and make meaning clear in spite of inappropriacies. Generally paraphrases successfully.",
        5: "Has limited vocabulary range; can talk about familiar/everyday subjects reasonably well, but struggles with abstract or less familiar topics. Paraphrase is attempted but not always successful.",
        4: "Uses only basic and simple vocabulary items that may be used repetitively. Frequently makes errors in word choice.",
        3: "Uses only basic and simple vocabulary. Limited to short, simple expressions.",
        2: "Vocabulary is so limited that communication breaks down.",
        1: "Unable to produce words other than isolated, memorised items.",
        0: "No response.",
    },
    "grammatical_range": {
        9: "Uses a full range of structures naturally and appropriately. Produces consistently accurate structures apart from native-speaker-like slips.",
        8: "Uses a wide range of structures flexibly. Produces a majority of error-free sentences with only very occasional inappropriacies or basic/non-systematic errors.",
        7: "Uses a range of complex structures with some flexibility. Frequently produces error-free sentences, though some grammatical mistakes persist.",
        6: "Uses a mix of simple and complex structures, but with limited flexibility. May make frequent mistakes with complex structures, though these rarely cause comprehension problems.",
        5: "Produces basic sentence forms with reasonable accuracy. Uses a limited range of complex structures, which frequently contain errors and may cause comprehension problems.",
        4: "Uses only a very limited range of structures with only rare use of subordinate clauses. Some basic structures are attempted but errors predominate.",
        3: "Attempts basic sentence forms but with limited success. Relies heavily on prompted or memorised utterances.",
        2: "Incapable of producing grammatically correct sentences.",
        1: "Unable to produce any sentences.",
        0: "No response.",
    },
    "pronunciation": {
        9: "Uses a full range of pronunciation features with precision and subtlety. Sustains flexible use of features throughout. Is effortless to understand.",
        8: "Uses a wide range of pronunciation features. Sustains flexible use of features, with only occasional lapses. Easy to understand throughout; L1 accent has minimal effect on intelligibility.",
        7: "Shows all the positive features of Band 6 and some, but not all, of the positive features of Band 8.",
        6: "Uses a range of pronunciation features with mixed control. Shows some effective use of features, but this is not sustained. Can generally be understood throughout, though mispronunciation of individual words or sounds reduces clarity at times.",
        5: "Shows basic pronunciation features. Control is limited, and mispronunciations frequently cause lack of clarity or strain for the listener.",
        4: "Uses a limited range of pronunciation features. Can be understood with some strain, though individual words or sound sequences may be difficult to hear.",
        3: "Uses only a few pronunciation features, with limited control. Can generally be understood only by familiar listeners who are prepared to make a lot of effort.",
        2: "Uses pronunciation features only sporadically. Difficult to understand except by familiar listeners.",
        1: "Produces isolated sounds only with great effort from the listener.",
        0: "No response.",
    },
}

CRITERIA = ["fluency_coherence", "lexical_resource", "grammatical_range", "pronunciation"]

# Pronunciation is only ever scored from the recording; the text evaluator has no
# evidence for it and reproduces the fluency reasoning when asked to guess.
TEXT_CRITERIA = [c for c in CRITERIA if c != "pronunciation"]
AUDIO_CRITERIA = ["pronunciation"]

CRITERION_WEIGHT = 0.25  # each criterion contributes 25% of the overall band

CRITERIA_LABELS = {
    "fluency_coherence": "Fluency & Coherence",
    "lexical_resource": "Lexical Resource",
    "grammatical_range": "Grammatical Range & Accuracy",
    "pronunciation": "Pronunciation",
}



def round_half_up(value: float, increment: float = 0.5) -> float:
    """IELTS-style rounding: nearest half band, .25 rounds UP (6.25 -> 6.5)."""
    if value is None:
        return 0.0
    steps = round((float(value) / increment) + 1e-9)
    # handle exact .5 distance with half-up (not banker's rounding)
    raw = float(value) / increment
    frac = raw - int(raw)
    if abs(frac - 0.5) < 1e-9:
        steps = int(raw) + 1
    return round(steps * increment, 1)


def assessed_criteria(scores: dict) -> list:
    """Criteria that carry a real band; None means 'not assessed', never 0."""
    return [
        c for c in CRITERIA
        if isinstance(scores.get(c), (int, float)) and scores.get(c) is not None
    ]


def overall_band(scores: dict) -> float:
    """Mean of the assessed criteria, rounded to the nearest half band.

    A criterion scored None (pronunciation without usable audio) is excluded
    rather than counted as Band 0 — averaging in a fake zero drags every
    candidate toward the same floor band.
    """
    vals = [float(scores[c]) for c in assessed_criteria(scores)]
    if not vals:
        return 0.0
    return round_half_up(sum(vals) / len(vals))


def clamp_band(value) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(9.0, v))


def rubric_prompt() -> str:
    lines = [
        "Official IELTS Speaking assessment: four criteria, each weighted 25%:",
        "Fluency & Coherence (FC), Lexical Resource (LR), Grammatical Range &",
        "Accuracy (GRA), Pronunciation (P). Score each criterion independently",
        "against the descriptors below, using the exact band wording as the anchor.",
    ]
    for crit in CRITERIA:
        lines.append(f"\n{CRITERIA_LABELS[crit]}:")
        for band in range(9, -1, -1):
            lines.append(f"  Band {band}: {DESCRIPTORS[crit][band]}")
    lines.append(
        "\nOverall band = arithmetic mean of the four criteria (25% each), "
        "rounded to the nearest half or whole band (6.125 -> 6.0, 6.25 -> 6.5)."
    )
    return "\n".join(lines)


RUBRIC_PROMPT = rubric_prompt()
