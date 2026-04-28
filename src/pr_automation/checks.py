"""CheckRunner — Run PR checks and gates."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional


@dataclass
class CheckConfig:
    """Configuration for a PR check."""
    name: str
    required: bool = True
    timeout: int = 300
    config: Dict[str, str] = field(default_factory=dict)


@dataclass
class CheckResult:
    """Result of a PR check."""
    name: str
    passed: bool
    message: str
    duration: float = 0.0


class CheckRunner:
    """Run configurable PR checks and gates.

    Supports defining custom checks, running them,
    and bypassing checks when needed.
    """

    def __init__(self) -> None:
        self._checks: Dict[str, CheckConfig] = {}
        self._results: Dict[str, List[CheckResult]] = {}  # pr_id -> results
        self._bypassed: Dict[str, str] = {}  # check_name -> reason

    def run_checks(self, pr_id: str) -> List[CheckResult]:
        """Run all defined checks for a PR.

        Args:
            pr_id: PR identifier.

        Returns:
            List of CheckResult for each check.
        """
        results: List[CheckResult] = []
        for name, config in self._checks.items():
            if name in self._bypassed:
                results.append(CheckResult(
                    name=name, passed=True,
                    message=f"Bypassed: {self._bypassed[name]}",
                ))
                continue

            # Simulate check execution
            passed = self._execute_check(config)
            results.append(CheckResult(
                name=name,
                passed=passed,
                message="Check passed" if passed else "Check failed",
                duration=1.0,
            ))

        self._results[pr_id] = results
        return results

    def get_check_results(self, pr_id: str) -> List[CheckResult]:
        """Get check results for a PR.

        Args:
            pr_id: PR identifier.

        Returns:
            List of CheckResult.
        """
        return self._results.get(pr_id, [])

    def define_check(self, name: str, config: Optional[CheckConfig] = None) -> CheckConfig:
        """Define a new check.

        Args:
            name: Check name.
            config: Optional configuration.

        Returns:
            Created CheckConfig.
        """
        check = config or CheckConfig(name=name)
        self._checks[name] = check
        return check

    def bypass_check(self, name: str, reason: str) -> bool:
        """Bypass a check with a reason.

        Args:
            name: Check to bypass.
            reason: Reason for bypass.

        Returns:
            True if check exists and was bypassed.
        """
        if name not in self._checks:
            return False
        self._bypassed[name] = reason
        return True

    def all_passed(self, pr_id: str) -> bool:
        """Check if all required checks passed."""
        results = self._results.get(pr_id, [])
        if not results:
            return False
        return all(r.passed for r in results)

    def _execute_check(self, config: CheckConfig) -> bool:
        """Simulate check execution. Always passes in simulation."""
        return True

    def get_checks(self) -> Dict[str, CheckConfig]:
        """Get all defined checks."""
        return dict(self._checks)
