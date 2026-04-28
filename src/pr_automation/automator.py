"""PRAutomator — Automated PR operations."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class PRStatus(str, Enum):
    """PR status."""
    DRAFT = "draft"
    OPEN = "open"
    APPROVED = "approved"
    MERGED = "merged"
    CLOSED = "closed"


@dataclass
class PR:
    """A pull request."""
    pr_id: str
    title: str
    author: str = ""
    branch: str = ""
    status: PRStatus = PRStatus.OPEN
    files: List[str] = field(default_factory=list)
    reviewers: List[str] = field(default_factory=list)
    created_at: float = 0.0
    checks_passing: bool = False
    conflicts: bool = False


@dataclass
class Diagnosis:
    """Simplified diagnosis for fix PR."""
    root_cause: str
    category: str
    fix_description: str


class PRAutomator:
    """Automate PR operations including creation, review, and merge.

    Creates fix PRs, runs automated reviews, and manages
    the merge workflow.
    """

    def __init__(self) -> None:
        self._prs: Dict[str, PR] = {}
        self._counter = 0

    def create_fix_pr(self, diagnosis: Diagnosis, fix_description: str = "") -> PR:
        """Create a PR with a fix.

        Args:
            diagnosis: Diagnosis driving the fix.
            fix_description: Description of the fix.

        Returns:
            Created PR.
        """
        self._counter += 1
        pr = PR(
            pr_id=f"PR-{self._counter}",
            title=f"Fix: {diagnosis.root_cause[:60]}",
            branch=f"fix/{diagnosis.category}-{self._counter}",
            status=PRStatus.OPEN,
            created_at=time.time(),
        )
        self._prs[pr.pr_id] = pr
        return pr

    def review_pr(self, pr_id: str) -> Dict[str, any]:
        """Run automated review on a PR.

        Args:
            pr_id: PR to review.

        Returns:
            Review results dict.
        """
        pr = self._prs.get(pr_id)
        if not pr:
            return {"status": "not_found"}

        issues: List[str] = []
        if len(pr.title) < 10:
            issues.append("Title too short")
        if not pr.files:
            issues.append("No files changed")
        if pr.conflicts:
            issues.append("Has merge conflicts")

        return {
            "pr_id": pr_id,
            "status": "approved" if not issues else "changes_requested",
            "issues": issues,
            "file_count": len(pr.files),
        }

    def merge_pr(self, pr_id: str, checks_required: bool = True) -> bool:
        """Merge a PR if all checks pass.

        Args:
            pr_id: PR to merge.
            checks_required: Whether CI checks must pass.

        Returns:
            True if merged successfully.
        """
        pr = self._prs.get(pr_id)
        if not pr:
            return False
        if checks_required and not pr.checks_passing:
            return False
        if pr.conflicts:
            return False
        pr.status = PRStatus.MERGED
        return True

    def get_pr_status(self, pr_id: str) -> Optional[PR]:
        """Get PR status.

        Args:
            pr_id: PR identifier.

        Returns:
            PR if found, else None.
        """
        return self._prs.get(pr_id)

    def update_pr(self, pr_id: str, **kwargs: any) -> bool:
        """Update PR attributes."""
        pr = self._prs.get(pr_id)
        if not pr:
            return False
        for key, value in kwargs.items():
            if hasattr(pr, key):
                setattr(pr, key, value)
        return True
