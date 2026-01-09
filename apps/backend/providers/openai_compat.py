"""
OpenAI-compatible client wrapper with tool execution.

Provides a minimal async interface compatible with the Claude SDK usage pattern
(query + receive_response) for non-Claude providers (e.g., Z.AI GLM).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

import httpx

from openai import AsyncOpenAI

from security import validate_command

logger = logging.getLogger(__name__)

# Default timeout for OpenAI-compatible API calls (120 seconds)
# Z.AI and other providers may have different latency characteristics
# Can be overridden via OPENAI_COMPAT_TIMEOUT_SECONDS environment variable
_DEFAULT_TIMEOUT_SECONDS = float(os.environ.get("OPENAI_COMPAT_TIMEOUT_SECONDS", "120.0"))
_DEFAULT_CONNECT_TIMEOUT = float(os.environ.get("OPENAI_COMPAT_CONNECT_TIMEOUT", "20.0"))
DEFAULT_TIMEOUT = httpx.Timeout(_DEFAULT_TIMEOUT_SECONDS, connect=_DEFAULT_CONNECT_TIMEOUT)

SUPPORTED_TOOLS: set[str] = {
    "Read",
    "Write",
    "Edit",
    "Glob",
    "Grep",
    "Bash",
    "WebFetch",
    "WebSearch",
}

TOOL_SCHEMAS: dict[str, dict[str, Any]] = {
    "Read": {
        "type": "object",
        "properties": {"file_path": {"type": "string"}},
        "required": ["file_path"],
    },
    "Write": {
        "type": "object",
        "properties": {
            "file_path": {"type": "string"},
            "content": {"type": "string"},
        },
        "required": ["file_path", "content"],
    },
    "Edit": {
        "type": "object",
        "properties": {
            "file_path": {"type": "string"},
            "old_string": {"type": "string"},
            "new_string": {"type": "string"},
        },
        "required": ["file_path", "old_string", "new_string"],
    },
    "Glob": {
        "type": "object",
        "properties": {"pattern": {"type": "string"}},
        "required": ["pattern"],
    },
    "Grep": {
        "type": "object",
        "properties": {
            "pattern": {"type": "string"},
            "path": {"type": "string"},
        },
        "required": ["pattern"],
    },
    "Bash": {
        "type": "object",
        "properties": {"command": {"type": "string"}},
        "required": ["command"],
    },
    "WebFetch": {
        "type": "object",
        "properties": {"url": {"type": "string"}},
        "required": ["url"],
    },
    "WebSearch": {
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
    },
}


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


class OpenAICompatClient:
    def __init__(
        self,
        model: str,
        system_prompt: str,
        allowed_tools: list[str] | None,
        project_dir: Path,
        spec_dir: Path,
        api_key: str,
        base_url: str | None = None,
        max_turns: int = 20,
    ) -> None:
        self.model = model
        self.system_prompt = system_prompt
        self.allowed_tools = allowed_tools or []
        self.project_dir = Path(project_dir).resolve()
        self.spec_dir = Path(spec_dir).resolve()
        self.max_turns = max_turns
        self.base_url = base_url
        # Use explicit timeout to prevent hangs on slow/non-responsive providers
        # 120s timeout for API calls, 20s for connection
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=DEFAULT_TIMEOUT,
        )
        self._events: list[Any] = []
        self._messages: list[dict[str, Any]] = []

        # Filter to supported tools only
        self.supported_tools = [
            tool for tool in self.allowed_tools if tool in SUPPORTED_TOOLS
        ]
        self.tool_defs = [
            {
                "type": "function",
                "function": {
                    "name": tool,
                    "description": f"Auto-Claude tool: {tool}",
                    "parameters": TOOL_SCHEMAS[tool],
                },
            }
            for tool in self.supported_tools
        ]

    async def __aenter__(self) -> "OpenAICompatClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    async def close(self) -> None:
        try:
            await self.client.close()
        except Exception:
            pass

    async def query(self, prompt: str) -> None:
        self._events = []
        self._messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt},
        ]
        await self._run_conversation()

    async def receive_response(self):
        for msg in self._events:
            yield msg
            await asyncio.sleep(0)

    async def _run_conversation(self) -> None:
        turns = 0
        while True:
            turns += 1
            if turns > self.max_turns:
                self._events.append(
                    AssistantMessage(
                        [TextBlock("[OpenAICompat] Max turns reached, stopping.")]
                    )
                )
                break

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=self._messages,
                tools=self.tool_defs or None,
                tool_choice="auto" if self.tool_defs else None,
            )

            choices = getattr(response, "choices", None)
            if not choices:
                base_url = getattr(self.client, "base_url", None) or self.base_url
                base_url_str = str(base_url) if base_url else "<default>"

                hint = ""
                if "anthropic" in base_url_str:
                    hint = (
                        " Base URL contains 'anthropic' and is likely not OpenAI-compatible."
                        " Use an OpenAI-compatible base URL (often ends with /v1)."
                    )
                    if "z.ai" in base_url_str:
                        hint += (
                            " For Z.AI, the default OpenAI-compatible base URL is"
                            " https://api.z.ai/api/coding/paas/v4."
                        )

                raise ValueError(
                    "OpenAI-compatible provider returned an invalid chat completion response "
                    "(missing 'choices'). "
                    f"model={self.model} base_url={base_url_str}.{hint}"
                )

            choice = choices[0]
            message = getattr(choice, "message", None)
            if message is None:
                base_url = getattr(self.client, "base_url", None) or self.base_url
                base_url_str = str(base_url) if base_url else "<default>"
                raise ValueError(
                    "OpenAI-compatible provider returned an invalid chat completion response "
                    "(missing 'message'). "
                    f"model={self.model} base_url={base_url_str}."
                )

            # Debug: Log response details for troubleshooting
            content_preview = str(getattr(message, "content", None))[:100] if getattr(message, "content", None) else None
            tool_count = len(getattr(message, "tool_calls", None) or [])
            logger.debug(
                f"[OpenAICompat] Turn {turns}/{self.max_turns}: "
                f"model={self.model}, "
                f"content={repr(content_preview)}, "
                f"tool_calls={tool_count}"
            )

            blocks: list[Any] = []

            # Track if we got any meaningful response
            has_content = False
            has_tool_calls = False

            # Check for actual text content (not just empty/whitespace)
            content = getattr(message, "content", None)
            if content and str(content).strip():
                blocks.append(TextBlock(message.content))
                has_content = True

            tool_calls = getattr(message, "tool_calls", None) or []
            if tool_calls:
                has_tool_calls = True

            for tool_call in tool_calls:
                tool_name = tool_call.function.name
                tool_args = self._parse_tool_args(tool_call.function.arguments)
                blocks.append(ToolUseBlock(tool_name, tool_args))

            # Detect empty response - model returned neither text nor tools
            # This can happen with some providers (e.g., Z.AI) when the model
            # cannot process the prompt or tool definitions properly
            if not has_content and not has_tool_calls:
                base_url = getattr(self.client, "base_url", None) or self.base_url
                base_url_str = str(base_url) if base_url else "<default>"

                # Provide helpful error message
                error_detail = (
                    f"OpenAI-compatible provider returned an empty response. "
                    f"This can happen when:\n"
                    f"  1. The model doesn't support the requested tools\n"
                    f"  2. The prompt is too long or malformed\n"
                    f"  3. The provider API has issues\n\n"
                    f"Provider response: content={repr(content)}, tool_calls={len(tool_calls) if tool_calls else 0}\n"
                    f"model={self.model} base_url={base_url_str}\n\n"
                    f"Troubleshooting:\n"
                    f"  - Try using Claude provider instead\n"
                    f"  - Check if ZAI_API_KEY is valid\n"
                    f"  - Reduce prompt length or simplify the task"
                )

                self._events.append(
                    AssistantMessage(
                        [TextBlock(f"[OpenAICompat] Empty response detected.\n\n{error_detail}")]
                    )
                )
                break

            if blocks:
                self._events.append(AssistantMessage(blocks))

            # Add assistant message to conversation
            self._messages.append(self._convert_message(message))

            if not tool_calls:
                break

            for tool_call in tool_calls:
                tool_name = tool_call.function.name
                tool_args = self._parse_tool_args(tool_call.function.arguments)
                result_text, is_error = await self._execute_tool(tool_name, tool_args)

                self._events.append(
                    UserMessage([ToolResultBlock(result_text, is_error=is_error)])
                )

                self._messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result_text,
                    }
                )

    @staticmethod
    def _parse_tool_args(raw_args: str | None) -> dict[str, Any]:
        if not raw_args:
            return {}
        try:
            return json.loads(raw_args)
        except json.JSONDecodeError:
            return {}

    @staticmethod
    def _convert_message(message: Any) -> dict[str, Any]:
        base: dict[str, Any] = {"role": message.role}
        if message.content:
            base["content"] = message.content
        tool_calls = getattr(message, "tool_calls", None)
        if tool_calls:
            base["tool_calls"] = [
                {
                    "id": call.id,
                    "type": call.type,
                    "function": {
                        "name": call.function.name,
                        "arguments": call.function.arguments,
                    },
                }
                for call in tool_calls
            ]
        return base

    async def _execute_tool(self, tool_name: str, tool_input: dict[str, Any]) -> tuple[str, bool]:
        if tool_name not in SUPPORTED_TOOLS:
            return f"Tool '{tool_name}' is not supported for this provider.", True

        try:
            if tool_name == "Read":
                return await self._tool_read(tool_input), False
            if tool_name == "Write":
                return await self._tool_write(tool_input), False
            if tool_name == "Edit":
                return await self._tool_edit(tool_input), False
            if tool_name == "Glob":
                return await self._tool_glob(tool_input), False
            if tool_name == "Grep":
                return await self._tool_grep(tool_input), False
            if tool_name == "Bash":
                return await self._tool_bash(tool_input), False
            if tool_name == "WebFetch":
                return await self._tool_web_fetch(tool_input), False
            if tool_name == "WebSearch":
                return await self._tool_web_search(tool_input), False
        except Exception as exc:  # noqa: BLE001
            return f"Tool '{tool_name}' failed: {exc}", True

        return f"Tool '{tool_name}' is not implemented.", True

    def _resolve_path(self, file_path: str) -> Path:
        if not file_path:
            raise ValueError("file_path is required")
        path = Path(file_path)
        if not path.is_absolute():
            path = (self.project_dir / file_path).resolve()
        else:
            path = path.resolve()
        try:
            path.relative_to(self.project_dir)
        except ValueError as exc:
            raise ValueError("Path is outside project directory") from exc
        return path

    async def _tool_read(self, tool_input: dict[str, Any]) -> str:
        file_path = tool_input.get("file_path")
        path = self._resolve_path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        content = path.read_text(encoding="utf-8", errors="replace")
        if len(content) > 20000:
            content = content[:20000] + "\n\n[... truncated ...]"
        return content

    async def _tool_write(self, tool_input: dict[str, Any]) -> str:
        file_path = tool_input.get("file_path")
        content = tool_input.get("content", "")
        path = self._resolve_path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return f"Wrote {len(content)} chars to {file_path}"

    async def _tool_edit(self, tool_input: dict[str, Any]) -> str:
        file_path = tool_input.get("file_path")
        old_string = tool_input.get("old_string", "")
        new_string = tool_input.get("new_string", "")
        path = self._resolve_path(file_path)
        content = path.read_text(encoding="utf-8", errors="replace")
        if old_string not in content:
            raise ValueError("old_string not found in file")
        updated = content.replace(old_string, new_string, 1)
        path.write_text(updated, encoding="utf-8")
        return f"Updated {file_path}"

    async def _tool_glob(self, tool_input: dict[str, Any]) -> str:
        pattern = tool_input.get("pattern")
        if not pattern:
            raise ValueError("pattern is required")
        matches = [
            str(Path(match).resolve().relative_to(self.project_dir))
            for match in (self.project_dir).glob(pattern)
        ]
        if not matches:
            return "No matches."
        return "\n".join(sorted(matches))

    async def _tool_grep(self, tool_input: dict[str, Any]) -> str:
        pattern = tool_input.get("pattern")
        if not pattern:
            raise ValueError("pattern is required")
        path_value = tool_input.get("path")
        root = self._resolve_path(path_value) if path_value else self.project_dir
        regex = re.compile(pattern)
        results: list[str] = []
        for file_path in root.rglob("*"):
            if not file_path.is_file():
                continue
            if file_path.stat().st_size > 1_000_000:
                continue
            try:
                text = file_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            for idx, line in enumerate(text.splitlines(), start=1):
                if regex.search(line):
                    rel = file_path.resolve().relative_to(self.project_dir)
                    results.append(f"{rel}:{idx}:{line}")
                    if len(results) >= 200:
                        break
            if len(results) >= 200:
                break
        if not results:
            return "No matches."
        return "\n".join(results)

    async def _tool_bash(self, tool_input: dict[str, Any]) -> str:
        command = tool_input.get("command")
        if not command:
            raise ValueError("command is required")
        allowed, reason = validate_command(command, self.project_dir)
        if not allowed:
            raise ValueError(f"Command blocked: {reason}")
        proc = subprocess.run(
            command,
            shell=True,
            cwd=str(self.project_dir),
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )
        output = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
        output = output.strip()
        if len(output) > 20000:
            output = output[:20000] + "\n\n[... truncated ...]"
        if proc.returncode != 0:
            return f"Command failed ({proc.returncode}):\n{output}"
        return output or "Command completed with no output."

    async def _tool_web_fetch(self, tool_input: dict[str, Any]) -> str:
        url = tool_input.get("url")
        if not url:
            raise ValueError("url is required")
        req = Request(
            url,
            headers={
                "User-Agent": "Auto-Claude/1.0",
                "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
            },
        )
        with urlopen(req, timeout=20) as resp:
            data = resp.read()
        text = data.decode("utf-8", errors="replace")
        if len(text) > 20000:
            text = text[:20000] + "\n\n[... truncated ...]"
        return text

    async def _tool_web_search(self, tool_input: dict[str, Any]) -> str:
        query = tool_input.get("query")
        if not query:
            raise ValueError("query is required")
        url = (
            "https://api.duckduckgo.com/?q="
            + quote_plus(query)
            + "&format=json&no_redirect=1&no_html=1"
        )
        req = Request(url, headers={"User-Agent": "Auto-Claude/1.0"})
        with urlopen(req, timeout=20) as resp:
            payload = json.loads(resp.read().decode("utf-8", errors="replace"))

        results: list[str] = []
        abstract = payload.get("AbstractText")
        if abstract:
            results.append(f"Abstract: {abstract}")
        related = payload.get("RelatedTopics") or []
        for entry in related:
            if isinstance(entry, dict) and entry.get("Text"):
                results.append(entry["Text"])
            elif isinstance(entry, dict) and entry.get("Topics"):
                for topic in entry.get("Topics", []):
                    if topic.get("Text"):
                        results.append(topic["Text"])
            if len(results) >= 10:
                break

        if not results:
            return "No results."
        return "\n".join(results)
