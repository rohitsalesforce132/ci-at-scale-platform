"""MonorepoAnalyzer — Analyze monorepo structure and dependencies."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple


@dataclass
class PackageInfo:
    """Information about a package in the monorepo."""
    name: str
    path: str
    dependencies: Set[str] = field(default_factory=set)
    dependents: Set[str] = field(default_factory=set)
    files: List[str] = field(default_factory=list)


@dataclass
class CommitChange:
    """Changes in a commit."""
    sha: str
    files: List[str] = field(default_factory=list)
    author: str = ""


@dataclass
class ChangeImpact:
    """Impact analysis of a change."""
    commit: str
    affected_packages: List[str]
    total_packages: int
    impact_ratio: float


class MonorepoAnalyzer:
    """Analyze monorepo structure, dependencies, and change impact.

    Builds a dependency graph and determines which packages
    are affected by code changes.
    """

    def __init__(self) -> None:
        self._packages: Dict[str, PackageInfo] = {}
        self._file_to_package: Dict[str, str] = {}  # file_path -> package_name

    def analyze_structure(self, files: List[str]) -> Dict[str, PackageInfo]:
        """Analyze monorepo structure from file list.

        Args:
            files: All files in the monorepo.

        Returns:
            Dict of package name -> PackageInfo.
        """
        for fp in files:
            parts = fp.split("/")
            if len(parts) >= 2:
                pkg_name = parts[1] if parts[0] in ("packages", "libs", "apps") else parts[0]
            else:
                pkg_name = "root"

            if pkg_name not in self._packages:
                self._packages[pkg_name] = PackageInfo(name=pkg_name, path=pkg_name)
            self._packages[pkg_name].files.append(fp)
            self._file_to_package[fp] = pkg_name

        return dict(self._packages)

    def detect_affected_packages(self, commit: CommitChange) -> List[str]:
        """Detect which packages are affected by a commit.

        Args:
            commit: The commit changes.

        Returns:
            List of affected package names.
        """
        affected: Set[str] = set()
        for fp in commit.files:
            pkg = self._file_to_package.get(fp)
            if pkg:
                affected.add(pkg)
                # Add dependents
                pkg_info = self._packages.get(pkg)
                if pkg_info:
                    affected.update(pkg_info.dependents)
        return list(affected)

    def compute_dependency_graph(self) -> Dict[str, Set[str]]:
        """Compute the dependency graph.

        Returns:
            Dict mapping package -> set of dependencies.
        """
        return {name: pkg.dependencies for name, pkg in self._packages.items()}

    def get_change_impact(self, commit: CommitChange) -> ChangeImpact:
        """Get change impact analysis for a commit.

        Args:
            commit: The commit.

        Returns:
            ChangeImpact with affected package info.
        """
        affected = self.detect_affected_packages(commit)
        total = len(self._packages) if self._packages else 1
        return ChangeImpact(
            commit=commit.sha,
            affected_packages=affected,
            total_packages=total,
            impact_ratio=len(affected) / total,
        )

    def add_package(self, package: PackageInfo) -> None:
        """Register a package."""
        self._packages[package.name] = package
        for fp in package.files:
            self._file_to_package[fp] = package.name

    def add_dependency(self, package: str, depends_on: str) -> None:
        """Add a dependency relationship."""
        if package in self._packages and depends_on in self._packages:
            self._packages[package].dependencies.add(depends_on)
            self._packages[depends_on].dependents.add(package)
