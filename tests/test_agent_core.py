"""Tests for the ReAct engine: action parsing, token trimming, and the run loop.

The run-loop tests build an AgentCore via __new__ and inject fakes, avoiding the
heavyweight __init__ (which constructs the real router, memory, and tools).
"""
from __future__ import annotations

import unittest
from unittest import mock

try:
    from agent.core import (
        AgentCore,
        _estimate_tokens,
        _parse_action,
        _trim_messages,
    )
except ModuleNotFoundError:  # pragma: no cover - optional dependency guard
    AgentCore = None
    _estimate_tokens = _parse_action = _trim_messages = None


@unittest.skipUnless(_parse_action is not None, "agent dependencies not installed")
class ParseActionTests(unittest.TestCase):
    def test_final_answer_takes_precedence(self) -> None:
        name, inp, final = _parse_action("Thought: done.\nFinal Answer: The answer is 42.")
        self.assertIsNone(name)
        self.assertIsNone(inp)
        self.assertEqual(final, "The answer is 42.")

    def test_action_with_json_input(self) -> None:
        name, inp, final = _parse_action(
            'Thought: search.\nAction: search\nAction Input: {"query": "abc"}'
        )
        self.assertEqual(name, "search")
        self.assertEqual(inp, {"query": "abc"})
        self.assertIsNone(final)

    def test_dot_notation_injects_subaction(self) -> None:
        name, inp, _ = _parse_action(
            'Action: stock.analyse\nAction Input: {"tickers": ["AAPL"]}'
        )
        self.assertEqual(name, "stock")
        self.assertEqual(inp["action"], "analyse")
        self.assertEqual(inp["tickers"], ["AAPL"])

    def test_explicit_action_field_wins_over_dot_notation(self) -> None:
        name, inp, _ = _parse_action(
            'Action: stock.screen\nAction Input: {"action": "analyse", "sector": "tech"}'
        )
        self.assertEqual(name, "stock")
        self.assertEqual(inp["action"], "analyse")

    def test_markdown_fenced_json_fallback(self) -> None:
        text = 'Action: search\nAction Input:\n```json\n{"query": "x"}\n```'
        name, inp, _ = _parse_action(text)
        self.assertEqual(name, "search")
        self.assertEqual(inp, {"query": "x"})

    def test_action_without_input_returns_empty_dict(self) -> None:
        name, inp, final = _parse_action("Thought: go.\nAction: search")
        self.assertEqual(name, "search")
        self.assertEqual(inp, {})
        self.assertIsNone(final)

    def test_dot_notation_without_input_keeps_subaction(self) -> None:
        name, inp, _ = _parse_action("Action: stock.report")
        self.assertEqual(name, "stock")
        self.assertEqual(inp, {"action": "report"})

    def test_no_action_no_final_returns_all_none(self) -> None:
        name, inp, final = _parse_action("Thought: I am still considering options.")
        self.assertIsNone(name)
        self.assertIsNone(inp)
        self.assertIsNone(final)


@unittest.skipUnless(_estimate_tokens is not None, "agent dependencies not installed")
class TokenEstimateTests(unittest.TestCase):
    def test_estimate_is_total_chars_over_four(self) -> None:
        msgs = [{"role": "user", "content": "a" * 40}]
        self.assertEqual(_estimate_tokens(msgs), 10)

    def test_estimate_sums_across_messages(self) -> None:
        msgs = [
            {"role": "user", "content": "a" * 20},
            {"role": "assistant", "content": "b" * 20},
        ]
        self.assertEqual(_estimate_tokens(msgs), 10)


@unittest.skipUnless(_trim_messages is not None, "agent dependencies not installed")
class TrimMessagesTests(unittest.TestCase):
    def test_under_budget_returns_same_object(self) -> None:
        msgs = [{"role": "user", "content": "small"}]
        self.assertIs(_trim_messages(msgs, max_tokens=10_000), msgs)

    def test_drops_oldest_observations_keeping_first_message(self) -> None:
        first = {"role": "user", "content": "TASK"}
        msgs = [first] + [
            {"role": "user", "content": "Observation: " + "x" * 4000}
            for _ in range(3)
        ]
        result = _trim_messages(msgs, max_tokens=500)
        self.assertIs(result[0], first)
        self.assertEqual(len(result), 1)

    def test_drops_assistant_messages_when_no_observations(self) -> None:
        first = {"role": "user", "content": "TASK"}
        msgs = [
            first,
            {"role": "assistant", "content": "a" * 4000},
            {"role": "assistant", "content": "b" * 4000},
        ]
        result = _trim_messages(msgs, max_tokens=500)
        self.assertIs(result[0], first)
        self.assertEqual(len(result), 1)


class _FakeMemory:
    async def search(self, query, top_k=3):
        return []

    async def add(self, text):
        return None


class _FakeTool:
    name = "faketool"
    description = "a fake tool for tests"
    parameters: dict = {}

    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def run(self, action_input):
        self.calls.append(action_input)
        return "TOOL_RESULT"


class _FakeRouter:
    """Returns scripted responses; reuses the last one once the script runs out."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.complete_calls = 0

    def _next(self) -> str:
        idx = min(self.complete_calls, len(self._responses) - 1)
        self.complete_calls += 1
        return self._responses[idx]

    async def complete(self, *, system, messages, temperature=0.2):
        return self._next()

    async def complete_stream(self, *, system, messages, temperature=0.2):
        resp = self._next()
        mid = len(resp) // 2
        yield resp[:mid]
        yield resp[mid:]


def _make_agent(responses) -> "AgentCore":
    agent = AgentCore.__new__(AgentCore)
    agent.router = _FakeRouter(responses)
    agent.memory = _FakeMemory()
    tool = _FakeTool()
    agent.tools = [tool]
    agent._tool_map = {tool.name: tool}
    return agent


@unittest.skipUnless(AgentCore is not None, "agent dependencies not installed")
class RunLoopTests(unittest.IsolatedAsyncioTestCase):
    async def test_tool_call_then_final_answer(self) -> None:
        agent = _make_agent(
            [
                'Thought: need data.\nAction: faketool\nAction Input: {"x": 1}',
                "Thought: done.\nFinal Answer: The answer is 42.",
            ]
        )
        result = await agent.run("question", skip_memory=True)
        self.assertEqual(result, "The answer is 42.")
        self.assertEqual(agent.tools[0].calls, [{"x": 1}])

    async def test_immediate_final_answer_skips_tools(self) -> None:
        agent = _make_agent(["Final Answer: hi there"])
        result = await agent.run("question", skip_memory=True)
        self.assertEqual(result, "hi there")
        self.assertEqual(agent.tools[0].calls, [])

    async def test_unknown_tool_yields_recoverable_observation(self) -> None:
        agent = _make_agent(
            [
                "Action: ghost\nAction Input: {}",
                "Final Answer: recovered",
            ]
        )
        result = await agent.run("question", skip_memory=True)
        self.assertEqual(result, "recovered")
        self.assertEqual(agent.tools[0].calls, [])

    async def test_max_steps_returns_fallback_message(self) -> None:
        agent = _make_agent(['Action: faketool\nAction Input: {}'])  # never finalises
        with mock.patch("agent.core.MAX_STEPS", 3):
            result = await agent.run("question", skip_memory=True)
        self.assertIn("maximum number of reasoning steps", result)

    async def test_streaming_collects_chunks_and_returns_final(self) -> None:
        agent = _make_agent(["Final Answer: streamed"])
        chunks: list[str] = []
        result = await agent.run("question", on_chunk=chunks.append, skip_memory=True)
        self.assertEqual(result, "streamed")
        self.assertIn("streamed", "".join(chunks))


if __name__ == "__main__":
    unittest.main()
