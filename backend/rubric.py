"""Official IELTS Speaking band descriptors (0-9) and band arithmetic."""


DESCRIPTORS = {
    "fluency_coherence": {
        9: "Speaks fluently with only rare repetition or self-correction. Any hesitation is only for searching for language or ideas. Speaks coherently with fully appropriate use of cohesive features.",
        8: "Speaks fluently with only occasional repetition or self-correction. Hesitation is usually for language retrieval only. Speaks coherently with appropriate use of cohesive features, though there may be some under- or over-use.",
        7: "Speaks at length without noticeable effort or loss of coherence. May demonstrate language-related hesitation at times, and some re-phrasing and/or self-correction. Uses a range of cohesive devices appropriately.",
        6: "Speaks at length without noticeable effort or loss of coherence. May demonstrate language-related hesitation at times, and some re-phrasing. Uses a range of cohesive devices appropriately, though there may be some under- or over-use.",
        5: "Speaks at length but may lose coherence at times due to repetition, self-correction and/or hesitation. Uses a limited range of cohesive devices with some inappropriacy.",
        4: "Cannot respond without noticeable pauses. May need to repeat what the examiner says to show understanding. Speaks in short, disconnected utterances with frequent loss of coherence.",
        3: "Speaks with frequent pauses that impede the flow of communication. May rely heavily on repetition or rephrasing to continue. Unable to respond without starting again or saying sorry, please repeat.",
        2: "Pauses before responses that are so long that the flow of conversation breaks down. May need to repeat what the examiner says to show understanding.",
        1: "Unable to produce more than isolated words or short formulaic phrases. May not be able to communicate at all.",
        0: "Does not attend. Unable to produce any response.",
    },
    "lexical_resource": {
        9: "Uses vocabulary with full flexibility and precision in all topics. Uses a wide range of general and some non-general lexical items naturally and precisely, including idiomatic expressions.",
        8: "Uses a wide range of vocabulary fluently and flexibly to convey precise meanings. Uses a wide range of general and some non-general lexical items with a high degree of accuracy, including idiomatic expressions.",
        7: "Uses a sufficient range of vocabulary to allow some flexibility and precision in expressing meanings. Uses less common and some idiomatic vocabulary and shows some awareness of style and collocation, with some errors.",
        6: "Has a wide enough vocabulary to discuss a variety of topics at length and make meaning clear in spite of some imprecision. Uses less common and some idiomatic vocabulary with some errors in word choice or collocation.",
        5: "Uses a limited range of vocabulary and this minimally conveys meaning. Frequently makes errors in word choice that impede communication. Uses only a very limited range of vocabulary, with some errors in word formation.",
        4: "Uses only basic and simple vocabulary items that may be used repetitively. Uses limited vocabulary and frequently makes errors in word choice.",
        3: "Uses only basic and simple vocabulary. Limited to short, simple expressions.",
        2: "Vocabulary is so limited that communication breaks down.",
        1: "Unable to produce words other than isolated, memorised items.",
        0: "No response.",
    },
    "grammatical_range": {
        9: "Uses a wide range of structures with full flexibility and accuracy. Produces a majority of error-free sentences and shows a wide range of structures.",
        8: "Uses a wide range of structures. The majority of sentences are error-free. Produces a wide range of structures, with flexibility and accuracy.",
        7: "Uses a variety of complex structures. Produces frequent error-free sentences. Shows a wide range of structures with accuracy and flexibility.",
        6: "Uses a mix of simple and complex structures, but with limited flexibility. May make frequent grammatical errors and some may cause confusion for the listener.",
        5: "Uses only a limited range of structures. Attempts complex sentences but these tend to be faulty. Grammatical errors may cause confusion for the listener.",
        4: "Uses only a very limited range of structures with only rare use of subordinate clauses. Some basic structures are attempted but errors predominate, and punctuation is frequently faulty.",
        3: "Attempts basic sentence forms but with limited success. Relies heavily on prompted or memorised utterances.",
        2: "Incapable of producing grammatically correct sentences.",
        1: "Unable to produce any sentences.",
        0: "No response.",
    },
    "pronunciation": {
        9: "Uses a full range of pronunciation features with precision and subtlety. Uses a wide range of pronunciation features to convey meaning appropriately, with effortless control. L1 has no effect on intelligibility.",
        8: "Uses a wide range of pronunciation features. Sustained, flexible and accurate use of pronunciation features, with only occasional lapses. L1 has no effect on intelligibility.",
        7: "Shows all positive features of Band 6 and some but not all of the positive features of Band 8. Easy to understand throughout, with L1 accent having no effect on intelligibility at not more than one point.",
        6: "Uses a range of pronunciation features with mixed control. Can be understood throughout, though mispronunciations of individual words or sound sequences may cause some difficulty.",
        5: "Shows some effective use of pronunciation features, but this is not sustained. Can generally be understood throughout, though with some strain for the listener.",
        4: "Uses a limited range of pronunciation features. Attempts to control features, but these are limited. Can be understood with some strain, though individual words or sound sequences may be difficult to hear.",
        3: "Uses only a few pronunciation features, with limited control. Can generally be understood only by familiar listeners who are prepared to make a lot of effort.",
        2: "Uses pronunciation features only sporadically. Difficult to understand except by familiar listeners.",
        1: "Produces isolated sounds only with great effort from the listener.",
        0: "No response.",
    },
}

CRITERIA = ["fluency_coherence", "lexical_resource", "grammatical_range", "pronunciation"]

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


def overall_band(scores: dict) -> float:
    """Mean of the four criteria, rounded to the nearest half band."""
    vals = [float(scores.get(c, 0) or 0) for c in CRITERIA]
    return round_half_up(sum(vals) / len(vals))


def clamp_band(value) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(9.0, v))


def rubric_prompt() -> str:
    lines = []
    for crit in CRITERIA:
        lines.append(f"\n{CRITERIA_LABELS[crit]}:")
        for band in range(9, -1, -1):
            lines.append(f"  Band {band}: {DESCRIPTORS[crit][band]}")
    lines.append(
        "\nOverall band = mean of the four criteria, rounded to the nearest half band."
    )
    return "\n".join(lines)


RUBRIC_PROMPT = rubric_prompt()
