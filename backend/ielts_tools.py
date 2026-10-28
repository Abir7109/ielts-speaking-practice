"""Gemini function declarations for the IELTS speaking examiner.

ONLY these tools exist in this app. Nothing else is callable.
"""

IELTS_TOOLS = [
    {
        "name": "start_test",
        "description": (
            "Start an IELTS speaking test. Call once after the candidate says whether "
            "they want a full mock test or a single part. The result contains the EXACT "
            "text to speak aloud word for word, including the first question."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "description": "Which test to run",
                    "enum": ["full", "part1", "part2", "part3"],
                },
                "topic": {
                    "type": "string",
                    "description": "Optional Part 1 topic (e.g. 'hometown', 'technology')",
                },
            },
            "required": ["mode"],
        },
    },
    {
        "name": "evaluate_answer",
        "description": (
            "Evaluate the candidate's most recent spoken answer. The system already "
            "captured the transcript and audio — do NOT pass the transcript. The result "
            "contains the EXACT feedback to speak aloud word for word."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "part": {
                    "type": "integer",
                    "description": "Speaking part of the answer being evaluated (1, 2 or 3)",
                },
            },
            "required": [],
        },
    },
    {
        "name": "next_question",
        "description": (
            "Move to the next question of the test. Automatically evaluates any answer "
            "that was not yet evaluated, then returns the EXACT text to speak aloud."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "repeat_question",
        "description": (
            "Repeat the current question because the candidate did not hear or "
            "understand it. Returns the EXACT text to speak aloud."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "finish_test",
        "description": (
            "End the test and generate the final report (evaluates any pending answer "
            "first). The result contains the EXACT summary to read aloud."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "set_goal",
        "description": "Save the candidate's target band score and/or exam date.",
        "parameters": {
            "type": "object",
            "properties": {
                "target_band": {"type": "number", "description": "Target overall band (e.g. 7.0)"},
                "exam_date": {"type": "string", "description": "Exam date YYYY-MM-DD"},
            },
            "required": [],
        },
    },
    {
        "name": "get_progress",
        "description": (
            "Show the candidate's band history and progress dashboard. "
            "Opens the dashboard panel on screen."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]

IELTS_TOOL_NAMES = [t["name"] for t in IELTS_TOOLS]
