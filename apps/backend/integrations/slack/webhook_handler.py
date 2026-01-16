"""
Slack Webhook Handler - Incoming Event Processing
===================================================

Handles incoming Slack events for approve/reject interactions.
Processes reactions, button clicks, and other interactive events.

Design Principles:
- Validate all incoming requests (signature verification)
- Parse Slack events into actionable commands
- Update spec state based on user interactions
- Graceful degradation if webhook malformed
- Follow Linear updater pattern for state management

Event Types Supported:
- reaction_added: Emoji reactions on messages (✅ approve, ❌ reject)
- url_verification: Initial Slack webhook verification
- interactive: Button clicks from approval messages
"""

import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from .config import (
    MESSAGE_SPEC_APPROVAL,
    SESSION_QA_REQUEST,
    REACTION_APPROVE,
    REACTION_REJECT,
    SLACK_PROJECT_MARKER,
    SlackProjectState,
)


# Event types
EVENT_TYPE_REACTION = "reaction_added"
EVENT_TYPE_URL_VERIFICATION = "url_verification"
EVENT_TYPE_INTERACTIVE = "interactive"
EVENT_TYPE_APP_MENTION = "app_mention"

# Action types from buttons
ACTION_APPROVE_SPEC = "approve_spec"
ACTION_REJECT_SPEC = "reject_spec"
ACTION_QA_APPROVE = "qa_approve"
ACTION_QA_REJECT = "qa_reject"


@dataclass
class WebhookEvent:
    """Parsed webhook event."""

    event_type: str
    user_id: str | None = None
    channel_id: str | None = None
    message_ts: str | None = None
    reaction: str | None = None
    action_value: str | None = None
    action_id: str | None = None
    spec_id: str | None = None
    timestamp: str | None = None

    def is_approval(self) -> bool:
        """Check if this is an approval action."""
        return (
            self.reaction == REACTION_APPROVE
            or self.action_id == ACTION_APPROVE_SPEC
            or self.action_id == ACTION_QA_APPROVE
        )

    def is_rejection(self) -> bool:
        """Check if this is a rejection action."""
        return (
            self.reaction == REACTION_REJECT
            or self.action_id == ACTION_REJECT_SPEC
            or self.action_id == ACTION_QA_REJECT
        )


def get_signing_secret() -> str:
    """Get the Slack signing secret from environment."""
    return os.environ.get("SLACK_SIGNING_SECRET", "")


def verify_slack_request(
    timestamp: str,
    signature: str,
    body: str,
) -> bool:
    """
    Verify an incoming Slack webhook request.

    Args:
        timestamp: X-Slack-Request-Timestamp header
        signature: X-Slack-Signature header
        body: Raw request body

    Returns:
        True if signature is valid
    """
    signing_secret = get_signing_secret()
    if not signing_secret:
        return False

    # Check timestamp to prevent replay attacks (5 min tolerance)
    current_time = int(time.time())
    request_time = int(timestamp)
    if abs(current_time - request_time) > 300:
        return False

    # Create signature
    basestring = f"v0:{timestamp}:{body}"
    expected_signature = "v0=" + hmac.new(
        signing_secret.encode(),
        basestring.encode(),
        hashlib.sha256,
    ).hexdigest()

    # Compare in constant time to prevent timing attacks
    return hmac.compare_digest(expected_signature, signature)


def parse_reaction_added(event: dict) -> Optional[WebhookEvent]:
    """
    Parse a reaction_added event.

    Args:
        event: Slack event dict

    Returns:
        WebhookEvent if valid, None otherwise
    """
    try:
        return WebhookEvent(
            event_type=EVENT_TYPE_REACTION,
            user_id=event.get("user"),
            channel_id=event.get("item", {}).get("channel"),
            message_ts=event.get("item", {}).get("ts"),
            reaction=event.get("reaction"),
            timestamp=event.get("event_ts"),
        )
    except (KeyError, AttributeError):
        return None


def parse_interactive_payload(payload: dict) -> Optional[WebhookEvent]:
    """
    Parse an interactive component payload (button click).

    Args:
        payload: Parsed payload from Slack

    Returns:
        WebhookEvent if valid, None otherwise
    """
    try:
        actions = payload.get("actions", [])
        if not actions:
            return None

        action = actions[0]
        action_id = action.get("action_id", "")
        value = action.get("value", "")

        # Parse spec_id from value (format: "approve:001-spec" or "qa_approve:001-spec")
        spec_id = None
        if ":" in value:
            _, spec_id = value.split(":", 1)

        return WebhookEvent(
            event_type=EVENT_TYPE_INTERACTIVE,
            user_id=payload.get("user", {}).get("id"),
            channel_id=payload.get("channel", {}).get("id"),
            message_ts=payload.get("message", {}).get("ts"),
            action_id=action_id,
            action_value=value,
            spec_id=spec_id,
            timestamp=payload.get("trigger_id"),
        )
    except (KeyError, AttributeError):
        return None


def parse_webhook_payload(body: str) -> tuple[Optional[WebhookEvent], str | None]:
    """
    Parse incoming Slack webhook payload.

    Args:
        body: Raw request body string

    Returns:
        Tuple of (WebhookEvent or None, error_message or None)
    """
    try:
        data = json.loads(body)

        # Handle URL verification challenge
        if data.get("type") == EVENT_TYPE_URL_VERIFICATION:
            event = WebhookEvent(
                event_type=EVENT_TYPE_URL_VERIFICATION,
                timestamp=data.get("token"),
            )
            return event, None

        # Handle reaction_added events
        if data.get("type") == "event_callback":
            inner_event = data.get("event", {})
            if inner_event.get("type") == EVENT_TYPE_REACTION:
                return parse_reaction_added(inner_event), None

        # Handle interactive payloads (different structure)
        if "payload" in data:
            payload = json.loads(data["payload"])
            return parse_interactive_payload(payload), None

        return None, "Unknown event type"

    except (json.JSONDecodeError, KeyError, AttributeError) as e:
        return None, f"Failed to parse payload: {e}"


class SlackWebhookHandler:
    """
    Handler for incoming Slack webhook events.

    This class processes incoming events from Slack and updates
    spec state based on user interactions (approve/reject).
    """

    def __init__(self, spec_dir: Path):
        """
        Initialize webhook handler.

        Args:
            spec_dir: Spec directory (contains implementation_plan.json and .slack_project.json)
        """
        self.spec_dir = spec_dir
        self.state: SlackProjectState | None = None

        # Load existing state
        self._load_state()

    def _load_state(self) -> None:
        """Load Slack project state from spec directory."""
        self.state = SlackProjectState.load(self.spec_dir)

    def _save_state(self) -> None:
        """Save Slack project state to spec directory."""
        if self.state:
            self.state.save(self.spec_dir)

    def _load_implementation_plan(self) -> dict | None:
        """Load the implementation plan."""
        plan_file = self.spec_dir / "implementation_plan.json"
        if not plan_file.exists():
            return None

        try:
            with open(plan_file) as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return None

    def _update_spec_approval(self, approved: bool, user_id: str) -> bool:
        """
        Update spec approval status in implementation plan.

        Args:
            approved: True if approved, False if rejected
            user_id: Slack user ID who approved/rejected

        Returns:
            True if successful
        """
        plan = self._load_implementation_plan()
        if not plan:
            return False

        # Add approval metadata to plan
        plan["slack_approval"] = {
            "approved": approved,
            "approved_by": user_id,
            "approved_at": datetime.now().isoformat(),
        }

        # Save updated plan
        plan_file = self.spec_dir / "implementation_plan.json"
        try:
            with open(plan_file, "w") as f:
                json.dump(plan, f, indent=2)
            return True
        except OSError:
            return False

    def _update_qa_approval(self, approved: bool, user_id: str) -> bool:
        """
        Update QA approval status in implementation plan.

        Args:
            approved: True if approved, False if fixes requested
            user_id: Slack user ID who approved/rejected

        Returns:
            True if successful
        """
        plan = self._load_implementation_plan()
        if not plan:
            return False

        # Update QA signoff
        qa_signoff = plan.get("qa_signoff", {})
        qa_signoff["slack_reviewed"] = True
        qa_signoff["slack_approved"] = approved
        qa_signoff["slack_reviewed_by"] = user_id
        qa_signoff["slack_reviewed_at"] = datetime.now().isoformat()

        plan["qa_signoff"] = qa_signoff

        # Save updated plan
        plan_file = self.spec_dir / "implementation_plan.json"
        try:
            with open(plan_file, "w") as f:
                json.dump(plan, f, indent=2)
            return True
        except OSError:
            return False

    def handle_reaction(self, event: WebhookEvent) -> dict:
        """
        Handle a reaction event (emoji added to message).

        Args:
            event: Parsed webhook event

        Returns:
            Response dict with status and message
        """
        if not self.state:
            return {
                "status": "error",
                "message": "Slack integration not initialized for this spec",
            }

        # Check if reaction is on the approval message
        if event.message_ts != self.state.approval_ts:
            return {
                "status": "ignored",
                "message": "Reaction not on approval message",
            }

        if event.is_approval():
            success = self._update_spec_approval(True, event.user_id or "unknown")
            if success:
                return {
                    "status": "success",
                    "action": "approved",
                    "message": f"Spec approved by {event.user_id}",
                }
            else:
                return {
                    "status": "error",
                    "message": "Failed to update approval status",
                }

        elif event.is_rejection():
            success = self._update_spec_approval(False, event.user_id or "unknown")
            if success:
                return {
                    "status": "success",
                    "action": "rejected",
                    "message": f"Spec rejected by {event.user_id}",
                }
            else:
                return {
                    "status": "error",
                    "message": "Failed to update rejection status",
                }

        return {
            "status": "ignored",
            "message": f"Reaction '{event.reaction}' not recognized",
        }

    def handle_interactive(self, event: WebhookEvent) -> dict:
        """
        Handle an interactive component event (button click).

        Args:
            event: Parsed webhook event

        Returns:
            Response dict with status and message
        """
        if not self.state:
            return {
                "status": "error",
                "message": "Slack integration not initialized for this spec",
            }

        # Handle spec approval
        if event.action_id == ACTION_APPROVE_SPEC:
            success = self._update_spec_approval(True, event.user_id or "unknown")
            if success:
                return {
                    "status": "success",
                    "action": "approved",
                    "message": f"Spec approved by {event.user_id}",
                    "replace_original": True,
                    "response_text": f":white_check_mark: Spec approved by <@{event.user_id}>",
                }
            else:
                return {
                    "status": "error",
                    "message": "Failed to update approval status",
                }

        elif event.action_id == ACTION_REJECT_SPEC:
            success = self._update_spec_approval(False, event.user_id or "unknown")
            if success:
                return {
                    "status": "success",
                    "action": "rejected",
                    "message": f"Spec rejected by {event.user_id}",
                    "replace_original": True,
                    "response_text": f":x: Spec rejected by <@{event.user_id}>",
                }
            else:
                return {
                    "status": "error",
                    "message": "Failed to update rejection status",
                }

        # Handle QA approval
        elif event.action_id == ACTION_QA_APPROVE:
            success = self._update_qa_approval(True, event.user_id or "unknown")
            if success:
                return {
                    "status": "success",
                    "action": "qa_approved",
                    "message": f"QA approved by {event.user_id}",
                    "replace_original": True,
                    "response_text": f":white_check_mark: QA approved by <@{event.user_id}>",
                }
            else:
                return {
                    "status": "error",
                    "message": "Failed to update QA approval status",
                }

        elif event.action_id == ACTION_QA_REJECT:
            success = self._update_qa_approval(False, event.user_id or "unknown")
            if success:
                return {
                    "status": "success",
                    "action": "qa_rejected",
                    "message": f"Fixes requested by {event.user_id}",
                    "replace_original": True,
                    "response_text": f":x: Fixes requested by <@{event.user_id}>",
                }
            else:
                return {
                    "status": "error",
                    "message": "Failed to update QA rejection status",
                }

        return {
            "status": "ignored",
            "message": f"Unknown action_id: {event.action_id}",
        }

    def handle_event(self, event: WebhookEvent) -> dict:
        """
        Handle a parsed webhook event.

        Args:
            event: Parsed webhook event

        Returns:
            Response dict with status and message
        """
        if event.event_type == EVENT_TYPE_REACTION:
            return self.handle_reaction(event)

        elif event.event_type == EVENT_TYPE_INTERACTIVE:
            return self.handle_interactive(event)

        elif event.event_type == EVENT_TYPE_URL_VERIFICATION:
            return {
                "status": "challenge",
                "message": "URL verification required",
                "challenge": event.timestamp,  # Using timestamp field to store challenge
            }

        return {
            "status": "ignored",
            "message": f"Unhandled event type: {event.event_type}",
        }


# === Convenience functions ===


def handle_slack_webhook(
    spec_dir: Path,
    body: str,
    timestamp: str,
    signature: str,
) -> tuple[int, str | dict]:
    """
    Handle an incoming Slack webhook request.

    This is the main entry point for webhook processing.

    Args:
        spec_dir: Spec directory
        body: Raw request body
        timestamp: X-Slack-Request-Timestamp header
        signature: X-Slack-Signature header

    Returns:
        Tuple of (status_code, response_body)
        - status_code: HTTP status code (200, 401, 500)
        - response_body: Dict or challenge string for URL verification
    """
    # Verify signature
    if not verify_slack_request(timestamp, signature, body):
        return 401, {"error": "Invalid signature"}

    # Parse payload
    event, error = parse_webhook_payload(body)
    if error:
        return 400, {"error": error}

    if not event:
        return 400, {"error": "Failed to parse event"}

    # Handle event
    handler = SlackWebhookHandler(spec_dir)
    result = handler.handle_event(event)

    # Handle URL verification challenge
    if result.get("status") == "challenge":
        return 200, {"challenge": result.get("challenge")}

    # Return success response
    if result.get("status") == "success":
        # For interactive messages, return the response text
        if "response_text" in result:
            return 200, {
                "text": result["response_text"],
                "replace_original": result.get("replace_original", False),
            }
        return 200, result

    # Return error response
    if result.get("status") == "error":
        return 500, result

    # Ignored events return 200 OK
    return 200, result


def is_webhook_configured() -> bool:
    """Check if Slack webhook is configured."""
    return bool(get_signing_secret())


def get_webhook_handler(spec_dir: Path) -> SlackWebhookHandler:
    """
    Get a webhook handler for the given spec.

    Args:
        spec_dir: Spec directory

    Returns:
        SlackWebhookHandler instance
    """
    return SlackWebhookHandler(spec_dir)
