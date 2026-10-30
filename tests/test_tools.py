"""Regression tests: Gemini Live tool declarations must be real pydantic types."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from google.genai import types  # noqa: E402

from ielts_tools import IELTS_TOOL_NAMES, build_tools  # noqa: E402


class TestBuildTools(unittest.TestCase):
    def test_returns_single_tool_with_all_declarations(self):
        tools = build_tools()
        self.assertEqual(len(tools), 1)
        tool = tools[0]
        self.assertIsInstance(tool, types.Tool)
        self.assertEqual(len(tool.function_declarations), len(IELTS_TOOL_NAMES))
        names = [d.name for d in tool.function_declarations]
        self.assertEqual(names, IELTS_TOOL_NAMES)

    def test_declarations_have_parameters(self):
        tool = build_tools()[0]
        for decl in tool.function_declarations:
            self.assertIsNotNone(decl.parameters, f"{decl.name} has no parameters schema")

    def test_live_connect_config_accepts_tools(self):
        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            system_instruction="test",
            tools=build_tools(),
        )
        self.assertEqual(len(config.tools), 1)

    def test_exactly_seven_tools(self):
        self.assertEqual(len(IELTS_TOOL_NAMES), 7)
        self.assertEqual(
            set(IELTS_TOOL_NAMES),
            {
                "start_test",
                "evaluate_answer",
                "next_question",
                "repeat_question",
                "finish_test",
                "set_goal",
                "get_progress",
            },
        )


if __name__ == "__main__":
    unittest.main()
