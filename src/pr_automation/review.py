"""ReviewAssigner — Assign PR reviewers intelligently."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set


@dataclass
class Reviewer:
    """A potential PR reviewer."""
    name: str
    expertise: Set[str] = field(default_factory=set)
    active_reviews: int = 0
    max_reviews: int = 5


@dataclass
class Assignment:
    """A review assignment."""
    pr_id: str
    reviewers: List[str]
    reason: str


class ReviewAssigner:
    """Assign PR reviewers based on expertise and load balancing.

    Matches reviewers to PRs based on file expertise,
    current review load, and assignment history.
    """

    def __init__(self) -> None:
        self._reviewers: Dict[str, Reviewer] = {}
        self._assignments: Dict[str, Assignment] = {}

    def assign(self, pr_id: str, files: Optional[List[str]] = None) -> Assignment:
        """Assign reviewers to a PR.

        Args:
            pr_id: PR identifier.
            files: Files changed in the PR.

        Returns:
            Assignment with selected reviewers.
        """
        files = files or []
        candidates = self._find_reviewers(files)

        # Sort by load (fewest reviews first)
        candidates.sort(key=lambda r: r.active_reviews)

        # Assign up to 2 reviewers
        assigned = [r.name for r in candidates[:2]]

        # Update load
        for name in assigned:
            if name in self._reviewers:
                self._reviewers[name].active_reviews += 1

        assignment = Assignment(
            pr_id=pr_id,
            reviewers=assigned,
            reason=f"Matched by expertise on {len(files)} files",
        )
        self._assignments[pr_id] = assignment
        return assignment

    def find_reviewers(self, file_paths: List[str]) -> List[str]:
        """Find suitable reviewers for given files.

        Args:
            file_paths: Files to find reviewers for.

        Returns:
            List of reviewer names.
        """
        reviewers = self._find_reviewers(file_paths)
        return [r.name for r in reviewers]

    def get_review_load(self, reviewer: str) -> int:
        """Get current review load for a reviewer.

        Args:
            reviewer: Reviewer name.

        Returns:
            Number of active reviews.
        """
        r = self._reviewers.get(reviewer)
        return r.active_reviews if r else 0

    def balance_assignment(self, pr_ids: List[str]) -> Dict[str, List[str]]:
        """Balance review assignments across multiple PRs.

        Args:
            pr_ids: PRs to assign.

        Returns:
            Dict mapping pr_id -> reviewer names.
        """
        result: Dict[str, List[str]] = {}
        for pr_id in pr_ids:
            assignment = self.assign(pr_id)
            result[pr_id] = assignment.reviewers
        return result

    def add_reviewer(self, reviewer: Reviewer) -> None:
        """Register a reviewer."""
        self._reviewers[reviewer.name] = reviewer

    def complete_review(self, pr_id: str, reviewer: str) -> bool:
        """Mark a review as complete."""
        r = self._reviewers.get(reviewer)
        if r:
            r.active_reviews = max(0, r.active_reviews - 1)
            return True
        return False

    def _find_reviewers(self, files: List[str]) -> List[Reviewer]:
        """Find matching reviewers by file expertise."""
        if not files:
            return list(self._reviewers.values())

        scored: List[tuple] = []
        for reviewer in self._reviewers.values():
            if reviewer.active_reviews >= reviewer.max_reviews:
                continue
            score = sum(1 for f in files for exp in reviewer.expertise if exp in f)
            scored.append((-score, reviewer.active_reviews, reviewer))

        scored.sort()
        return [r for _, _, r in scored]

    def get_assignment(self, pr_id: str) -> Optional[Assignment]:
        """Get assignment for a PR."""
        return self._assignments.get(pr_id)
