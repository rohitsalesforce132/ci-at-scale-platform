"""BuildOptimizer — Optimize monorepo build execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from .analyzer import CommitChange


@dataclass
class BuildTask:
    """A build task for a package."""
    package: str
    estimated_duration: float = 60.0
    dependencies: Set[str] = field(default_factory=set)
    status: str = "pending"


@dataclass
class BuildPlan:
    """An optimized build plan."""
    stages: List[List[str]]  # packages that can build in parallel per stage
    total_duration: float
    parallelism_used: int


class BuildOptimizer:
    """Optimize monorepo build execution.

    Detects affected builds, computes optimal build order
    respecting dependencies, and maximizes parallelism.
    """

    def __init__(self) -> None:
        self._packages: Dict[str, BuildTask] = {}
        self._dependencies: Dict[str, Set[str]] = {}

    def detect_affected_builds(self, commit: CommitChange) -> List[str]:
        """Detect which packages need rebuilding.

        Args:
            commit: The commit changes.

        Returns:
            List of packages that need building.
        """
        affected: Set[str] = set()
        for fp in commit.files:
            for pkg_name, task in self._packages.items():
                if any(fp.startswith(prefix) for prefix in [pkg_name, f"packages/{pkg_name}", f"libs/{pkg_name}"]):
                    affected.add(pkg_name)
                    # Also add dependents
                    self._add_dependents(pkg_name, affected)
        return list(affected)

    def compute_build_order(self, builds: List[str]) -> BuildPlan:
        """Compute optimal build order respecting dependencies.

        Args:
            builds: Packages to build.

        Returns:
            BuildPlan with parallel stages.
        """
        remaining: Set[str] = set(builds)
        stages: List[List[str]] = []
        built: Set[str] = set()
        total_duration = 0.0

        while remaining:
            # Find packages with all deps satisfied
            ready = []
            for pkg in sorted(remaining):
                deps = self._dependencies.get(pkg, set())
                if deps <= built:
                    ready.append(pkg)

            if not ready:
                # Circular dependency fallback
                ready = [min(remaining)]

            stages.append(ready)
            stage_duration = max(
                self._packages.get(p, BuildTask(package=p)).estimated_duration
                for p in ready
            ) if ready else 0
            total_duration += stage_duration
            built.update(ready)
            remaining -= set(ready)

        max_parallel = max(len(s) for s in stages) if stages else 1
        return BuildPlan(
            stages=stages,
            total_duration=total_duration,
            parallelism_used=max_parallel,
        )

    def parallelize(self, builds: List[str], workers: int = 4) -> BuildPlan:
        """Parallelize builds across workers.

        Args:
            builds: Packages to build.
            workers: Number of parallel workers.

        Returns:
            Optimized BuildPlan.
        """
        plan = self.compute_build_order(builds)
        # Limit parallelism to workers
        capped_stages = []
        for stage in plan.stages:
            for i in range(0, len(stage), workers):
                capped_stages.append(stage[i:i + workers])
        plan.stages = capped_stages
        plan.parallelism_used = min(plan.parallelism_used, workers)
        return plan

    def estimate_build_time(self, builds: List[str]) -> float:
        """Estimate total build time.

        Args:
            builds: Packages to build.

        Returns:
            Estimated time in seconds.
        """
        if not builds:
            return 0.0
        plan = self.compute_build_order(builds)
        return plan.total_duration

    def add_package(self, name: str, task: BuildTask) -> None:
        """Register a build task."""
        self._packages[name] = task
        self._dependencies[name] = task.dependencies

    def _add_dependents(self, package: str, affected: Set[str]) -> None:
        for name, task in self._packages.items():
            if package in task.dependencies and name not in affected:
                affected.add(name)
                self._add_dependents(name, affected)
