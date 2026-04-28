"""NotificationRouter — Route failure notifications smartly."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class Failure:
    """A CI failure to route."""
    id: str
    test_name: str
    error_message: str
    commit: str = ""
    severity: str = "medium"


@dataclass
class RoutingDecision:
    """Result of routing a failure."""
    failure_id: str
    recipient: str
    channel: str
    priority: str
    suppressed: bool
    reason: str


@dataclass
class RoutingRule:
    """A routing rule for notifications."""
    name: str
    condition: Callable[[Failure], bool]
    channel: str = "slack"
    priority: str = "medium"


class NotificationRouter:
    """Route failure notifications to the right people.

    Applies routing rules, suppresses noise, and ensures
    the right people get notified at the right priority.
    """

    def __init__(self) -> None:
        self._rules: List[RoutingRule] = []
        self._suppressed: Dict[str, int] = {}  # failure_pattern -> count
        self._routed: List[RoutingDecision] = []

    def route(self, failure: Failure) -> RoutingDecision:
        """Route a failure notification.

        Args:
            failure: The failure to route.

        Returns:
            RoutingDecision with routing details.
        """
        # Check suppression (same error seen many times)
        if self._should_suppress(failure):
            key = failure.error_message[:50]
            self._suppressed[key] = self._suppressed.get(key, 0) + 1
            decision = RoutingDecision(
                failure_id=failure.id,
                recipient="",
                channel="none",
                priority="low",
                suppressed=True,
                reason="Duplicate failure already notified",
            )
            self._routed.append(decision)
            return decision

        # Apply rules
        for rule in self._rules:
            if rule.condition(failure):
                decision = RoutingDecision(
                    failure_id=failure.id,
                    recipient=rule.name,
                    channel=rule.channel,
                    priority=rule.priority,
                    suppressed=False,
                    reason=f"Matched rule: {rule.name}",
                )
                self._routed.append(decision)
                return decision

        # Default routing
        decision = RoutingDecision(
            failure_id=failure.id,
            recipient="ci-team",
            channel="slack",
            priority=failure.severity,
            suppressed=False,
            reason="Default routing",
        )
        self._routed.append(decision)
        return decision

    def find_responsible(self, commit: str) -> Optional[str]:
        """Find the responsible person for a commit.

        Args:
            commit: Commit SHA.

        Returns:
            Author identifier or None.
        """
        # In real implementation, would query git blame
        return f"author-{commit[:7]}" if commit else None

    def should_notify(self, failure: Failure, user: str) -> bool:
        """Determine if a user should be notified.

        Args:
            failure: The failure.
            user: User identifier.

        Returns:
            True if user should be notified.
        """
        decision = self.route(failure)
        return not decision.suppressed and decision.recipient in (user, "ci-team")

    def get_routing_rules(self) -> List[RoutingRule]:
        """Get current routing rules.

        Returns:
            List of routing rules.
        """
        return list(self._rules)

    def add_rule(self, rule: RoutingRule) -> None:
        """Add a routing rule."""
        self._rules.append(rule)

    def get_routed_count(self) -> int:
        """Get count of routed notifications."""
        return len(self._routed)

    def _should_suppress(self, failure: Failure) -> bool:
        key = failure.error_message[:50]
        count = self._suppressed.get(key, 0)
        return count >= 3 and failure.severity != "critical"
