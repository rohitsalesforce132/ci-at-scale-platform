"""CommitBlamer — Trace failures to commit authors."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class BlameInfo:
    """Blame information for a file."""
    file_path: str
    author: str
    commit_sha: str
    last_modified: float = 0.0


@dataclass
class ExpertInfo:
    """Expert for a code area."""
    area: str
    expert: str
    commit_count: int
    last_active: float = 0.0


class CommitBlamer:
    """Trace failures to commit authors and find experts.

    Uses git blame-style logic to identify who last touched
    failing code and who are the domain experts.
    """

    def __init__(self) -> None:
        self._blame_data: Dict[str, BlameInfo] = {}
        self._commits: Dict[str, List[BlameInfo]] = {}  # sha -> files
        self._experts: Dict[str, List[ExpertInfo]] = {}  # area -> experts

    def blame(self, failure_files: List[str], commits: Optional[List[str]] = None) -> Optional[BlameInfo]:
        """Find who to blame for files involved in a failure.

        Args:
            failure_files: Files involved in the failure.
            commits: Optional commit SHAs to check.

        Returns:
            BlameInfo for the most recently modified file.
        """
        candidates: List[BlameInfo] = []
        for fp in failure_files:
            if fp in self._blame_data:
                candidates.append(self._blame_data[fp])

        if commits:
            for sha in commits:
                for info in self._commits.get(sha, []):
                    candidates.append(info)

        if not candidates:
            return None
        return max(candidates, key=lambda x: x.last_modified)

    def get_recent_commits(self, file_path: str) -> List[BlameInfo]:
        """Get recent commits for a file path.

        Args:
            file_path: File to check.

        Returns:
            Recent blame info.
        """
        results: List[BlameInfo] = []
        for sha, infos in self._commits.items():
            for info in infos:
                if info.file_path == file_path:
                    results.append(info)
        return sorted(results, key=lambda x: -x.last_modified)

    def find_expert(self, area: str) -> Optional[str]:
        """Find the expert for a code area.

        Args:
            area: Code area/module name.

        Returns:
            Expert identifier or None.
        """
        experts = self._experts.get(area, [])
        if not experts:
            return None
        return max(experts, key=lambda x: x.commit_count).expert

    def compute_blame_confidence(self, failure_files: List[str], commit_sha: str) -> float:
        """Compute confidence that a commit caused the failure.

        Args:
            failure_files: Files in the failure.
            commit_sha: Suspected commit.

        Returns:
            Confidence score (0.0 to 1.0).
        """
        commit_files = self._commits.get(commit_sha, [])
        if not commit_files or not failure_files:
            return 0.0

        commit_paths = {info.file_path for info in commit_files}
        overlap = len(set(failure_files) & commit_paths)
        total = len(set(failure_files) | commit_paths)
        return overlap / total if total else 0.0

    def add_blame_info(self, file_path: str, info: BlameInfo) -> None:
        """Register blame info for a file."""
        self._blame_data[file_path] = info

    def add_commit_files(self, sha: str, files: List[BlameInfo]) -> None:
        """Register files changed in a commit."""
        self._commits[sha] = files

    def add_expert(self, area: str, expert: ExpertInfo) -> None:
        """Register an expert for a code area."""
        if area not in self._experts:
            self._experts[area] = []
        self._experts[area].append(expert)
