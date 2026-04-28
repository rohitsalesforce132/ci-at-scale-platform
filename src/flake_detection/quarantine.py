"""TestQuarantine — Quarantine flaky tests to stabilize CI."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class QuarantineEntry:
    """A quarantined test entry."""
    test_name: str
    reason: str
    quarantined_at: float
    released_at: Optional[float] = None
    quarantine_count: int = 1


class TestQuarantine:
    """Manage quarantine of flaky tests.

    Quarantined tests are excluded from critical CI paths
    but still tracked for recovery.
    """

    def __init__(self) -> None:
        self._quarantined: Dict[str, QuarantineEntry] = {}
        self._history: List[QuarantineEntry] = []

    def quarantine(self, test_name: str, reason: str = "") -> None:
        """Quarantine a flaky test.

        Args:
            test_name: Test to quarantine.
            reason: Reason for quarantine.
        """
        import time
        if test_name in self._quarantined:
            self._quarantined[test_name].quarantine_count += 1
            return
        entry = QuarantineEntry(
            test_name=test_name,
            reason=reason,
            quarantined_at=time.time(),
        )
        self._quarantined[test_name] = entry
        self._history.append(entry)

    def release(self, test_name: str) -> bool:
        """Release a test from quarantine.

        Args:
            test_name: Test to release.

        Returns:
            True if the test was quarantined and is now released.
        """
        import time
        if test_name not in self._quarantined:
            return False
        entry = self._quarantined.pop(test_name)
        entry.released_at = time.time()
        return True

    def get_quarantined(self) -> List[QuarantineEntry]:
        """Get all currently quarantined tests.

        Returns:
            List of quarantine entries.
        """
        return list(self._quarantined.values())

    def is_quarantined(self, test_name: str) -> bool:
        """Check if a test is currently quarantined.

        Args:
            test_name: Test to check.

        Returns:
            True if quarantined.
        """
        return test_name in self._quarantined

    def get_quarantine_history(self) -> List[QuarantineEntry]:
        """Get full quarantine history including released tests."""
        return list(self._history)

    def get_count(self) -> int:
        """Get number of currently quarantined tests."""
        return len(self._quarantined)
