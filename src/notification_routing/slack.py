"""SlackIntegrator — Slack-style notification management."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Message:
    """A notification message."""
    id: str
    user: str
    text: str
    channel: str = "ci-alerts"
    thread_id: Optional[str] = None
    timestamp: float = 0.0
    resolved: bool = False


@dataclass
class Thread:
    """A notification thread for a failure."""
    id: str
    failure_id: str
    messages: List[Message] = field(default_factory=list)
    status: str = "open"
    created_at: float = 0.0


@dataclass
class NotificationPreferences:
    """User notification preferences."""
    user: str
    enabled: bool = True
    quiet_hours_start: int = 22  # 10pm
    quiet_hours_end: int = 8  # 8am
    min_severity: str = "medium"
    channels: List[str] = field(default_factory=lambda: ["slack"])


class SlackIntegrator:
    """Manage Slack-style notifications for CI failures.

    Creates threads per failure, tracks resolution,
    and respects user notification preferences.
    """

    def __init__(self) -> None:
        self._messages: Dict[str, Message] = {}
        self._threads: Dict[str, Thread] = {}
        self._preferences: Dict[str, NotificationPreferences] = {}
        self._msg_counter = 0

    def send_message(self, user: str, message: str, channel: str = "ci-alerts") -> Message:
        """Send a notification message.

        Args:
            user: Recipient user.
            message: Message text.
            channel: Target channel.

        Returns:
            Created Message.
        """
        self._msg_counter += 1
        msg = Message(
            id=f"msg_{self._msg_counter}",
            user=user,
            text=message,
            channel=channel,
            timestamp=time.time(),
        )
        self._messages[msg.id] = msg
        return msg

    def create_thread(self, failure_id: str) -> Thread:
        """Create a notification thread for a failure.

        Args:
            failure_id: The failure to track.

        Returns:
            Created Thread.
        """
        thread_id = f"thread_{failure_id}"
        thread = Thread(
            id=thread_id,
            failure_id=failure_id,
            created_at=time.time(),
        )
        self._threads[thread_id] = thread
        return thread

    def resolve_thread(self, thread_id: str) -> bool:
        """Mark a thread as resolved.

        Args:
            thread_id: Thread to resolve.

        Returns:
            True if thread was found and resolved.
        """
        thread = self._threads.get(thread_id)
        if not thread:
            return False
        thread.status = "resolved"
        for msg in thread.messages:
            msg.resolved = True
        return True

    def get_notification_preferences(self, user: str) -> NotificationPreferences:
        """Get notification preferences for a user.

        Args:
            user: User identifier.

        Returns:
            User's preferences (defaults if not set).
        """
        return self._preferences.get(user, NotificationPreferences(user=user))

    def set_notification_preferences(self, prefs: NotificationPreferences) -> None:
        """Set notification preferences for a user."""
        self._preferences[prefs.user] = prefs

    def get_thread(self, thread_id: str) -> Optional[Thread]:
        """Get a thread by ID."""
        return self._threads.get(thread_id)

    def get_open_threads(self) -> List[Thread]:
        """Get all open threads."""
        return [t for t in self._threads.values() if t.status == "open"]
