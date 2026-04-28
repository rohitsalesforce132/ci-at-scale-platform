"""BranchManager — Manage branch strategies and cleanup."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Branch:
    """A git branch."""
    name: str
    base: str
    author: str = ""
    created_at: float = 0.0
    last_commit_at: float = 0.0
    commit_count: int = 0
    is_merged: bool = False
    is_stale: bool = False


@dataclass
class BranchHealth:
    """Health assessment of a branch."""
    name: str
    behind_main: int
    has_conflicts: bool
    staleness_days: float
    status: str  # 'healthy', 'stale', 'conflicted', 'merged'


@dataclass
class CleanupSuggestion:
    """Suggestion for branch cleanup."""
    branch: str
    action: str  # 'delete', 'rebase', 'merge'
    reason: str


class BranchManager:
    """Manage branch strategies and cleanup.

    Tracks branch health, detects stale branches,
    and suggests cleanup actions.
    """

    STALE_THRESHOLD_DAYS = 30.0

    def __init__(self) -> None:
        self._branches: Dict[str, Branch] = {}
        self._main_branch = "main"

    def create_branch(self, name: str, base: str = "main") -> Branch:
        """Create a new branch.

        Args:
            name: Branch name.
            base: Base branch.

        Returns:
            Created Branch.
        """
        branch = Branch(
            name=name,
            base=base,
            created_at=time.time(),
            last_commit_at=time.time(),
        )
        self._branches[name] = branch
        return branch

    def detect_stale_branches(self) -> List[Branch]:
        """Detect branches that are stale.

        Returns:
            List of stale branches.
        """
        now = time.time()
        stale_threshold = self.STALE_THRESHOLD_DAYS * 86400
        stale: List[Branch] = []

        for branch in self._branches.values():
            age = now - branch.last_commit_at
            if age > stale_threshold and not branch.is_merged:
                branch.is_stale = True
                stale.append(branch)

        return stale

    def get_branch_health(self, name: str) -> Optional[BranchHealth]:
        """Get health assessment of a branch.

        Args:
            name: Branch name.

        Returns:
            BranchHealth or None.
        """
        branch = self._branches.get(name)
        if not branch:
            return None

        now = time.time()
        staleness = (now - branch.last_commit_at) / 86400

        if branch.is_merged:
            status = "merged"
        elif staleness > self.STALE_THRESHOLD_DAYS:
            status = "stale"
        else:
            status = "healthy"

        return BranchHealth(
            name=name,
            behind_main=0,  # Would need git integration
            has_conflicts=False,
            staleness_days=staleness,
            status=status,
        )

    def suggest_cleanup(self) -> List[CleanupSuggestion]:
        """Suggest branch cleanup actions.

        Returns:
            List of cleanup suggestions.
        """
        suggestions: List[CleanupSuggestion] = []
        for branch in self._branches.values():
            if branch.is_merged:
                suggestions.append(CleanupSuggestion(
                    branch=branch.name,
                    action="delete",
                    reason="Already merged",
                ))
            elif branch.is_stale:
                suggestions.append(CleanupSuggestion(
                    branch=branch.name,
                    action="delete",
                    reason=f"Stale for {self.STALE_THRESHOLD_DAYS}+ days",
                ))
        return suggestions

    def update_branch(self, name: str, commit_count: int = 0) -> None:
        """Update branch activity."""
        branch = self._branches.get(name)
        if branch:
            branch.last_commit_at = time.time()
            branch.commit_count += commit_count

    def mark_merged(self, name: str) -> bool:
        """Mark a branch as merged."""
        branch = self._branches.get(name)
        if branch:
            branch.is_merged = True
            return True
        return False

    def get_all_branches(self) -> List[Branch]:
        """Get all branches."""
        return list(self._branches.values())
