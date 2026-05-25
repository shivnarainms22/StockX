"""Tests for the LLM router: key validation, provider ordering, and fallover.

All network methods are replaced with in-process fakes — no real HTTP calls.
"""
from __future__ import annotations

import unittest

try:
    from llm.router import LLMRouter, _MAX_OUTPUT
except ModuleNotFoundError:  # pragma: no cover - optional dependency guard
    LLMRouter = None
    _MAX_OUTPUT = None


def _router_with_keys(nvidia: str = "", anthropic: str = "", openai: str = "") -> "LLMRouter":
    """Build a router and force its keys directly, bypassing env coupling."""
    r = LLMRouter()
    r.nvidia_key = nvidia
    r.anthropic_key = anthropic
    r.openai_key = openai
    return r


@unittest.skipUnless(LLMRouter is not None, "llm router dependencies not installed")
class KeyValidationTests(unittest.TestCase):
    def test_empty_key_is_invalid(self) -> None:
        r = _router_with_keys()
        self.assertFalse(r._key_valid(""))

    def test_placeholder_key_is_invalid(self) -> None:
        r = _router_with_keys()
        self.assertFalse(r._key_valid("nvapi-your-key-here"))
        self.assertFalse(r._key_valid("sk-ant-your-key-here"))
        self.assertFalse(r._key_valid("sk-your-key-here"))

    def test_real_key_is_valid(self) -> None:
        r = _router_with_keys()
        self.assertTrue(r._key_valid("nvapi-real-token-123"))


@unittest.skipUnless(LLMRouter is not None, "llm router dependencies not installed")
class ProviderOrderingTests(unittest.TestCase):
    def _names(self, **keys: str) -> list[str]:
        return [name for name, _, _ in _router_with_keys(**keys)._get_providers()]

    def test_priority_order_is_nvidia_anthropic_openai(self) -> None:
        names = self._names(nvidia="nvapi-x", anthropic="sk-ant-x", openai="sk-x")
        self.assertEqual(names, ["NVIDIA NIM", "Anthropic", "OpenAI"])

    def test_missing_key_is_skipped_preserving_order(self) -> None:
        names = self._names(nvidia="", anthropic="sk-ant-x", openai="sk-x")
        self.assertEqual(names, ["Anthropic", "OpenAI"])

    def test_placeholder_key_is_skipped(self) -> None:
        names = self._names(nvidia="nvapi-your-key-here", anthropic="sk-ant-x")
        self.assertEqual(names, ["Anthropic"])

    def test_no_valid_keys_yields_no_providers(self) -> None:
        self.assertEqual(self._names(), [])


@unittest.skipUnless(LLMRouter is not None, "llm router dependencies not installed")
class CompleteFalloverTests(unittest.IsolatedAsyncioTestCase):
    async def test_no_provider_raises(self) -> None:
        r = _router_with_keys()
        with self.assertRaises(RuntimeError):
            await r.complete(system="s", messages=[{"role": "user", "content": "hi"}])

    async def test_first_provider_success_short_circuits(self) -> None:
        r = _router_with_keys(nvidia="nvapi-x", anthropic="sk-ant-x")
        anthropic_called = False

        async def ok_nvidia(**_kwargs):
            return "from-nvidia"

        async def should_not_run(**_kwargs):
            nonlocal anthropic_called
            anthropic_called = True
            return "from-anthropic"

        r._call_nvidia = ok_nvidia
        r._call_anthropic = should_not_run

        result = await r.complete(system="s", messages=[{"role": "user", "content": "hi"}])
        self.assertEqual(result, "from-nvidia")
        self.assertFalse(anthropic_called)

    async def test_falls_over_to_next_provider_on_failure(self) -> None:
        r = _router_with_keys(nvidia="nvapi-x", anthropic="sk-ant-x")

        async def bad_nvidia(**_kwargs):
            raise RuntimeError("nvidia down")

        async def ok_anthropic(**_kwargs):
            return "from-anthropic"

        r._call_nvidia = bad_nvidia
        r._call_anthropic = ok_anthropic

        result = await r.complete(system="s", messages=[{"role": "user", "content": "hi"}])
        self.assertEqual(result, "from-anthropic")

    async def test_all_providers_failing_raises_with_last_error(self) -> None:
        r = _router_with_keys(nvidia="nvapi-x", openai="sk-x")

        async def bad_nvidia(**_kwargs):
            raise RuntimeError("nvidia down")

        async def bad_openai(**_kwargs):
            raise RuntimeError("openai down")

        r._call_nvidia = bad_nvidia
        r._call_openai = bad_openai

        with self.assertRaises(RuntimeError) as ctx:
            await r.complete(system="s", messages=[{"role": "user", "content": "hi"}])
        self.assertIn("openai down", str(ctx.exception))

    async def test_max_tokens_matches_provider_limit(self) -> None:
        r = _router_with_keys(anthropic="sk-ant-x")
        seen: dict[str, int] = {}

        async def capture(**kwargs):
            seen["max_tokens"] = kwargs["max_tokens"]
            return "ok"

        r._call_anthropic = capture
        await r.complete(system="s", messages=[{"role": "user", "content": "hi"}])
        self.assertEqual(seen["max_tokens"], _MAX_OUTPUT["Anthropic"])


@unittest.skipUnless(LLMRouter is not None, "llm router dependencies not installed")
class StreamFalloverTests(unittest.IsolatedAsyncioTestCase):
    async def test_stream_falls_over_to_next_provider(self) -> None:
        r = _router_with_keys(nvidia="nvapi-x", anthropic="sk-ant-x")

        async def bad_stream(**_kwargs):
            raise RuntimeError("stream boom")
            yield  # pragma: no cover - makes this a generator

        async def good_stream(**_kwargs):
            yield "hel"
            yield "lo"

        r._stream_nvidia = bad_stream
        r._stream_anthropic = good_stream

        chunks = [
            c
            async for c in r.complete_stream(
                system="s", messages=[{"role": "user", "content": "hi"}]
            )
        ]
        self.assertEqual("".join(chunks), "hello")


if __name__ == "__main__":
    unittest.main()
