"""
Slack integration module facade.

Provides Slack integration functionality.
Re-exports from integrations.slack for clean imports.
"""

from integrations.slack.config import (
    NotificationPreferences,
    SlackConfig,
    SlackProjectState,
    format_build_notification,
    format_qa_approval_notification,
    format_qa_request,
    format_slack_message,
    format_spec_approval_request,
    format_subtask_update,
    get_status_color,
    get_status_emoji,
    get_timestamp_url,
)

from integrations.slack.integration import (
    SlackManager,
    get_slack_manager,
    is_slack_enabled,
    prepare_coder_slack_instructions,
    prepare_planner_slack_instructions,
)

from integrations.slack.updater import (
    send_spec_approval_request,
    slack_build_completed,
    slack_build_failed,
    slack_build_started,
    slack_qa_approval,
)

__all__ = [
    # Config exports
    "NotificationPreferences",
    "SlackConfig",
    "SlackProjectState",
    "format_build_notification",
    "format_qa_approval_notification",
    "format_qa_request",
    "format_slack_message",
    "format_spec_approval_request",
    "format_subtask_update",
    "get_status_color",
    "get_status_emoji",
    "get_timestamp_url",
    # Integration exports
    "SlackManager",
    "get_slack_manager",
    "is_slack_enabled",
    "prepare_coder_slack_instructions",
    "prepare_planner_slack_instructions",
    # Updater exports
    "send_spec_approval_request",
    "slack_build_completed",
    "slack_build_failed",
    "slack_build_started",
    "slack_qa_approval",
]
