"""FixSuggester — Suggest code fixes for diagnosed failures."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .diagnostician import Diagnosis


@dataclass
class CodePatch:
    """A suggested code patch."""
    file_path: str
    description: str
    old_code: str
    new_code: str
    confidence: float


@dataclass
class PRInfo:
    """Info about an auto-created PR."""
    pr_number: int
    title: str
    branch: str
    url: str


class FixSuggester:
    """Suggest code fixes for diagnosed failures.

    Generates patches based on failure categories and can
    automatically open PRs for approved fixes.
    """

    _FIX_TEMPLATES: Dict[str, Dict[str, str]] = {
        "timeout": {
            "old": "# operation without timeout\nresult = do_operation()",
            "new": "# operation with timeout\nresult = do_operation(timeout=300)",
        },
        "dependency": {
            "old": "import missing_module",
            "new": "try:\n    import missing_module\nexcept ImportError:\n    from alternative import replacement",
        },
        "test": {
            "old": "assert result == expected",
            "new": "assert result == expected, f'Expected {expected}, got {result}'",
        },
        "resource": {
            "old": "data = load_all()",
            "new": "data = load_all(chunk_size=1024)",
        },
    }

    def __init__(self) -> None:
        self._suggestions: List[CodePatch] = []
        self._pr_counter = 1000

    def suggest(self, diagnosis: Diagnosis) -> Optional[CodePatch]:
        """Suggest a fix for a diagnosis.

        Args:
            diagnosis: The diagnosis.

        Returns:
            CodePatch suggestion, or None if no fix available.
        """
        template = self._FIX_TEMPLATES.get(diagnosis.category)
        if not template:
            return None

        patch = CodePatch(
            file_path=f"fix_{diagnosis.category}",
            description=diagnosis.suggested_fix,
            old_code=template["old"],
            new_code=template["new"],
            confidence=diagnosis.confidence * 0.8,
        )
        self._suggestions.append(patch)
        return patch

    def generate_patch(self, diagnosis: Diagnosis) -> Optional[CodePatch]:
        """Generate a code patch for the diagnosis.

        Args:
            diagnosis: The diagnosis.

        Returns:
            Generated patch, or None.
        """
        return self.suggest(diagnosis)

    def validate_patch(self, patch: CodePatch) -> bool:
        """Validate a generated patch.

        Args:
            patch: The patch to validate.

        Returns:
            True if patch looks valid.
        """
        if not patch.new_code or not patch.old_code:
            return False
        if patch.confidence < 0.3:
            return False
        if len(patch.new_code) < 5:
            return False
        return True

    def open_pr(self, diagnosis: Diagnosis, patch: CodePatch) -> PRInfo:
        """Simulate opening a PR with the fix.

        Args:
            diagnosis: The diagnosis.
            patch: The code patch.

        Returns:
            PRInfo with PR details.
        """
        self._pr_counter += 1
        return PRInfo(
            pr_number=self._pr_counter,
            title=f"Fix: {diagnosis.root_cause[:60]}",
            branch=f"fix/{diagnosis.category}-{self._pr_counter}",
            url=f"https://github.com/org/repo/pull/{self._pr_counter}",
        )

    def get_suggestions(self) -> List[CodePatch]:
        """Get all generated suggestions."""
        return list(self._suggestions)
