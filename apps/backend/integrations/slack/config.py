"""
Slack Integration Configuration
================================

Constants, status mappings, and configuration helpers for Slack integration.
"""

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

# Message types
MESSAGE_BUILD_START = "build_start"
MESSAGE_BUILD_COMPLETE = "build_complete"
MESSAGE_BUILD_FAIL = "build_fail"
MESSAGE_SPEC_APPROVAL = "spec_approval"
MESSAGE_SUBTASK_UPDATE = "subtask_update"
SESSION_QA_REQUEST = "qa_request"
MESSAGE_QA_APPROVAL = "qa_approval"

# Slack project marker file (stores channel IDs and state)
SLACK_PROJECT_MARKER = ".slack_project.json"

# Approval reactions
REACTION_APPROVE = "white_check_mark"
REACTION_REJECT = "x"
REACTION_IN_PROGRESS = "eyes"

# Default notification preferences
DEFAULT_NOTIFY_BUILD_START = True
DEFAULT_NOTIFY_BUILD_COMPLETE = True
DEFAULT_NOTIFY_BUILD_FAIL = True
DEFAULT_NOTIFY_SPEC_APPROVAL = True
DEFAULT_NOTIFY_SUBTASK_UPDATES = False


@dataclass
class SlackConfig:
    """Configuration for Slack integration."""

    bot_token: str
    signing_secret: str | None = None
    webhook_url: str | None = None
    default_channel_id: str | None = None
    app_id: str | None = None
    enabled: bool = True

    @classmethod
    def from_env(cls) -> "SlackConfig":
        """Create config from environment variables."""
        bot_token = os.environ.get("SLACK_BOT_TOKEN", "")
        signing_secret = os.environ.get("SLACK_SIGNING_SECRET")
        webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
        default_channel_id = os.environ.get("SLACK_DEFAULT_CHANNEL_ID")
        app_id = os.environ.get("SLACK_APP_ID")

        return cls(
            bot_token=bot_token,
            signing_secret=signing_secret,
            webhook_url=webhook_url,
            default_channel_id=default_channel_id,
            app_id=app_id,
            enabled=bool(bot_token or webhook_url),
        )

    def is_valid(self) -> bool:
        """Check if config has minimum required values."""
        return bool(self.bot_token or self.webhook_url)

    def is_bot_configured(self) -> bool:
        """Check if bot token is configured (for interactive features)."""
        return bool(self.bot_token)

    def is_webhook_configured(self) -> bool:
        """Check if webhook is configured (for simple notifications)."""
        return bool(self.webhook_url)


@dataclass
class NotificationPreferences:
    """User notification preferences."""

    notify_build_start: bool = DEFAULT_NOTIFY_BUILD_START
    notify_build_complete: bool = DEFAULT_NOTIFY_BUILD_COMPLETE
    notify_build_fail: bool = DEFAULT_NOTIFY_BUILD_FAIL
    notify_spec_approval: bool = DEFAULT_NOTIFY_SPEC_APPROVAL
    notify_subtask_updates: bool = DEFAULT_NOTIFY_SUBTASK_UPDATES

    def to_dict(self) -> dict:
        return {
            "notify_build_start": self.notify_build_start,
            "notify_build_complete": self.notify_build_complete,
            "notify_build_fail": self.notify_build_fail,
            "notify_spec_approval": self.notify_spec_approval,
            "notify_subtask_updates": self.notify_subtask_updates,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "NotificationPreferences":
        return cls(
            notify_build_start=data.get("notify_build_start", DEFAULT_NOTIFY_BUILD_START),
            notify_build_complete=data.get("notify_build_complete", DEFAULT_NOTIFY_BUILD_COMPLETE),
            notify_build_fail=data.get("notify_build_fail", DEFAULT_NOTIFY_BUILD_FAIL),
            notify_spec_approval=data.get("notify_spec_approval", DEFAULT_NOTIFY_SPEC_APPROVAL),
            notify_subtask_updates=data.get("notify_subtask_updates", DEFAULT_NOTIFY_SUBTASK_UPDATES),
        )


@dataclass
class SlackProjectState:
    """State of a Slack integration for an auto-claude spec."""

    initialized: bool = False
    channel_id: str | None = None
    notification_ts: str | None = None  # Message timestamp for updates
    approval_ts: str | None = None  # Message timestamp for approval requests
    total_messages: int = 0
    created_at: str | None = None
    preferences: dict = None  # Notification preferences
    message_mapping: dict = None  # subtask_id -> message_ts mapping

    def __post_init__(self):
        if self.preferences is None:
            self.preferences = NotificationPreferences().to_dict()
        if self.message_mapping is None:
            self.message_mapping = {}

    def to_dict(self) -> dict:
        return {
            "initialized": self.initialized,
            "channel_id": self.channel_id,
            "notification_ts": self.notification_ts,
            "approval_ts": self.approval_ts,
            "total_messages": self.total_messages,
            "created_at": self.created_at,
            "preferences": self.preferences,
            "message_mapping": self.message_mapping,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SlackProjectState":
        return cls(
            initialized=data.get("initialized", False),
            channel_id=data.get("channel_id"),
            notification_ts=data.get("notification_ts"),
            approval_ts=data.get("approval_ts"),
            total_messages=data.get("total_messages", 0),
            created_at=data.get("created_at"),
            preferences=data.get("preferences"),
            message_mapping=data.get("message_mapping"),
        )

    def save(self, spec_dir: Path) -> None:
        """Save state to the spec directory."""
        marker_file = spec_dir / SLACK_PROJECT_MARKER
        with open(marker_file, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, spec_dir: Path) -> Optional["SlackProjectState"]:
        """Load state from the spec directory."""
        marker_file = spec_dir / SLACK_PROJECT_MARKER
        if not marker_file.exists():
            return None

        try:
            with open(marker_file) as f:
                return cls.from_dict(json.load(f))
        except (OSError, json.JSONDecodeError):
            return None

    def get_preferences(self) -> NotificationPreferences:
        """Get notification preferences as an object."""
        return NotificationPreferences.from_dict(self.preferences)


def get_status_emoji(status: str) -> str:
    """
    Get emoji for subtask status.

    Args:
        status: Status from implementation_plan.json

    Returns:
        Emoji string
    """
    emoji_map = {
        "pending": "📋",
        "in_progress": "🔄",
        "completed": "✅",
        "blocked": "🚫",
        "failed": "❌",
        "stuck": "⚠️",
    }
    return emoji_map.get(status, "📋")


def get_status_color(status: str) -> str:
    """
    Get color for Slack attachment based on status.

    Args:
        status: Status from implementation_plan.json

    Returns:
        Hex color code
    """
    color_map = {
        "pending": "#808080",  # Gray
        "in_progress": "#03A9F4",  # Blue
        "completed": "#4CAF50",  # Green
        "blocked": "#F44336",  # Red
        "failed": "#F44336",  # Red
        "stuck": "#FF9800",  # Orange
    }
    return color_map.get(status, "#808080")


def get_timestamp_url(channel_id: str, message_ts: str) -> str:
    """
    Generate a permalink URL to a Slack message.

    Args:
        channel_id: Slack channel ID
        message_ts: Message timestamp

    Returns:
        Permalink URL
    """
    return f"https://slack.com/archives/{channel_id}/p{message_ts.replace('.', '')}"


def format_slack_message(
    message_type: str,
    title: str,
    text: str,
    status: str | None = None,
    fields: list[dict] | None = None,
    actions: list[dict] | None = None,
    footer: str | None = None,
) -> dict:
    """
    Format a message for Slack using Block Kit.

    Args:
        message_type: Type of message (build_start, build_complete, etc.)
        title: Message title
        text: Message text/description
        status: Optional status for emoji and color
        fields: Optional list of field dicts {"title": str, "value": str}
        actions: Optional list of action buttons for approval
        footer: Optional footer text

    Returns:
        Slack message dict with blocks
    """
    blocks = []

    # Header section with emoji if status provided
    if status:
        emoji = get_status_emoji(status)
        blocks.append({
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{emoji} {title}",
                "emoji": True,
            },
        })
    else:
        blocks.append({
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": title,
            },
        })

    # Main text section
    if text:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": text,
            },
        })

    # Fields section
    if fields:
        blocks.append({
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*{field['title']}*\n{field['value']}",
                }
                for field in fields[:5]  # Slack limit: 5 fields
            ],
        })

    # Actions section (for approval buttons)
    if actions:
        blocks.append({
            "type": "actions",
            "elements": actions,
        })

    # Divider
    blocks.append({"type": "divider"})

    # Footer context
    if footer:
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": footer,
                },
            ],
        })

    return {"blocks": blocks}


def format_build_notification(
    spec_name: str,
    build_status: str,
    phase_name: str | None = None,
    subtask_count: int = 0,
    completed_count: int = 0,
) -> dict:
    """
    Format a build status notification message.

    Args:
        spec_name: Name of the spec
        build_status: Status (pending, in_progress, completed, failed)
        phase_name: Current phase name (optional)
        subtask_count: Total number of subtasks
        completed_count: Number of completed subtasks

    Returns:
        Slack message dict
    """
    title = f"Build {build_status.replace('_', ' ').title()}"
    emoji = get_status_emoji(build_status)

    # Build progress text
    if subtask_count > 0:
        progress = f"{completed_count}/{subtask_count} subtasks completed"
        text = f"*{spec_name}*"
        if phase_name:
            text += f"\n*Phase:* {phase_name}"
        text += f"\n*Progress:* {progress}"
    else:
        text = f"*{spec_name}*"
        if phase_name:
            text += f"\n*Phase:* {phase_name}"

    # Footer
    footer = f"Auto Claude Build • {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

    return format_slack_message(
        message_type=f"build_{build_status}",
        title=title,
        text=text,
        status=build_status,
        footer=footer,
    )


def format_spec_approval_request(
    spec_name: str,
    spec_id: str,
    description: str,
    requirements: list[str] | None = None,
) -> dict:
    """
    Format a spec approval request message.

    Args:
        spec_name: Name of the spec
        spec_id: Spec ID (e.g., "001-feature")
        description: Spec description
        requirements: List of key requirements

    Returns:
        Slack message dict with approval buttons
    """
    title = "Spec Approval Required"
    emoji = "🔔"

    # Build description text
    text = f"*{spec_name}* (`{spec_id}`)\n{description}"

    # Add requirements as fields
    fields = []
    if requirements:
        for i, req in enumerate(requirements[:3], 1):  # Max 3 requirements
            fields.append({
                "title": f"Requirement {i}",
                "value": req[:100],  # Truncate long requirements
            })

    # Approval actions
    actions = [
        {
            "type": "button",
            "text": {
                "type": "plain_text",
                "text": f":white_check_mark: Approve",
                "emoji": True,
            },
            "style": "primary",
            "value": f"approve:{spec_id}",
            "action_id": f"approve_spec_{spec_id}",
        },
        {
            "type": "button",
            "text": {
                "type": "plain_text",
                "text": ":x: Reject",
                "emoji": True,
            },
            "style": "danger",
            "value": f"reject:{spec_id}",
            "action_id": f"reject_spec_{spec_id}",
        },
    ]

    footer = "React to approve or reject this spec"

    return format_slack_message(
        message_type=MESSAGE_SPEC_APPROVAL,
        title=title,
        text=text,
        fields=fields if fields else None,
        actions=actions,
        footer=footer,
    )


def format_subtask_update(
    subtask_id: str,
    subtask_title: str,
    old_status: str,
    new_status: str,
    phase_name: str | None = None,
) -> dict:
    """
    Format a subtask status update message.

    Args:
        subtask_id: Subtask ID (e.g., "subtask-1-1")
        subtask_title: Subtask title/description
        old_status: Previous status
        new_status: New status
        phase_name: Current phase name (optional)

    Returns:
        Slack message dict
    """
    old_emoji = get_status_emoji(old_status)
    new_emoji = get_status_emoji(new_status)

    title = f"Subtask Updated: {subtask_id}"

    text = (
        f"{old_emoji} → {new_emoji} *{subtask_title}*\n"
        f"*Status:* `{old_status}` → `{new_status}`"
    )

    if phase_name:
        text += f"\n*Phase:* {phase_name}"

    footer = f"Auto Claude • {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

    return format_slack_message(
        message_type=MESSAGE_SUBTASK_UPDATE,
        title=title,
        text=text,
        status=new_status,
        footer=footer,
    )


def format_qa_request(
    spec_name: str,
    qa_report_path: str,
    issues_count: int,
    spec_id: str,
) -> dict:
    """
    Format a QA review request message.

    Args:
        spec_name: Name of the spec
        qa_report_path: Path to QA report
        issues_count: Number of issues found
        spec_id: Spec ID

    Returns:
        Slack message dict with review request buttons
    """
    title = "QA Review Request"
    emoji = "🔍"

    text = (
        f"*{spec_name}* is ready for QA review.\n"
        f"*Issues Found:* {issues_count}\n"
        f"*Report:* `{qa_report_path}`"
    )

    # Review actions
    actions = [
        {
            "type": "button",
            "text": {
                "type": "plain_text",
                "text": ":white_check_mark: Approve",
                "emoji": True,
            },
            "style": "primary",
            "value": f"qa_approve:{spec_id}",
            "action_id": f"qa_approve_{spec_id}",
        },
        {
            "type": "button",
            "text": {
                "type": "plain_text",
                "text": ":x: Request Fixes",
                "emoji": True,
            },
            "style": "danger",
            "value": f"qa_reject:{spec_id}",
            "action_id": f"qa_reject_{spec_id}",
        },
    ]

    footer = "Review the QA report and approve or request fixes"

    return format_slack_message(
        message_type=SESSION_QA_REQUEST,
        title=title,
        text=text,
        actions=actions,
        footer=footer,
    )


def format_qa_approval_notification(
    spec_name: str,
    qa_status: str,
    qa_session: int,
    issues_count: int = 0,
    report_path: str | None = None,
) -> dict:
    """
    Format a QA approval/rejection notification message.

    Args:
        spec_name: Name of the spec
        qa_status: "approved" or "rejected"
        qa_session: QA session number
        issues_count: Number of issues found (if rejected)
        report_path: Path to QA report (optional)

    Returns:
        Slack message dict with approval status
    """
    if qa_status == "approved":
        title = "✅ QA Approved"
        emoji = "white_check_mark"
        status = "success"
        text = (
            f"*{spec_name}* has passed QA review and is ready for merge.\n"
            f"*QA Session:* {qa_session}\n"
            f"*Status:* All acceptance criteria validated"
        )
        footer = "Build approved - ready for production"
    else:  # rejected
        title = "❌ QA Rejected"
        emoji = "x"
        status = "danger"
        text = (
            f"*{spec_name}* has been rejected by QA review.\n"
            f"*QA Session:* {qa_session}\n"
            f"*Issues Found:* {issues_count}\n"
        )
        if report_path:
            text += f"*Report:* `{report_path}`\n"
        footer = "Fixes required - see QA report for details"

    return format_slack_message(
        message_type=MESSAGE_QA_APPROVAL,
        title=title,
        text=text,
        status=status,
        footer=footer,
    )
