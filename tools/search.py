"""
StockX — Search Tool
Uses a real search API (Brave or Tavily) when a key is configured.
Falls back to DuckDuckGo HTML scrape if no API key is set.
Also supports fetching full page content from a URL.
"""
from __future__ import annotations

import logging
import os
import re
from typing import Any
from urllib.parse import quote_plus

import httpx

from tools.base import BaseTool

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(30.0)

# ── Search result cache (item 2) ─────────────────────────────────────────────
import time as _time
_search_cache: dict[str, tuple[float, list]] = {}  # {query: (timestamp, results)}
_SEARCH_TTL = 600  # 10 minutes

_BRAVE_BASE  = "https://api.search.brave.com/res/v1/web/search"
_TAVILY_BASE = "https://api.tavily.com/search"
_DDG_URL     = "https://html.duckduckgo.com/html/"

_PLACEHOLDER_KEYS = {"your-brave-key-here", "your-tavily-key-here", ""}


class SearchTool(BaseTool):
    name = "search"
    description = (
        "Search the web for up-to-date information or fetch a page's content. "
        "Actions: "
        "'search' — query the web, returns numbered results with title/URL/snippet; "
        "'summarise' — search and return plain text summary of top results; "
        "'fetch' — download and return the readable text content of a specific URL."
    )
    parameters = {
        "action": "string — one of: search | summarise | fetch",
        "query": "string — the search query (for search/summarise actions)",
        "url": "string — the URL to fetch content from (for fetch action)",
        "num_results": "integer (optional) — number of results to return (default 5)",
    }

    async def run(self, params: dict[str, Any]) -> str:
        # Read keys dynamically so settings changes take effect immediately
        api_key  = os.getenv("SEARCH_API_KEY", "").strip()
        provider = os.getenv("SEARCH_PROVIDER", "brave").lower()

        action = params.get("action", "search").lower()

        if action == "fetch":
            url = params.get("url", "").strip()
            if not url:
                return "Error: 'url' parameter is required for fetch action."
            return await self._fetch_page(url)

        if action not in ("search", "summarise"):
            return f"Unknown action '{action}'. Use: search, summarise, fetch"

        query = self._require(params, "query")
        num   = int(params.get("num_results", 5))

        results = await self._fetch_results(query, num, api_key, provider)

        if action == "summarise":
            if not results:
                return f"No results found for: {query}"
            lines = [f"{r['title']}\n{r['snippet']}" for r in results if r.get("title") or r.get("snippet")]
            return "\n\n".join(lines) if lines else f"No usable results for: {query}"

        # action == "search"
        if not results:
            return f"No results found for: {query}"
        lines = []
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. {r['title']}\n   {r['url']}\n   {r['snippet']}")
        return "\n\n".join(lines)

    async def _fetch_results(
        self, query: str, num: int, api_key: str, provider: str
    ) -> list[dict[str, str]]:
        """Try configured API first, fall back to DuckDuckGo HTML scrape."""
        # Cache check (item 2)
        cache_key = f"{query}|{num}|{provider}"
        cached = _search_cache.get(cache_key)
        if cached and (_time.time() - cached[0]) < _SEARCH_TTL:
            return cached[1]

        if api_key and api_key not in _PLACEHOLDER_KEYS:
            try:
                if provider == "tavily":
                    results = await self._fetch_tavily(query, num, api_key)
                else:
                    results = await self._fetch_brave(query, num, api_key)
                _search_cache[cache_key] = (_time.time(), results)
                return results
            except Exception as exc:
                logger.warning("Search API (%s) failed: %s — falling back to DDG scrape", provider, exc)

        results = await self._fetch_ddg(query, num)
        _search_cache[cache_key] = (_time.time(), results)
        return results

    async def _fetch_brave(self, query: str, num: int, api_key: str) -> list[dict[str, str]]:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                _BRAVE_BASE,
                params={"q": query, "count": num},
                headers={
                    "Accept": "application/json",
                    "Accept-Encoding": "gzip",
                    "X-Subscription-Token": api_key,
                },
            )
        resp.raise_for_status()
        data = resp.json()
        results = []
        for item in data.get("web", {}).get("results", [])[:num]:
            results.append({
                "title":   item.get("title", ""),
                "url":     item.get("url", ""),
                "snippet": item.get("description", ""),
            })
        return results

    async def _fetch_tavily(self, query: str, num: int, api_key: str) -> list[dict[str, str]]:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                _TAVILY_BASE,
                json={
                    "api_key":      api_key,
                    "query":        query,
                    "max_results":  num,
                    "search_depth": "basic",
                },
                headers={"Content-Type": "application/json"},
            )
        resp.raise_for_status()
        data = resp.json()
        results = []
        for item in data.get("results", [])[:num]:
            results.append({
                "title":   item.get("title", ""),
                "url":     item.get("url", ""),
                "snippet": item.get("content", ""),
            })
        return results

    async def _fetch_ddg(self, query: str, num: int) -> list[dict[str, str]]:
        """DuckDuckGo HTML fallback — no API key required, scraper-friendly."""
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        }
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=True) as client:
                resp = await client.post(
                    _DDG_URL,
                    data={"q": query, "kl": "us-en"},
                    headers=headers,
                )
            html = resp.text

            results: list[dict[str, str]] = []

            # Extract result blocks: title, URL, snippet
            # DDG HTML structure: <a class="result__a" href="...">title</a>
            #                     <a class="result__snippet">snippet</a>
            title_pattern   = re.compile(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.DOTALL)
            snippet_pattern = re.compile(r'class="result__snippet"[^>]*>(.*?)</a>', re.DOTALL)

            titles   = title_pattern.findall(html)
            snippets = snippet_pattern.findall(html)

            for i, (url, title) in enumerate(titles[:num]):
                snippet = snippets[i] if i < len(snippets) else ""
                # Strip HTML tags from title and snippet
                title   = re.sub(r"<[^>]+>", "", title).strip()
                snippet = re.sub(r"<[^>]+>", "", snippet).strip()
                # DDG wraps real URLs in a redirect — decode if needed
                if url.startswith("//duckduckgo.com/l/?uddg="):
                    from urllib.parse import unquote
                    url = unquote(url.split("uddg=")[-1].split("&")[0])
                results.append({"title": title, "url": url, "snippet": snippet})

            if not results:
                logger.warning("DDG scrape returned no results for: %s", query)
            return results

        except Exception as exc:
            logger.warning("DuckDuckGo scrape failed: %s", exc)
            return []

    async def _fetch_page(self, url: str) -> str:
        """Fetch a URL and return its readable text content (strips HTML tags)."""
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        }
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=True) as client:
                resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            html = resp.text

            # Remove scripts, styles, and navigation noise
            html = re.sub(r"<(script|style|nav|footer|header)[^>]*>.*?</\1>", "", html,
                          flags=re.DOTALL | re.IGNORECASE)
            # Strip remaining tags
            text = re.sub(r"<[^>]+>", " ", html)
            # Collapse whitespace
            text = re.sub(r"\s{2,}", "\n", text).strip()
            # Decode HTML entities
            text = text.replace("&amp;", "&").replace("&lt;", "<").replace(
                "&gt;", ">").replace("&quot;", '"').replace("&#39;", "'").replace("&nbsp;", " ")

            # Cap at ~6000 chars to stay within token budget
            if len(text) > 6000:
                text = text[:6000] + "\n\n[Content truncated — page has more text]"

            return text if text.strip() else "No readable content found at that URL."

        except httpx.HTTPStatusError as exc:
            return f"Error fetching page: HTTP {exc.response.status_code}"
        except Exception as exc:
            return f"Error fetching page: {exc}"
