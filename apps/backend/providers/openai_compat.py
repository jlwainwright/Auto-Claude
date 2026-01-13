"""
OpenAI-compatible client wrapper with tool execution.

This module provides a minimal async interface compatible with the subset of the
Claude Agent SDK client API used throughout this repo:
  - async with client
  - await client.query(prompt)
  - async for msg in client.receive_response(): ...

It is intended for OpenAI-compatible providers like Z.AI (GLM models).
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncIterator
from urllib.parse import quote_plus

import httpx

from security import validate_command

logger = logging.getLogger(__name__)

# =============================================================================
# Defaults / configuration
# =============================================================================

_DEFAULT_TIMEOUT_SECONDS = float(os.environ.get("OPENAI_COMPAT_TIMEOUT_SECONDS", "120.0"))
_DEFAULT_CONNECT_TIMEOUT_SECONDS = float(
    os.environ.get("OPENAI_COMPAT_CONNECT_TIMEOUT_SECONDS", "20.0")
)

# Max characters to return from tools to avoid blowing up model context.
_MAX_TOOL_OUTPUT_CHARS = int(os.environ.get("OPENAI_COMPAT_MAX_TOOL_OUTPUT_CHARS", "50000"))

# =============================================================================
# Tool schemas (OpenAI function calling)
# =============================================================================

SUPPORTED_TOOLS: set[str] = {
    "Bash",
    "Edit",
    "Glob",
    "Grep",
    "Read",
    "Write",
    "WebFetch",
    "WebSearch",
}


def _tool_schema(name: str, description: str, properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


TOOL_SCHEMAS: dict[str, dict[str, Any]] = {
    "Read": _tool_schema(
        "Read",
        "Read a file from the workspace.",
        {"file_path": {"type": "string"}},
        ["file_path"],
    ),
    "Write": _tool_schema(
        "Write",
        "Write a file to the workspace (overwrites if exists).",
        {"file_path": {"type": "string"}, "content": {"type": "string"}},
        ["file_path", "content"],
    ),
    "Edit": _tool_schema(
        "Edit",
        "Edit a file by replacing an exact string match.",
        {
            "file_path": {"type": "string"},
            "old_string": {"type": "string"},
            "new_string": {"type": "string"},
        },
        ["file_path", "old_string", "new_string"],
    ),
    "Glob": _tool_schema(
        "Glob",
        "List files matching a glob pattern (relative to the working directory).",
        {"pattern": {"type": "string"}},
        ["pattern"],
    ),
    "Grep": _tool_schema(
        "Grep",
        "Search for a pattern in files under a path (relative to the working directory).",
        {"pattern": {"type": "string"}, "path": {"type": "string"}},
        ["pattern"],
    ),
    "Bash": _tool_schema(
        "Bash",
        "Run a shell command in the working directory.",
        {"command": {"type": "string"}},
        ["command"],
    ),
    "WebFetch": _tool_schema(
        "WebFetch",
        "Fetch a URL and return the response text.",
        {"url": {"type": "string"}},
        ["url"],
    ),
    "WebSearch": _tool_schema(
        "WebSearch",
        "Search the web for a query and return a short summary of results.",
        {"query": {"type": "string"}},
        ["query"],
    ),
}


# =============================================================================
# Message / block types (Claude-SDK-like)
# =============================================================================


@dataclass
class TextBlock:
    text: str


@dataclass
class ToolUseBlock:
    name: str
    input: dict[str, Any]


@dataclass
class ToolResultBlock:
    content: str
    is_error: bool = False


@dataclass
class AssistantMessage:
    content: list[Any]


@dataclass
class UserMessage:
    content: list[Any]


# =============================================================================
# Client
# =============================================================================


class OpenAICompatClient:
    """
    OpenAI-compatible client with a Claude-SDK-like interface.

    This client implements a simple tool loop:
      1) Send user prompt
      2) Yield assistant text/tool calls
      3) Execute tools locally
      4) Send tool results
      5) Repeat until assistant returns no tool calls
    """

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        system_prompt: str | None,
        allowed_tools: list[str] | None = None,
        cwd: str | Path | None = None,
        max_turns: int = 1000,
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
        connect_timeout_seconds: float = _DEFAULT_CONNECT_TIMEOUT_SECONDS,
    ) -> None:
        if not api_key.strip():
            raise ValueError("OpenAI-compatible provider api_key is required")

        self.model = model
        self.system_prompt = system_prompt
        self.max_turns = max_turns

        self.cwd = Path(cwd).resolve() if cwd else Path.cwd().resolve()

        # Filter to supported tools only (MCP tools etc. are ignored for compat clients)
        tools = allowed_tools or []
        self.supported_tools = [t for t in tools if t in SUPPORTED_TOOLS]
        self.tool_defs = [TOOL_SCHEMAS[t] for t in self.supported_tools if t in TOOL_SCHEMAS]

        base_url = base_url.rstrip("/")
        self._chat_url = f"{base_url}/chat/completions"

        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout_seconds, connect=connect_timeout_seconds)
        )

        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        self._messages: list[dict[str, Any]] = []
        if system_prompt:
            self._messages.append({"role": "system", "content": system_prompt})

    async def __aenter__(self) -> "OpenAICompatClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        await self.close()

    async def close(self) -> None:
        await self._client.aclose()

    async def query(self, prompt: str) -> None:
        if not prompt:
            raise ValueError("query prompt is required")
        self._messages.append({"role": "user", "content": prompt})

    async def receive_response(self) -> AsyncIterator[Any]:
        turns = 0

        while True:
            turns += 1
            if turns > self.max_turns:
                raise RuntimeError(f"Exceeded max_turns={self.max_turns} in OpenAICompatClient")

            response = await self._chat()
            message = (response.get("choices") or [{}])[0].get("message") or {}

            content_text = message.get("content") or ""
            tool_calls = message.get("tool_calls") or []

            blocks: list[Any] = []
            if content_text:
                blocks.append(TextBlock(text=content_text))

            for call in tool_calls:
                fn = call.get("function") or {}
                name = fn.get("name") or ""
                raw_args = fn.get("arguments") or "{}"
                args = self._parse_tool_args(raw_args)
                blocks.append(ToolUseBlock(name=name, input=args))

            yield AssistantMessage(content=blocks)

            # Add assistant message to conversation state (include tool_calls if present)
            assistant_entry: dict[str, Any] = {"role": "assistant", "content": content_text}
            if tool_calls:
                assistant_entry["tool_calls"] = tool_calls
            self._messages.append(assistant_entry)

            if not tool_calls:
                return

            # Execute tools and append results
            for call in tool_calls:
                call_id = call.get("id")
                fn = call.get("function") or {}
                tool_name = fn.get("name") or ""
                raw_args = fn.get("arguments") or "{}"
                tool_args = self._parse_tool_args(raw_args)

                result_text, is_error = await self._execute_tool(tool_name, tool_args)

                # Yield ToolResult in Claude-compatible shape
                yield UserMessage(
                    content=[ToolResultBlock(content=result_text, is_error=is_error)]
                )

                # Append tool result in OpenAI tool-message format
                if call_id:
                    self._messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call_id,
                            "content": result_text,
                        }
                    )
                else:
                    # Shouldn't happen, but keep conversation consistent
                    self._messages.append(
                        {
                            "role": "tool",
                            "content": result_text,
                        }
                    )

    async def _chat(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": self._messages,
        }

        if self.tool_defs:
            payload["tools"] = self.tool_defs
            payload["tool_choice"] = "auto"

        resp = await self._client.post(self._chat_url, headers=self._headers, json=payload)

        if resp.status_code >= 400:
            # Try to surface provider error payload for debugging.
            detail = resp.text
            raise RuntimeError(f"OpenAI-compatible API error {resp.status_code}: {detail}")

        return resp.json()

    def _parse_tool_args(self, raw_args: str) -> dict[str, Any]:
        raw = (raw_args or "").strip()
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
            return {"_args": parsed}
        except json.JSONDecodeError:
            # Some models return non-JSON or partially-JSON arguments.
            return {"_raw": raw}

    def _resolve_path(self, path_str: str) -> Path:
        if not path_str:
            raise ValueError("file_path is required")

        p = Path(path_str)
        if not p.is_absolute():
            p = self.cwd / p

        p = p.resolve()

        # Restrict file ops to within cwd for safety (matches Claude SDK permissions intent).
        if p != self.cwd and self.cwd not in p.parents:
            raise ValueError(f"Path escapes working directory: {path_str}")

        return p

    def _truncate(self, text: str) -> str:
        if len(text) <= _MAX_TOOL_OUTPUT_CHARS:
            return text
        return text[:_MAX_TOOL_OUTPUT_CHARS] + "\n... (truncated)"

    async def _execute_tool(self, tool_name: str, tool_input: dict[str, Any]) -> tuple[str, bool]:
        if tool_name not in SUPPORTED_TOOLS:
            return f"Unsupported tool: {tool_name}", True

        try:
            if tool_name == "Read":
                return self._tool_read(tool_input), False
            if tool_name == "Write":
                return self._tool_write(tool_input), False
            if tool_name == "Edit":
                return self._tool_edit(tool_input), False
            if tool_name == "Glob":
                return self._tool_glob(tool_input), False
            if tool_name == "Grep":
                return self._tool_grep(tool_input), False
            if tool_name == "Bash":
                return self._tool_bash(tool_input), False
            if tool_name == "WebFetch":
                return await self._tool_web_fetch(tool_input), False
            if tool_name == "WebSearch":
                return await self._tool_web_search(tool_input), False
        except Exception as e:
            logger.exception("Tool execution error")
            return f"{type(e).__name__}: {e}", True

        return f"Unhandled tool: {tool_name}", True

    def _tool_read(self, tool_input: dict[str, Any]) -> str:
        file_path = tool_input.get("file_path") or tool_input.get("path") or ""
        p = self._resolve_path(str(file_path))
        content = p.read_text(encoding="utf-8", errors="replace")
        return self._truncate(content)

    def _tool_write(self, tool_input: dict[str, Any]) -> str:
        file_path = tool_input.get("file_path") or tool_input.get("path") or ""
        content = tool_input.get("content")
        if content is None:
            raise ValueError("Write requires 'content'")
        p = self._resolve_path(str(file_path))
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(str(content), encoding="utf-8")
        return f"Wrote {p.relative_to(self.cwd)} ({len(str(content))} chars)"

    def _tool_edit(self, tool_input: dict[str, Any]) -> str:
        file_path = tool_input.get("file_path") or tool_input.get("path") or ""
        old = tool_input.get("old_string")
        new = tool_input.get("new_string")
        if old is None or new is None:
            raise ValueError("Edit requires 'old_string' and 'new_string'")

        p = self._resolve_path(str(file_path))
        content = p.read_text(encoding="utf-8", errors="replace")
        if str(old) not in content:
            raise ValueError("old_string not found in file")

        updated = content.replace(str(old), str(new), 1)
        p.write_text(updated, encoding="utf-8")
        return f"Edited {p.relative_to(self.cwd)}"

    def _tool_glob(self, tool_input: dict[str, Any]) -> str:
        import glob

        pattern = tool_input.get("pattern")
        if not pattern:
            raise ValueError("Glob requires 'pattern'")

        # Ensure pattern is evaluated from cwd.
        full_pattern = str((self.cwd / str(pattern)).resolve())
        matches = glob.glob(full_pattern, recursive=True)
        rel_matches: list[str] = []
        for m in matches:
            mp = Path(m).resolve()
            try:
                rel_matches.append(str(mp.relative_to(self.cwd)))
            except ValueError:
                # Outside cwd; ignore.
                continue

        rel_matches.sort()
        return self._truncate("\n".join(rel_matches))

    def _tool_grep(self, tool_input: dict[str, Any]) -> str:
        pattern = tool_input.get("pattern")
        if not pattern:
            raise ValueError("Grep requires 'pattern'")

        search_path = tool_input.get("path") or "."
        p = self._resolve_path(str(search_path))

        rg = shutil.which("rg")
        if rg:
            proc = subprocess.run(
                [rg, "-n", "--no-heading", "--color", "never", str(pattern), str(p)],
                cwd=str(self.cwd),
                capture_output=True,
                text=True,
            )
            out = proc.stdout + (("\n" + proc.stderr) if proc.stderr else "")
            return self._truncate(out.strip())

        # Fallback: naive grep for simple substrings/regex (best-effort).
        results: list[str] = []
        rx = re.compile(str(pattern))
        for file in p.rglob("*"):
            if not file.is_file():
                continue
            try:
                text = file.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            for i, line in enumerate(text.splitlines(), start=1):
                if rx.search(line):
                    try:
                        rel = str(file.resolve().relative_to(self.cwd))
                    except ValueError:
                        continue
                    results.append(f"{rel}:{i}:{line}")
                    if sum(len(r) for r in results) > _MAX_TOOL_OUTPUT_CHARS:
                        break
        return self._truncate("\n".join(results))

    def _tool_bash(self, tool_input: dict[str, Any]) -> str:
        command = tool_input.get("command")
        if not command:
            raise ValueError("Bash requires 'command'")

        allowed, reason = validate_command(str(command), self.cwd)
        if not allowed:
            return self._truncate(f"BLOCKED: {reason}")

        proc = subprocess.run(
            ["bash", "-lc", str(command)],
            cwd=str(self.cwd),
            capture_output=True,
            text=True,
        )

        output = proc.stdout
        if proc.stderr:
            output += ("\n" if output else "") + proc.stderr
        output = output.strip()

        if proc.returncode != 0:
            return self._truncate(f"(exit {proc.returncode})\n{output}")

        return self._truncate(output or "(no output)")

    async def _tool_web_fetch(self, tool_input: dict[str, Any]) -> str:
        url = tool_input.get("url")
        if not url:
            raise ValueError("WebFetch requires 'url'")

        resp = await self._client.get(str(url), headers={"User-Agent": "Auto-Claude/1.0"})
        resp.raise_for_status()
        return self._truncate(resp.text)

    async def _tool_web_search(self, tool_input: dict[str, Any]) -> str:
        query = tool_input.get("query")
        if not query:
            raise ValueError("WebSearch requires 'query'")

        # DuckDuckGo instant answer API (no key, lightweight).
        url = (
            "https://api.duckduckgo.com/?q="
            + quote_plus(str(query))
            + "&format=json&no_redirect=1&no_html=1"
        )
        resp = await self._client.get(url, headers={"User-Agent": "Auto-Claude/1.0"})
        resp.raise_for_status()
        data = resp.json()

        abstract = (data.get("AbstractText") or "").strip()
        if abstract:
            return self._truncate(f"Abstract: {abstract}")

        related = data.get("RelatedTopics") or []
        items: list[str] = []
        for entry in related:
            if isinstance(entry, dict) and entry.get("Text"):
                items.append(str(entry["Text"]))
            if isinstance(entry, dict) and entry.get("Topics"):
                for sub in entry.get("Topics") or []:
                    if isinstance(sub, dict) and sub.get("Text"):
                        items.append(str(sub["Text"]))

        if not items:
            return "No results."

        return self._truncate("RelatedTopics:\n" + "\n".join(f"- {t}" for t in items[:10]))
