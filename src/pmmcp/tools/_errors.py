"""Shared MCP error formatting for all tool modules."""

from __future__ import annotations


def _mcp_error(category: str, description: str, suggestion: str) -> dict:
    text = f"Error: {category}\n\nDetails: {description}\nSuggestion: {suggestion}"
    return {"content": [{"type": "text", "text": text}], "isError": True}
