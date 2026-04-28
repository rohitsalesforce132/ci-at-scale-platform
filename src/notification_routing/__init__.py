"""Notification Routing — Smart failure notification and routing."""

from .router import NotificationRouter
from .blamer import CommitBlamer
from .slack import SlackIntegrator
from .escalation import EscalationManager

__all__ = ["NotificationRouter", "CommitBlamer", "SlackIntegrator", "EscalationManager"]
