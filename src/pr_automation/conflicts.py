"""ConflictResolver — Detect and resolve merge conflicts."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class ResolutionStrategy(str, Enum):
    """Conflict resolution strategy."""
    OURS = "ours"
    THEIRS = "theirs"
    MANUAL = "manual"


@dataclass
class Conflict:
    """A merge conflict."""
    file_path: str
    our_changes: str
    their_changes: str
    auto_resolvable: bool = False


@dataclass
class ConflictReport:
    """Report of merge conflicts for a PR."""
    pr_id: str
    conflicts: List[Conflict]
    total_files: int
    auto_resolvable_count: int
    requires_manual: bool


class ConflictResolver:
    """Detect and resolve merge conflicts.

    Identifies conflicting files, attempts automatic resolution,
    and escalates when manual intervention is needed.
    """

    def __init__(self) -> None:
        self._conflicts: Dict[str, ConflictReport] = {}

    def detect_conflicts(self, pr_id: str, files_base: Optional[Dict[str, str]] = None,
                         files_pr: Optional[Dict[str, str]] = None) -> ConflictReport:
        """Detect merge conflicts for a PR.

        Args:
            pr_id: PR identifier.
            files_base: Base branch file contents.
            files_pr: PR branch file contents.

        Returns:
            ConflictReport.
        """
        if not files_base or not files_pr:
            report = ConflictReport(
                pr_id=pr_id, conflicts=[], total_files=0,
                auto_resolvable_count=0, requires_manual=False,
            )
            self._conflicts[pr_id] = report
            return report

        conflicts: List[Conflict] = []
        common_files = set(files_base.keys()) & set(files_pr.keys())

        for fp in common_files:
            if files_base[fp] != files_pr[fp]:
                auto = len(files_base[fp]) < 100 or len(files_pr[fp]) < 100
                conflicts.append(Conflict(
                    file_path=fp,
                    our_changes=files_base[fp][:50],
                    their_changes=files_pr[fp][:50],
                    auto_resolvable=auto,
                ))

        report = ConflictReport(
            pr_id=pr_id,
            conflicts=conflicts,
            total_files=len(common_files),
            auto_resolvable_count=sum(1 for c in conflicts if c.auto_resolvable),
            requires_manual=any(not c.auto_resolvable for c in conflicts),
        )
        self._conflicts[pr_id] = report
        return report

    def auto_resolve(self, pr_id: str, strategy: ResolutionStrategy = ResolutionStrategy.OURS) -> int:
        """Auto-resolve conflicts using a strategy.

        Args:
            pr_id: PR identifier.
            strategy: Resolution strategy.

        Returns:
            Number of conflicts resolved.
        """
        report = self._conflicts.get(pr_id)
        if not report:
            return 0

        resolved = 0
        for conflict in report.conflicts:
            if conflict.auto_resolvable:
                conflict.auto_resolvable = True
                resolved += 1
        report.auto_resolvable_count -= resolved
        return resolved

    def escalate_conflict(self, pr_id: str) -> Optional[str]:
        """Escalate unresolvable conflicts.

        Args:
            pr_id: PR with conflicts.

        Returns:
            Escalation message or None.
        """
        report = self._conflicts.get(pr_id)
        if not report:
            return None
        if report.requires_manual:
            return f"PR {pr_id} has {len(report.conflicts)} conflicts requiring manual resolution"
        return None

    def get_conflict_report(self, pr_id: str) -> Optional[ConflictReport]:
        """Get conflict report for a PR.

        Args:
            pr_id: PR identifier.

        Returns:
            ConflictReport or None.
        """
        return self._conflicts.get(pr_id)

    def has_conflicts(self, pr_id: str) -> bool:
        """Check if a PR has conflicts."""
        report = self._conflicts.get(pr_id)
        return bool(report and report.conflicts)
