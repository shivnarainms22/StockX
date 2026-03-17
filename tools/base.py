"""
StockX — Base Tool
All tools inherit from BaseTool.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseTool(ABC):
    """Abstract base class for all StockX tools."""

    name: str = ""
    description: str = ""
    parameters: dict[str, Any] | None = None  # JSON schema for arguments

    @abstractmethod
    async def run(self, params: dict[str, Any]) -> str:
        """Execute the tool and return a string observation."""
        ...

    def _require(self, params: dict[str, Any], key: str) -> Any:
        """Raise a clear error if a required parameter is missing."""
        if key not in params or params[key] is None:
            raise ValueError(f"Tool '{self.name}' requires parameter '{key}'")
        return params[key]
