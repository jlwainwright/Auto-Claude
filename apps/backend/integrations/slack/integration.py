"""
Slack Integration Manager
==========================

Manages two-way Slack integration for Auto-Build progress monitoring and control.
Provides real-time build notifications, spec approvals, and status updates through Slack.

The integration is OPTIONAL - if SLACK_BOT_TOKEN or SLACK_WEBHOOK_URL is not set,
all operations gracefully no-op and the build continues with local tracking only.

Key Features:
- Build lifecycle notifications (start, complete, fail)
- Spec approval requests with interactive buttons
- Subtask status updates
- Progress tracking messages
- QA review requests
"""

import json
import os
from datetime import datetime
from pathlib import Path

from .config import (
    MESSAGE_BUILD_COMPLETE,
    MESSAGE_BUILD_FAIL,
    MESSAGE_BUILD_START,
    MESSAGE_QA_APPROVAL,
    MESSAGE_SPEC_APPROVAL,
    MESSAGE_SUBTASK_UPDATE,
    SESSION_QA_REQUEST,
    SLACK_PROJECT_MARKER,
    SlackConfig,
    SlackProjectState,
    format_build_notification,
    format_qa_request,
    format_slack_message,
    format_spec_approval_request,
    format_subtask_update,
)


class SlackManager:
    """
    Manages Slack integration for an Auto-Build spec.

    This class provides a high-level interface for:
    - Sending build lifecycle notifications
    - Requesting spec approvals
    - Updating subtask status
    - Sending QA review requests
    - Tracking message mappings for updates

    All operations are idempotent and gracefully handle Slack being unavailable.
    """

    def __init__(self, spec_dir: Path, project_dir: Path):
        """
        Initialize Slack manager.

        Args:
            spec_dir: Spec directory (contains implementation_plan.json)
            project_dir: Project root directory
        """
        self.spec_dir = spec_dir
        self.project_dir = project_dir
        self.config = SlackConfig.from_env()
        self.state: SlackProjectState | None = None
        self._mcp_available = False

        # Load existing state if available
        self.state = SlackProjectState.load(spec_dir)

        # Check if Slack MCP tools are available
        self._check_mcp_availability()

    def _check_mcp_availability(self) -> None:
        """Check if Slack MCP tools are available in the environment."""
        # In agent context, MCP tools are available via claude-code
        # We'll assume they're available if SLACK_BOT_TOKEN or SLACK_WEBHOOK_URL is set
        self._mcp_available = self.config.is_valid()

    @property
    def is_enabled(self) -> bool:
        """Check if Slack integration is enabled and available."""
        return self.config.is_valid() and self._mcp_available

    @property
    def is_initialized(self) -> bool:
        """Check if Slack channel has been initialized for this spec."""
        return self.state is not None and self.state.initialized

    def get_message_timestamp(self, subtask_id: str) -> str | None:
        """
        Get the Slack message timestamp for a subtask.

        Args:
            subtask_id: Subtask ID from implementation_plan.json

        Returns:
            Slack message timestamp or None if not mapped
        """
        if not self.state:
            return None
        return self.state.message_mapping.get(subtask_id)

    def set_message_timestamp(self, subtask_id: str, message_ts: str) -> None:
        """
        Store the mapping between a subtask and its Slack message timestamp.

        Args:
            subtask_id: Subtask ID from implementation_plan.json
            message_ts: Slack message timestamp
        """
        if not self.state:
            self.state = SlackProjectState()

        self.state.message_mapping[subtask_id] = message_ts
        self.state.save(self.spec_dir)

    def initialize_channel(self, channel_id: str) -> bool:
        """
        Initialize a Slack channel for this spec.

        This should be called by the agent during the planner session
        to set up the Slack channel for notifications.

        Args:
            channel_id: Slack channel ID

        Returns:
            True if successful
        """
        if not self.is_enabled:
            print("Slack integration not enabled (SLACK_BOT_TOKEN or SLACK_WEBHOOK_URL not set)")
            return False

        # Create initial state
        self.state = SlackProjectState(
            initialized=True,
            channel_id=channel_id,
            created_at=datetime.now().isoformat(),
        )

        self.state.save(self.spec_dir)
        return True

    def load_implementation_plan(self) -> dict | None:
        """Load the implementation plan from spec directory."""
        plan_file = self.spec_dir / "implementation_plan.json"
        if not plan_file.exists():
            return None

        try:
            with open(plan_file) as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return None

    def get_notification_preferences(self) -> dict:
        """
        Get notification preferences for this spec.

        Returns:
            Dict of notification preferences
        """
        if not self.state:
            return {}
        return self.state.preferences

    def update_notification_preferences(self, preferences: dict) -> None:
        """
        Update notification preferences.

        Args:
            preferences: Dict of notification preferences
        """
        if not self.state:
            self.state = SlackProjectState()

        # Merge with existing preferences
        current = self.state.preferences.copy()
        current.update(preferences)
        self.state.preferences = current

        self.state.save(self.spec_dir)

    def send_build_start_notification(
        self,
        spec_name: str,
        phase_name: str | None = None,
        subtask_count: int = 0,
    ) -> dict:
        """
        Send a build start notification to Slack.

        Args:
            spec_name: Name of the spec
            phase_name: Current phase name (optional)
            subtask_count: Total number of subtasks

        Returns:
            Dict with message data for sending
        """
        if not self.is_enabled or not self.state:
            return {}

        plan = self.load_implementation_plan()
        if plan:
            subtask_count = len(plan.get("phases", []))

        message = format_build_notification(
            spec_name=spec_name,
            build_status="start",
            phase_name=phase_name,
            subtask_count=subtask_count,
            completed_count=0,
        )

        return {
            "channel_id": self.state.channel_id,
            "message": message,
            "message_type": MESSAGE_BUILD_START,
        }

    def send_build_complete_notification(
        self,
        spec_name: str,
        phase_name: str | None = None,
        subtask_count: int = 0,
        completed_count: int = 0,
    ) -> dict:
        """
        Send a build complete notification to Slack.

        Args:
            spec_name: Name of the spec
            phase_name: Current phase name (optional)
            subtask_count: Total number of subtasks
            completed_count: Number of completed subtasks

        Returns:
            Dict with message data for sending
        """
        if not self.is_enabled or not self.state:
            return {}

        message = format_build_notification(
            spec_name=spec_name,
            build_status="completed",
            phase_name=phase_name,
            subtask_count=subtask_count,
            completed_count=completed_count,
        )

        return {
            "channel_id": self.state.channel_id,
            "message": message,
            "message_type": MESSAGE_BUILD_COMPLETE,
        }

    def send_build_fail_notification(
        self,
        spec_name: str,
        error_message: str,
    ) -> dict:
        """
        Send a build failure notification to Slack.

        Args:
            spec_name: Name of the spec
            error_message: Error message describing the failure

        Returns:
            Dict with message data for sending
        """
        if not self.is_enabled or not self.state:
            return {}

        message = format_slack_message(
            message_type=MESSAGE_BUILD_FAIL,
            title="Build Failed",
            text=f"*{spec_name}*\n*Error:* {error_message}",
            status="failed",
            footer=f"Auto Claude Build • {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        )

        return {
            "channel_id": self.state.channel_id,
            "message": message,
            "message_type": MESSAGE_BUILD_FAIL,
        }

    def send_spec_approval_request(
        self,
        spec_name: str,
        spec_id: str,
        description: str,
        requirements: list[str] | None = None,
    ) -> dict:
        """
        Send a spec approval request to Slack.

        Args:
            spec_name: Name of the spec
            spec_id: Spec ID (e.g., "001-feature")
            description: Spec description
            requirements: List of key requirements

        Returns:
            Dict with message data for sending
        """
        if not self.is_enabled or not self.state:
            return {}

        message = format_spec_approval_request(
            spec_name=spec_name,
            spec_id=spec_id,
            description=description,
            requirements=requirements,
        )

        return {
            "channel_id": self.state.channel_id,
            "message": message,
            "message_type": MESSAGE_SPEC_APPROVAL,
        }

    def send_subtask_update(
        self,
        subtask_id: str,
        subtask_title: str,
        old_status: str,
        new_status: str,
        phase_name: str | None = None,
    ) -> dict:
        """
        Send a subtask status update to Slack.

        Args:
            subtask_id: Subtask ID (e.g., "subtask-1-1")
            subtask_title: Subtask title/description
            old_status: Previous status
            new_status: New status
            phase_name: Current phase name (optional)

        Returns:
            Dict with message data for sending
        """
        if not self.is_enabled or not self.state:
            return {}

        # Check if notifications are enabled for subtasks
        preferences = self.state.get_preferences()
        if not preferences.notify_subtask_updates:
            return {}

        message = format_subtask_update(
            subtask_id=subtask_id,
            subtask_title=subtask_title,
            old_status=old_status,
            new_status=new_status,
            phase_name=phase_name,
        )

        return {
            "channel_id": self.state.channel_id,
            "message": message,
            "message_type": MESSAGE_SUBTASK_UPDATE,
        }

    def send_qa_request(
        self,
        spec_name: str,
        qa_report_path: str,
        issues_count: int,
        spec_id: str,
    ) -> dict:
        """
        Send a QA review request to Slack.

        Args:
            spec_name: Name of the spec
            qa_report_path: Path to QA report
            issues_count: Number of issues found
            spec_id: Spec ID

        Returns:
            Dict with message data for sending
        """
        if not self.is_enabled or not self.state:
            return {}

        message = format_qa_request(
            spec_name=spec_name,
            qa_report_path=qa_report_path,
            issues_count=issues_count,
            spec_id=spec_id,
        )

        return {
            "channel_id": self.state.channel_id,
            "message": message,
            "message_type": SESSION_QA_REQUEST,
        }

    def send_qa_approval_notification(
        self,
        spec_name: str,
        qa_status: str,
        qa_session: int,
        issues_count: int = 0,
        report_path: str | None = None,
    ) -> dict:
        """
        Send a QA approval/rejection notification to Slack.

        Args:
            spec_name: Name of the spec
            qa_status: "approved" or "rejected"
            qa_session: QA session number
            issues_count: Number of issues found (if rejected)
            report_path: Path to QA report (optional)

        Returns:
            Dict with message data for sending
        """
        if not self.is_enabled or not self.state:
            return {}

        from .config import format_qa_approval_notification

        message = format_qa_approval_notification(
            spec_name=spec_name,
            qa_status=qa_status,
            qa_session=qa_session,
            issues_count=issues_count,
            report_path=report_path,
        )

        return {
            "channel_id": self.state.channel_id,
            "message": message,
            "message_type": MESSAGE_QA_APPROVAL,
        }

    def update_progress_message(
        self,
        spec_name: str,
        phase_name: str | None = None,
        subtask_count: int = 0,
        completed_count: int = 0,
    ) -> dict | None:
        """
        Update or create a progress tracking message in Slack.

        Args:
            spec_name: Name of the spec
            phase_name: Current phase name (optional)
            subtask_count: Total number of subtasks
            completed_count: Number of completed subtasks

        Returns:
            Dict with message data for update, or None if not enabled
        """
        if not self.is_enabled or not self.state:
            return None

        # Build progress message
        progress_pct = int((completed_count / subtask_count * 100)) if subtask_count > 0 else 0

        message = format_slack_message(
            message_type="progress_update",
            title=f"Build Progress: {spec_name}",
            text=(
                f"*Phase:* {phase_name or 'Initializing'}\n"
                f"*Progress:* {completed_count}/{subtask_count} subtasks ({progress_pct}%)\n"
                f"*Status:* {'In Progress' if completed_count < subtask_count else 'Complete'}"
            ),
            status="in_progress" if completed_count < subtask_count else "completed",
            footer=f"Auto Claude • {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        )

        # If we have a previous notification timestamp, we can update it
        return {
            "channel_id": self.state.channel_id,
            "message": message,
            "message_type": "progress_update",
            "update_ts": self.state.notification_ts,  # May be None
        }

    def get_progress_summary(self) -> dict:
        """
        Get a summary of Slack integration progress.

        Returns:
            Dict with progress statistics
        """
        plan = self.load_implementation_plan()
        if not plan:
            return {
                "enabled": self.is_enabled,
                "initialized": False,
                "total_subtasks": 0,
                "total_messages": 0,
            }

        # Count total subtasks
        subtasks = 0
        phases = plan.get("phases", [])
        for phase in phases:
            subtasks += len(phase.get("subtasks", []))

        return {
            "enabled": self.is_enabled,
            "initialized": self.is_initialized,
            "channel_id": self.state.channel_id if self.state else None,
            "notification_ts": self.state.notification_ts if self.state else None,
            "approval_ts": self.state.approval_ts if self.state else None,
            "total_subtasks": subtasks,
            "total_messages": self.state.total_messages if self.state else 0,
            "preferences": self.state.preferences if self.state else {},
        }

    def get_slack_context_for_prompt(self) -> str:
        """
        Generate Slack context section for agent prompts.

        This is included in the subtask prompt to give the agent
        awareness of Slack integration status.

        Returns:
            Markdown-formatted context string
        """
        if not self.is_enabled:
            return ""

        summary = self.get_progress_summary()

        if not summary["initialized"]:
            return """
## Slack Integration

Slack integration is enabled but not yet initialized.
During the planner session, configure the Slack channel for notifications.

Available Slack MCP tools:
- `mcp__slack-server__list_channels` - List available channels
- `mcp__slack-server__send_message` - Send notifications to a channel
- `mcp__slack-server__update_message` - Update existing messages
"""

        lines = [
            "## Slack Integration",
            "",
            f"**Channel:** {summary['channel_id']}",
            f"**Messages Sent:** {summary['total_messages']}",
            "",
            "When working on subtasks:",
            "- Progress updates will be sent to the configured channel",
            "- Build events (start, complete, fail) trigger notifications",
            "- Spec approvals and QA requests sent via interactive messages",
        ]

        return "\n".join(lines)

    def save_state(self) -> None:
        """Save the current state to disk."""
        if self.state:
            self.state.save(self.spec_dir)

    def increment_message_count(self) -> None:
        """Increment the total message counter."""
        if self.state:
            self.state.total_messages += 1
            self.state.save(self.spec_dir)

    def set_notification_timestamp(self, timestamp: str) -> None:
        """
        Store the timestamp of the main notification message.

        Args:
            timestamp: Slack message timestamp
        """
        if self.state:
            self.state.notification_ts = timestamp
            self.state.save(self.spec_dir)

    def set_approval_timestamp(self, timestamp: str) -> None:
        """
        Store the timestamp of the approval request message.

        Args:
            timestamp: Slack message timestamp
        """
        if self.state:
            self.state.approval_ts = timestamp
            self.state.save(self.spec_dir)

    async def notify_approval_decision(
        self,
        spec_name: str,
        approved: bool,
        approved_by: str = "user",
    ) -> bool:
        """
        Update the approval request message with the approval decision.

        Args:
            spec_name: Name of the spec
            approved: Whether the spec was approved (True) or rejected (False)
            approved_by: Who approved/rejected (e.g., "user", "slack")

        Returns:
            True if successful, False otherwise
        """
        if not self.is_enabled or not self.state:
            return False

        if not self.state.approval_ts:
            # No approval message to update
            return False

        try:
            from slack_integration import _update_message_in_slack

            # Build update message
            status_emoji = "✅" if approved else "❌"
            status_text = "APPROVED" if approved else "REJECTED"
            color = "#36a64f" if approved else "#dc3545"

            message = {
                "attachments": [
                    {
                        "color": color,
                        "blocks": [
                            {
                                "type": "header",
                                "text": {
                                    "type": "plain_text",
                                    "text": f"{status_emoji} Spec {status_text}",
                                    "emoji": True,
                                },
                            },
                            {
                                "type": "section",
                                "fields": [
                                    {
                                        "type": "mrkdwn",
                                        "text": f"*Spec:*\n{spec_name}",
                                    },
                                    {
                                        "type": "mrkdwn",
                                        "text": f"*Decision:*\n{status_text}",
                                    },
                                    {
                                        "type": "mrkdwn",
                                        "text": f"*By:*\n{approved_by}",
                                    },
                                    {
                                        "type": "mrkdwn",
                                        "text": f"*When:*\n{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                                    },
                                ],
                            },
                        ],
                    }
                ]
            }

            # Update the approval message
            await _update_message_in_slack(
                spec_dir=self.spec_dir,
                project_dir=self.project_dir,
                channel_id=self.state.channel_id,
                message_ts=self.state.approval_ts,
                message_updates=message,
            )

            return True
        except Exception:
            return False


# Utility functions for integration with other modules


def get_slack_manager(spec_dir: Path, project_dir: Path) -> SlackManager:
    """
    Get a SlackManager instance for the given spec.

    This is the main entry point for other modules.

    Args:
        spec_dir: Spec directory
        project_dir: Project root directory

    Returns:
        SlackManager instance
    """
    return SlackManager(spec_dir, project_dir)


def is_slack_enabled() -> bool:
    """Quick check if Slack integration is available."""
    return bool(os.environ.get("SLACK_BOT_TOKEN") or os.environ.get("SLACK_WEBHOOK_URL"))


def prepare_planner_slack_instructions(spec_dir: Path) -> str:
    """
    Generate Slack setup instructions for the planner agent.

    This is included in the planner prompt when Slack is enabled.

    Args:
        spec_dir: Spec directory

    Returns:
        Markdown instructions for Slack setup
    """
    if not is_slack_enabled():
        return ""

    return """
## Slack Integration Setup

Slack integration is ENABLED. After creating the implementation plan:

### Step 1: Find the Channel
```
Use mcp__slack-server__list_channels to find your target channel ID
```

### Step 2: Initialize the Channel
```
Use mcp__slack-server__send_message to send an initial message:
- channel: Your channel ID
- text: "Build started for {spec_name}"
```
Save the channel ID and message timestamp to .slack_project.json

### Step 3: Configure Notifications
The SlackManager will automatically:
- Send build start/complete/fail notifications
- Request spec approvals with interactive buttons
- Update progress during the build
- Send QA review requests

### Important Notes
- Update .slack_project.json after each Slack operation
- The JSON structure should include:
  - initialized: true
  - channel_id: "..."
  - notification_ts: "..." (optional, for progress updates)
  - approval_ts: "..." (optional, for approval requests)
  - message_mapping: { "subtask-1-1": "1234567890.123456", ... }
"""


def prepare_coder_slack_instructions(
    spec_dir: Path,
    subtask_id: str,
) -> str:
    """
    Generate Slack instructions for the coding agent.

    Args:
        spec_dir: Spec directory
        subtask_id: Current subtask being worked on

    Returns:
        Markdown instructions for Slack updates
    """
    if not is_slack_enabled():
        return ""

    manager = SlackManager(spec_dir, spec_dir.parent.parent)  # Approximate project_dir

    if not manager.is_initialized:
        return ""

    return f"""
## Slack Notifications

This build is linked to Slack channel: `{manager.state.channel_id if manager.state else 'N/A'}`

### Subtask Updates
When completing this subtask, a status update will be sent to Slack automatically.

### Progress Updates
Build progress is automatically tracked and updated in the channel as subtasks complete.
"""
