"""
StockX — Core ReAct Engine
12-step reasoning loop with robust action parser.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from datetime import datetime
from typing import Any, Callable

from llm.router import LLMRouter
from memory.store import MemoryStore
from services.diagnostics import record_tool_call
from tools.base import BaseTool
from tools.search import SearchTool
from tools.stock import StockTool

logger = logging.getLogger(__name__)

MAX_STEPS = int(os.getenv("AGENT_MAX_STEPS", "12"))

# Token budget: ~80% of 128k context window; estimate at chars/4
_MAX_CONTEXT_TOKENS = int(os.getenv("AGENT_MAX_CONTEXT_TOKENS", "102400"))

SYSTEM_PROMPT = """\
You are StockX, a stock analysis AI agent. You help users analyse stocks, screen sectors, build portfolios, and stay on top of market news.

Available tools:
{tool_descriptions}

Reply in this EXACT format for each step:

Thought: <your reasoning>
Action: <tool_name>
Action Input: <JSON object with tool arguments>

When you have the final answer, reply with:

Thought: I now know the final answer.
Final Answer: <your complete response to the user>

Rules:
- For simple conversational messages (greetings, chitchat), math calculations, or questions you can answer from knowledge — go STRAIGHT to Final Answer. Do NOT call any tool.
- Only use tools when fresh market data or news is required.
- IMPORTANT: [Relevant memory] is historical context only. NEVER use it for stock prices, financial data, market analysis, or any live information — always call the appropriate tool to get fresh, up-to-date data.
- ONLY call tools from the list above. Never invent tool names.
- Action Input MUST be valid JSON containing ALL required parameters for the chosen tool.
- Never expose internal keys or memory details to the user.
- If a tool fails, reason about why and try an alternative approach.
- For web research tasks: first use search action='search' to find relevant URLs, then use search action='fetch' with the best URL to get full page content before writing your answer.
- When search snippets are too short to answer the question, always follow up with search action='fetch' on the most relevant URL.
- For stock/investment questions use the 'stock' tool. The 'action' field MUST always be included inside the Action Input JSON — NEVER append it to the tool name (wrong: "Action: stock.analyse", right: "Action: stock" with {{"action":"analyse",...}} in Action Input).
- stock tool actions:
  * Analyse specific stocks/crypto: Action: stock  |  Action Input: {{"action":"analyse","tickers":["TSLA","AAPL"]}}  — accepts company names too e.g. "berkshire hathaway", "bitcoin"
  * Screen a sector for top picks: Action: stock  |  Action Input: {{"action":"screen","sector":"technology","top_n":5}}
  * Full investment report (screen + deep analysis): Action: stock  |  Action Input: {{"action":"report","sector":"all","top_n":5}}
- Valid sectors: technology, healthcare, finance, energy, consumer, industrials, semiconductors, software, ai, biotech, banks, payments, defense, ev, retail, pharma, gold, silver, etf, commodities, all
- The sector screener only covers US-listed stocks. If the user asks to screen a specific non-US market or country (e.g. "top Indian energy stocks", "best Korean tech stocks"), inform them that the screener is US-only, then offer to analyse specific tickers they provide or suggest well-known tickers for that market instead.
- For gold: Action Input: {{"action":"analyse","tickers":["GLD","IAU","GDX","NEM","GOLD"]}}  — GLD/IAU are physical gold ETFs, GDX is gold miners ETF.
- For silver: Action Input: {{"action":"screen","sector":"silver"}}  or  {{"action":"analyse","tickers":["SLV","PSLV","SIL","PAAS","AG"]}}
- For ETFs: Action Input: {{"action":"screen","sector":"etf"}}  or  {{"action":"analyse","tickers":["SPY","QQQ"]}}
- After stock analysis ALWAYS follow up with search tool for latest news on each ticker before your final answer.
- When presenting recommendations always include: rating, key signals, risks, short-term outlook AND long-term outlook (1-2 years), and a disclaimer that this is not financial advice.
- ALWAYS use the local currency of the stock/market being discussed. For example: UK stocks → GBP (£), European stocks → EUR (€), Japanese stocks → JPY (¥), Indian stocks → INR (₹), Hong Kong stocks → HKD (HK$), Canadian stocks → CAD (CA$). Never default to USD ($) for non-US securities.
"""


def _build_tool_descriptions(tools: list[BaseTool]) -> str:
    lines: list[str] = []
    for t in tools:
        lines.append(f"- {t.name}: {t.description}")
        if t.parameters:
            lines.append(f"  Parameters: {json.dumps(t.parameters)}")
    return "\n".join(lines)


def _parse_action(text: str) -> tuple[str | None, dict[str, Any] | None, str | None]:
    """
    Parse LLM output for Action / Action Input / Final Answer.
    Returns (action_name, action_input_dict, final_answer).
    """
    # Check for Final Answer first
    final_match = re.search(r"Final Answer\s*:\s*(.*)", text, re.IGNORECASE | re.DOTALL)
    if final_match:
        return None, None, final_match.group(1).strip()

    # Support both "Action: tool" and "Action: tool.subaction" dot-notation
    action_match = re.search(r"Action\s*:\s*(\w+)(?:\.(\w+))?", text, re.IGNORECASE)
    if not action_match:
        return None, None, None

    action_name = action_match.group(1).strip()
    sub_action   = action_match.group(2)  # e.g. "analyse" from "stock.analyse"

    # Try to extract JSON block after "Action Input:"
    input_match = re.search(
        r"Action Input\s*:\s*(\{.*?\}|\[.*?\])",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if input_match:
        raw = input_match.group(1).strip()
        try:
            action_input = json.loads(raw)
            # Inject sub-action if LLM used dot-notation and "action" not already in JSON
            if sub_action and "action" not in action_input:
                action_input["action"] = sub_action.lower()
            return action_name, action_input, None
        except json.JSONDecodeError:
            pass

    # Fallback: look for any JSON object after "Action Input:"
    input_fallback = re.search(
        r"Action Input\s*:\s*([\s\S]+?)(?=\nThought|\nAction|\nFinal Answer|$)",
        text,
        re.IGNORECASE,
    )
    if input_fallback:
        raw = input_fallback.group(1).strip()
        # Strip markdown code fences if present
        raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()
        try:
            action_input = json.loads(raw)
            if sub_action and "action" not in action_input:
                action_input["action"] = sub_action.lower()
            return action_name, action_input, None
        except json.JSONDecodeError:
            # Last resort: treat it as a plain string under "input" key
            params: dict[str, Any] = {"input": raw}
            if sub_action:
                params["action"] = sub_action.lower()
            return action_name, params, None

    return action_name, {"action": sub_action.lower()} if sub_action else {}, None


def _estimate_tokens(messages: list[dict[str, str]]) -> int:
    """Rough token estimate: total chars / 4."""
    return sum(len(m.get("content", "")) for m in messages) // 4


def _trim_messages(
    messages: list[dict[str, str]],
    max_tokens: int = _MAX_CONTEXT_TOKENS,
) -> list[dict[str, str]]:
    """
    If total estimated tokens exceed max_tokens, drop the oldest observation
    messages until within budget. Always keeps the first user message (original task).
    """
    if _estimate_tokens(messages) <= max_tokens or not messages:
        return messages

    first_msg = messages[0]
    rest = list(messages[1:])

    while _estimate_tokens([first_msg] + rest) > max_tokens and rest:
        # Drop oldest Observation (role=user starting with "Observation:") first
        for i, msg in enumerate(rest):
            if msg["role"] == "user" and msg.get("content", "").startswith("Observation:"):
                rest.pop(i)
                logger.debug("Trimmed observation at position %d to stay within token budget", i + 1)
                break
        else:
            # No observations left; drop oldest assistant message
            for i, msg in enumerate(rest):
                if msg["role"] == "assistant":
                    rest.pop(i)
                    logger.debug("Trimmed assistant message at position %d", i + 1)
                    break
            else:
                break  # Nothing left to trim

    return [first_msg] + rest


class AgentCore:
    def __init__(self) -> None:
        self.router = LLMRouter()
        self.memory = MemoryStore()
        self.tools: list[BaseTool] = [
            StockTool(),
            SearchTool(),
        ]
        self._tool_map: dict[str, BaseTool] = {t.name: t for t in self.tools}

    async def _get_tool(self, name: str) -> BaseTool | None:
        name_lower = name.lower()
        for key, tool in self._tool_map.items():
            if key.lower() == name_lower:
                return tool
        return None

    async def _run_tool_with_retry(
        self, tool: BaseTool, action_input: dict[str, Any]
    ) -> str:
        """Run a tool, retrying once after a 1-second delay on failure."""
        start = time.perf_counter()
        try:
            result = await tool.run(action_input)
            # Also retry if the tool returned an error string
            if isinstance(result, str) and result.startswith("Error:"):
                raise RuntimeError(result)
            record_tool_call(tool.name, (time.perf_counter() - start) * 1000, ok=True)
            return str(result)
        except Exception as exc:
            logger.warning("Tool %s failed: %s — retrying in 1s", tool.name, exc)
            await asyncio.sleep(1)
            try:
                result = await tool.run(action_input)
                logger.info("Tool %s retry succeeded", tool.name)
                record_tool_call(tool.name, (time.perf_counter() - start) * 1000, ok=True)
                return str(result)
            except Exception as exc2:
                logger.exception("Tool %s retry also failed", tool.name)
                record_tool_call(tool.name, (time.perf_counter() - start) * 1000, ok=False)
                return f"Tool error: {exc2}"

    async def run(
        self,
        task: str,
        history: list[dict[str, str]] | None = None,
        on_chunk: Callable[[str], None] | None = None,
        skip_memory: bool = False,
    ) -> str:
        """
        Run a task through the ReAct loop.

        Args:
            task:        The task/question from the user.
            history:     Optional prior conversation messages to prepend
                         (accumulated across chat turns in chat_mode).
            on_chunk:    Optional callback for streaming LLM output chunks.
                         When provided, chunks are passed to the callback as
                         they arrive and the step counter is suppressed.
            skip_memory: If True, skip ChromaDB memory search. Use this when
                         running from a background QThread to avoid onnxruntime
                         thread-safety crashes on Python 3.13.
        """
        logger.info("Task: %s", task)

        context_docs = [] if skip_memory else await self.memory.search(task, top_k=3)
        context_str = "\n".join(context_docs) if context_docs else ""

        system = SYSTEM_PROMPT.format(
            tool_descriptions=_build_tool_descriptions(self.tools)
        )

        messages: list[dict[str, str]] = []

        # Prepend prior conversation turns
        if history:
            messages.extend(history)

        if context_str:
            messages.append(
                {
                    "role": "user",
                    "content": f"[Relevant memory]\n{context_str}",
                }
            )
            messages.append({"role": "assistant", "content": "Understood."})

        messages.append({"role": "user", "content": task})

        step = 0
        while step < MAX_STEPS:
            step += 1

            # Trim messages if approaching token limit before each LLM call
            messages = _trim_messages(messages)

            if on_chunk:
                # Streaming mode: accumulate chunks, pass each to callback
                response = ""
                async for chunk in self.router.complete_stream(
                    system=system, messages=messages
                ):
                    on_chunk(chunk)
                    response += chunk
                # Ensure there's a newline after the streamed step output
                on_chunk("\n")
            else:
                # Non-streaming: print step counter with extracted thought
                response = await self.router.complete(
                    system=system,
                    messages=messages,
                )
                thought_match = re.search(
                    r"Thought\s*:\s*(.*?)(?=\nAction|\nFinal Answer|$)",
                    response,
                    re.DOTALL | re.IGNORECASE,
                )
                thought = thought_match.group(1).strip() if thought_match else "..."
                # Truncate very long thoughts for readability
                if len(thought) > 120:
                    thought = thought[:117] + "..."
                print(f"[Step {step}/{MAX_STEPS}] {thought}", flush=True)

            logger.debug("LLM response (step %d):\n%s", step, response)
            messages.append({"role": "assistant", "content": response})

            action_name, action_input, final_answer = _parse_action(response)

            if final_answer is not None:
                await self.memory.add(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] Task: {task}\nResult: {final_answer}")
                return final_answer

            if action_name is None:
                # No parseable action — treat entire response as final answer
                await self.memory.add(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] Task: {task}\nResult: {response}")
                return response

            tool = await self._get_tool(action_name)
            if tool is None:
                observation = (
                    f"Error: Tool '{action_name}' not found. "
                    f"Available: {', '.join(self._tool_map.keys())}"
                )
                logger.warning(observation)
            else:
                logger.info("Running tool: %s | input: %s", action_name, action_input)
                observation = await self._run_tool_with_retry(tool, action_input or {})

            messages.append(
                {
                    "role": "user",
                    "content": f"Observation: {observation}",
                }
            )

        return "I reached the maximum number of reasoning steps without a final answer. Please try rephrasing your request."
