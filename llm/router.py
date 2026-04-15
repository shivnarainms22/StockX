"""
StockX — LLM Router
Priority order: NVIDIA NIM → Anthropic → OpenAI
Falls back automatically if a provider is unavailable or a key is missing/placeholder.
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, AsyncGenerator

import httpx

from services.diagnostics import (
    record_provider_attempt,
    record_provider_failure,
    record_provider_success,
)

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Cloud providers
# ------------------------------------------------------------------
_NVIDIA_BASE      = "https://integrate.api.nvidia.com/v1"
_NVIDIA_MODEL     = "meta/llama-3.1-70b-instruct"

_ANTHROPIC_BASE    = "https://api.anthropic.com/v1"
_ANTHROPIC_MODEL   = "claude-sonnet-4-6"
_ANTHROPIC_VERSION = "2023-06-01"

_OPENAI_BASE  = "https://api.openai.com/v1"
_OPENAI_MODEL = "gpt-4o-mini"

_TIMEOUT = httpx.Timeout(60.0)

_PLACEHOLDERS = {
    "nvapi-your-key-here",
    "sk-ant-your-key-here",
    "sk-your-key-here",
}

# Per-provider maximum output token limits
_MAX_OUTPUT: dict[str, int] = {
    "NVIDIA NIM": 4096,
    "Anthropic":  8192,
    "OpenAI":    16384,
}


class LLMRouter:
    def __init__(self) -> None:
        self.nvidia_key    = os.getenv("NVIDIA_API_KEY", "")
        self.anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
        self.openai_key    = os.getenv("OPENAI_API_KEY", "")

    def _key_valid(self, key: str) -> bool:
        return bool(key) and key not in _PLACEHOLDERS

    def _get_providers(self) -> list[tuple[str, Any, Any]]:
        """Return list of (name, complete_fn, stream_fn) for available providers."""
        providers: list[tuple[str, Any, Any]] = []
        if self._key_valid(self.nvidia_key):
            providers.append(("NVIDIA NIM", self._call_nvidia, self._stream_nvidia))
        if self._key_valid(self.anthropic_key):
            providers.append(("Anthropic", self._call_anthropic, self._stream_anthropic))
        if self._key_valid(self.openai_key):
            providers.append(("OpenAI", self._call_openai, self._stream_openai))
        return providers

    async def complete(
        self,
        *,
        system: str,
        messages: list[dict[str, str]],
        temperature: float = 0.2,
    ) -> str:
        providers = self._get_providers()

        if not providers:
            raise RuntimeError(
                "No LLM provider available. "
                "Set a valid API key in .env (NVIDIA_API_KEY, ANTHROPIC_API_KEY, or OPENAI_API_KEY)."
            )

        last_error: Exception | None = None
        for idx, (name, fn, _) in enumerate(providers):
            start = time.perf_counter()
            try:
                logger.info("Trying provider: %s", name)
                record_provider_attempt(name)
                result = await fn(
                    system=system,
                    messages=messages,
                    max_tokens=_MAX_OUTPUT[name],
                    temperature=temperature,
                )
                latency_ms = (time.perf_counter() - start) * 1000
                record_provider_success(name, latency_ms, fallback_depth=idx)
                logger.info("Provider %s succeeded", name)
                return result
            except Exception as exc:
                logger.warning("Provider %s failed: %s", name, exc)
                record_provider_failure(name, str(exc))
                last_error = exc

        raise RuntimeError(f"All LLM providers failed. Last error: {last_error}")

    async def complete_stream(
        self,
        *,
        system: str,
        messages: list[dict[str, str]],
        temperature: float = 0.2,
    ) -> AsyncGenerator[str, None]:
        """Stream LLM response as text chunks. Falls back to non-streaming on error."""
        providers = self._get_providers()

        if not providers:
            raise RuntimeError(
                "No LLM provider available. "
                "Set a valid API key in .env (NVIDIA_API_KEY, ANTHROPIC_API_KEY, or OPENAI_API_KEY)."
            )

        last_error: Exception | None = None
        for idx, (name, complete_fn, stream_fn) in enumerate(providers):
            start = time.perf_counter()
            gen = stream_fn(
                system=system,
                messages=messages,
                max_tokens=_MAX_OUTPUT[name],
                temperature=temperature,
            )
            try:
                logger.info("Streaming via provider: %s", name)
                record_provider_attempt(name)
                async for chunk in gen:
                    yield chunk
                latency_ms = (time.perf_counter() - start) * 1000
                record_provider_success(name, latency_ms, fallback_depth=idx)
                return
            except Exception as exc:
                logger.warning("Provider %s streaming failed: %s — trying next", name, exc)
                record_provider_failure(name, str(exc))
                last_error = exc
            finally:
                await gen.aclose()

        raise RuntimeError(f"All streaming providers failed. Last error: {last_error}")

    # ------------------------------------------------------------------
    # NVIDIA NIM  (OpenAI-compatible)
    # ------------------------------------------------------------------
    async def _call_nvidia(
        self,
        *,
        system: str,
        messages: list[dict[str, str]],
        max_tokens: int,
        temperature: float,
    ) -> str:
        payload: dict[str, Any] = {
            "model": _NVIDIA_MODEL,
            "messages": [{"role": "system", "content": system}] + messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{_NVIDIA_BASE}/chat/completions",
                headers={"Authorization": f"Bearer {self.nvidia_key}",
                         "Content-Type": "application/json"},
                json=payload,
            )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    async def _stream_nvidia(
        self,
        *,
        system: str,
        messages: list[dict[str, str]],
        max_tokens: int,
        temperature: float,
    ) -> AsyncGenerator[str, None]:
        payload: dict[str, Any] = {
            "model": _NVIDIA_MODEL,
            "messages": [{"role": "system", "content": system}] + messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            async with client.stream(
                "POST",
                f"{_NVIDIA_BASE}/chat/completions",
                headers={"Authorization": f"Bearer {self.nvidia_key}",
                         "Content-Type": "application/json"},
                json=payload,
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data_str = line[6:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        delta = data["choices"][0]["delta"].get("content", "")
                        if delta:
                            yield delta
                    except (json.JSONDecodeError, KeyError):
                        continue

    # ------------------------------------------------------------------
    # Anthropic
    # ------------------------------------------------------------------
    async def _call_anthropic(
        self,
        *,
        system: str,
        messages: list[dict[str, str]],
        max_tokens: int,
        temperature: float,
    ) -> str:
        payload: dict[str, Any] = {
            "model": _ANTHROPIC_MODEL,
            "system": system,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{_ANTHROPIC_BASE}/messages",
                headers={"x-api-key": self.anthropic_key,
                         "anthropic-version": _ANTHROPIC_VERSION,
                         "Content-Type": "application/json"},
                json=payload,
            )
        resp.raise_for_status()
        return resp.json()["content"][0]["text"]

    async def _stream_anthropic(
        self,
        *,
        system: str,
        messages: list[dict[str, str]],
        max_tokens: int,
        temperature: float,
    ) -> AsyncGenerator[str, None]:
        payload: dict[str, Any] = {
            "model": _ANTHROPIC_MODEL,
            "system": system,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            async with client.stream(
                "POST",
                f"{_ANTHROPIC_BASE}/messages",
                headers={"x-api-key": self.anthropic_key,
                         "anthropic-version": _ANTHROPIC_VERSION,
                         "Content-Type": "application/json"},
                json=payload,
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data_str = line[6:].strip()
                    try:
                        data = json.loads(data_str)
                        if data.get("type") == "content_block_delta":
                            delta = data.get("delta", {}).get("text", "")
                            if delta:
                                yield delta
                    except (json.JSONDecodeError, KeyError):
                        continue

    # ------------------------------------------------------------------
    # OpenAI
    # ------------------------------------------------------------------
    async def _call_openai(
        self,
        *,
        system: str,
        messages: list[dict[str, str]],
        max_tokens: int,
        temperature: float,
    ) -> str:
        payload: dict[str, Any] = {
            "model": _OPENAI_MODEL,
            "messages": [{"role": "system", "content": system}] + messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{_OPENAI_BASE}/chat/completions",
                headers={"Authorization": f"Bearer {self.openai_key}",
                         "Content-Type": "application/json"},
                json=payload,
            )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    async def _stream_openai(
        self,
        *,
        system: str,
        messages: list[dict[str, str]],
        max_tokens: int,
        temperature: float,
    ) -> AsyncGenerator[str, None]:
        payload: dict[str, Any] = {
            "model": _OPENAI_MODEL,
            "messages": [{"role": "system", "content": system}] + messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            async with client.stream(
                "POST",
                f"{_OPENAI_BASE}/chat/completions",
                headers={"Authorization": f"Bearer {self.openai_key}",
                         "Content-Type": "application/json"},
                json=payload,
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data_str = line[6:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        delta = data["choices"][0]["delta"].get("content", "")
                        if delta:
                            yield delta
                    except (json.JSONDecodeError, KeyError):
                        continue
