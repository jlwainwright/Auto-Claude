"""
Slack Updater - Python-Orchestrated Slack Notifications
========================================================

Provides reliable Slack notifications via focused mini-agent calls.
Instead of relying on agents to remember Slack updates in long prompts,
the Python orchestrator triggers small, focused agents at key transitions.

Design Principles:
- ONE notification channel per spec
- Python orchestrator controls when notifications happen
- Small prompts that can't lose context
- Graceful degradation if Slack unavailable

Notification Flow:
  Build Start → Subtask Updates → Build Complete/Fail
       ↓              ↓                  ↓
  Channel init    Progress updates    Final status

The updater uses SlackManager to prepare message data, then executes
MCP tool calls via focused mini-agents to send/update messages.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient

from .config import (
    MESSAGE_BUILD_COMPLETE,
    MESSAGE_BUILD_FAIL,
    MESSAGE_BUILD_START,
    MESSAGE_SPEC_APPROVAL,
    SlackProjectState,
)
from .integration import SlackManager

# Slack MCP tools needed for notifications
SLACK_TOOLS = [
    "mcp__slack-server__list_channels",
    "mcp__slack-server__send_message",
    "mcp__slack-server__update_message",
]


def is_slack_enabled() -> bool:
    """Check if Slack integration is available."""
    return bool(os.environ.get("SLACK_BOT_TOKEN") or os.environ.get("SLACK_WEBHOOK_URL"))


def get_slack_bot_token() -> str:
    """Get the Slack bot token from environment."""
    return os.environ.get("SLACK_BOT_TOKEN", "")


def _create_slack_client() -> ClaudeSDKClient:
    """
    Create a minimal Claude client with only Slack MCP tools.
    Used for focused mini-agent calls.
    """
    from core.auth import (
        ensure_claude_code_oauth_token,
        get_sdk_env_vars,
        require_auth_token,
    )
    from phase_config import resolve_model_id

    require_auth_token()  # Raises ValueError if no token found
    ensure_claude_code_oauth_token()

    bot_token = get_slack_bot_token()
    if not bot_token:
        raise ValueError("SLACK_BOT_TOKEN not set")

    sdk_env = get_sdk_env_vars()

    return ClaudeSDKClient(
        options=ClaudeAgentOptions(
            model=resolve_model_id("haiku"),  # Fast model for simple operations
            system_prompt="You are a Slack API assistant. Execute the requested Slack operation precisely.",
            allowed_tools=SLACK_TOOLS,
            mcp_servers={
                "slack": {
                    "type": "http",
                    "url": "https://slack-mcp-server.example.com/mcp",  # TODO: Update with actual URL
                    "headers": {"Authorization": f"Bearer {bot_token}"},
                }
            },
            max_turns=10,  # Should complete in 1-3 turns
            env=sdk_env,  # Pass ANTHROPIC_BASE_URL etc. to subprocess
        )
    )


async def _run_slack_agent(prompt: str) -> str | None:
    """
    Run a focused mini-agent for a Slack operation.

    Args:
        prompt: The focused prompt for the Slack operation

    Returns:
        The response text, or None if failed
    """
    try:
        client = _create_slack_client()

        async with client:
            await client.query(prompt)

            response_text = ""
            async for msg in client.receive_response():
                msg_type = type(msg).__name__
                if msg_type == "AssistantMessage" and hasattr(msg, "content"):
                    for block in msg.content:
                        block_type = type(block).__name__
                        if block_type == "TextBlock" and hasattr(block, "text"):
                            response_text += block.text

            return response_text

    except Exception as e:
        print(f"Slack notification failed: {e}")
        return None


async def _send_message_to_slack(
    channel_id: str,
    message: dict,
) -> str | None:
    """
    Send a message to a Slack channel.

    Args:
        channel_id: Slack channel ID
        message: Message dict with blocks

    Returns:
        Message timestamp if successful, None otherwise
    """
    # Convert message dict to JSON string for the prompt
    message_json = json.dumps(message, indent=2)

    prompt = f"""Send a message to Slack:

Use mcp__slack-server__send_message with:
- channel: "{channel_id}"
- text: "Build notification"  # Fallback text
- blocks: {message_json}

After sending, tell me the message timestamp in this format:
TIMESTAMP: [the timestamp value]
"""

    response = await _run_slack_agent(prompt)
    if not response:
        return None

    # Parse response for timestamp
    for line in response.split("\n"):
        line = line.strip()
        if line.startswith("TIMESTAMP:"):
            return line.replace("TIMESTAMP:", "").strip()

    return None


async def _update_message_in_slack(
    channel_id: str,
    message_ts: str,
    message: dict,
) -> bool:
    """
    Update an existing message in Slack.

    Args:
        channel_id: Slack channel ID
        message_ts: Message timestamp to update
        message: Updated message dict with blocks

    Returns:
        True if successful, False otherwise
    """
    message_json = json.dumps(message, indent=2)

    prompt = f"""Update a message in Slack:

Use mcp__slack-server__update_message with:
- channel: "{channel_id}"
- timestamp: "{message_ts}"
- text: "Build notification update"  # Fallback text
- blocks: {message_json}

Confirm when done.
"""

    response = await _run_slack_agent(prompt)
    return response is not None


async def slack_build_started(
    spec_dir: Path,
    project_dir: Path,
    spec_name: str,
) -> bool:
    """
    Send a build start notification to Slack.

    Called when the build process begins (after planner creates the plan).

    Args:
        spec_dir: Spec directory
        project_dir: Project root directory
        spec_name: Name of the spec

    Returns:
        True if successful, False otherwise
    """
    if not is_slack_enabled():
        return False

    try:
        manager = SlackManager(spec_dir, project_dir)

        # Check if Slack is initialized for this spec
        if not manager.is_initialized:
            print(f"Slack not initialized for {spec_name}, skipping build start notification")
            return False

        # Prepare message data
        message_data = manager.send_build_start_notification(
            spec_name=spec_name,
        )

        if not message_data:
            return False

        # Send message via MCP
        channel_id = message_data["channel_id"]
        message = message_data["message"]

        message_ts = await _send_message_to_slack(channel_id, message)
        if message_ts:
            # Store the notification timestamp for later updates
            manager.set_notification_timestamp(message_ts)
            manager.increment_message_count()
            print(f"Build start notification sent to Slack: {message_ts}")
            return True

        return False

    except Exception as e:
        print(f"Failed to send build start notification: {e}")
        return False


async def slack_build_completed(
    spec_dir: Path,
    project_dir: Path,
    spec_name: str,
    subtask_count: int = 0,
    completed_count: int = 0,
) -> bool:
    """
    Send a build complete notification to Slack.

    Called when all subtasks are completed successfully.

    Args:
        spec_dir: Spec directory
        project_dir: Project root directory
        spec_name: Name of the spec
        subtask_count: Total number of subtasks
        completed_count: Number of completed subtasks

    Returns:
        True if successful, False otherwise
    """
    if not is_slack_enabled():
        return False

    try:
        manager = SlackManager(spec_dir, project_dir)

        if not manager.is_initialized:
            return False

        # Prepare message data
        message_data = manager.send_build_complete_notification(
            spec_name=spec_name,
            subtask_count=subtask_count,
            completed_count=completed_count,
        )

        if not message_data:
            return False

        channel_id = message_data["channel_id"]
        message = message_data["message"]

        # Send message via MCP
        message_ts = await _send_message_to_slack(channel_id, message)
        if message_ts:
            manager.increment_message_count()
            print(f"Build complete notification sent to Slack: {message_ts}")
            return True

        return False

    except Exception as e:
        print(f"Failed to send build complete notification: {e}")
        return False


async def slack_build_failed(
    spec_dir: Path,
    project_dir: Path,
    spec_name: str,
    error_message: str,
) -> bool:
    """
    Send a build failure notification to Slack.

    Called when the build process fails critically.

    Args:
        spec_dir: Spec directory
        project_dir: Project root directory
        spec_name: Name of the spec
        error_message: Error message describing the failure

    Returns:
        True if successful, False otherwise
    """
    if not is_slack_enabled():
        return False

    try:
        manager = SlackManager(spec_dir, project_dir)

        if not manager.is_initialized:
            return False

        # Prepare message data
        message_data = manager.send_build_fail_notification(
            spec_name=spec_name,
            error_message=error_message,
        )

        if not message_data:
            return False

        channel_id = message_data["channel_id"]
        message = message_data["message"]

        # Send message via MCP
        message_ts = await _send_message_to_slack(channel_id, message)
        if message_ts:
            manager.increment_message_count()
            print(f"Build failure notification sent to Slack: {message_ts}")
            return True

        return False

    except Exception as e:
        print(f"Failed to send build failure notification: {e}")
        return False


# === Additional helper functions ===


async def slack_subtask_update(
    spec_dir: Path,
    project_dir: Path,
    subtask_id: str,
    subtask_title: str,
    old_status: str,
    new_status: str,
) -> bool:
    """
    Send a subtask status update to Slack.

    Called after each coder session completes a subtask.

    Args:
        spec_dir: Spec directory
        project_dir: Project root directory
        subtask_id: Subtask ID (e.g., "subtask-1-1")
        subtask_title: Subtask title/description
        old_status: Previous status
        new_status: New status

    Returns:
        True if successful, False otherwise
    """
    if not is_slack_enabled():
        return False

    try:
        manager = SlackManager(spec_dir, project_dir)

        if not manager.is_initialized:
            return False

        # Check if subtask notifications are enabled
        preferences = manager.get_notification_preferences()
        if not preferences.get("notify_subtask_updates", False):
            return False

        # Prepare message data
        message_data = manager.send_subtask_update(
            subtask_id=subtask_id,
            subtask_title=subtask_title,
            old_status=old_status,
            new_status=new_status,
        )

        if not message_data:
            return False

        channel_id = message_data["channel_id"]
        message = message_data["message"]

        # Send message via MCP
        message_ts = await _send_message_to_slack(channel_id, message)
        if message_ts:
            # Store mapping for potential updates
            manager.set_message_timestamp(subtask_id, message_ts)
            manager.increment_message_count()
            print(f"Subtask update sent to Slack: {subtask_id} -> {new_status}")
            return True

        return False

    except Exception as e:
        print(f"Failed to send subtask update: {e}")
        return False


async def slack_progress_update(
    spec_dir: Path,
    project_dir: Path,
    spec_name: str,
    phase_name: str | None = None,
    subtask_count: int = 0,
    completed_count: int = 0,
) -> bool:
    """
    Update or create a progress tracking message in Slack.

    Called periodically during the build to show overall progress.

    Args:
        spec_dir: Spec directory
        project_dir: Project root directory
        spec_name: Name of the spec
        phase_name: Current phase name (optional)
        subtask_count: Total number of subtasks
        completed_count: Number of completed subtasks

    Returns:
        True if successful, False otherwise
    """
    if not is_slack_enabled():
        return False

    try:
        manager = SlackManager(spec_dir, project_dir)

        if not manager.is_initialized:
            return False

        # Prepare message data
        message_data = manager.update_progress_message(
            spec_name=spec_name,
            phase_name=phase_name,
            subtask_count=subtask_count,
            completed_count=completed_count,
        )

        if not message_data:
            return False

        channel_id = message_data["channel_id"]
        message = message_data["message"]
        update_ts = message_data.get("update_ts")

        # Update existing message or send new one
        if update_ts:
            success = await _update_message_in_slack(channel_id, update_ts, message)
            if success:
                print(f"Progress message updated in Slack: {completed_count}/{subtask_count}")
                return True
        else:
            message_ts = await _send_message_to_slack(channel_id, message)
            if message_ts:
                manager.set_notification_timestamp(message_ts)
                manager.increment_message_count()
                print(f"Progress message sent to Slack: {completed_count}/{subtask_count}")
                return True

        return False

    except Exception as e:
        print(f"Failed to update progress in Slack: {e}")
        return False


async def send_spec_approval_request(
    spec_dir: Path,
    project_dir: Path,
    spec_name: str,
    spec_id: str,
    description: str,
    requirements: list[str] | None = None,
) -> bool:
    """
    Send a spec approval request to Slack.

    Called when a spec is created and requires user approval before building.

    Args:
        spec_dir: Spec directory
        project_dir: Project root directory
        spec_name: Name of the spec
        spec_id: Spec ID (e.g., "001-feature")
        description: Spec description
        requirements: List of key requirements (optional)

    Returns:
        True if successful, False otherwise
    """
    if not is_slack_enabled():
        return False

    try:
        manager = SlackManager(spec_dir, project_dir)

        if not manager.is_initialized:
            print(f"Slack not initialized for {spec_name}, skipping approval request")
            return False

        # Check if spec approval notifications are enabled
        preferences = manager.get_notification_preferences()
        if not preferences.get("notify_spec_approval", True):
            return False

        # Prepare message data
        message_data = manager.send_spec_approval_request(
            spec_name=spec_name,
            spec_id=spec_id,
            description=description,
            requirements=requirements,
        )

        if not message_data:
            return False

        channel_id = message_data["channel_id"]
        message = message_data["message"]

        # Send message via MCP
        message_ts = await _send_message_to_slack(channel_id, message)
        if message_ts:
            # Store the approval timestamp for tracking responses
            manager.set_approval_timestamp(message_ts)
            manager.increment_message_count()
            print(f"Spec approval request sent to Slack: {message_ts}")
            return True

        return False

    except Exception as e:
        print(f"Failed to send spec approval request: {e}")
        return False
