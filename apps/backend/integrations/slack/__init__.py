"""
Slack Integration for Auto Claude
==================================

Provides two-way Slack integration for build monitoring and control.
"""

from integrations.slack.config import (
    SlackConfig,
    SlackProjectState,
    format_slack_message,
    get_status_emoji,
    get_status_color,
    get_timestamp_url,
)

__all__ = [
    "SlackConfig",
    "SlackProjectState",
    "format_slack_message",
    "get_status_emoji",
    "get_status_color",
    "get_timestamp_url",
]
