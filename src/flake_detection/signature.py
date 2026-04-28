"""FailureSignature — Create and match failure signatures."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set


@dataclass
class Signature:
    """A failure signature for matching and clustering."""
    id: str
    normalized: str
    keywords: Set[str] = field(default_factory=set)
    error_type: Optional[str] = None
    family: str = ""
    source: str = ""


@dataclass
class SignatureCluster:
    """A cluster of similar signatures."""
    cluster_id: str
    signatures: List[Signature]
    common_keywords: Set[str]
    size: int


class FailureSignature:
    """Create and match failure signatures for deduplication.

    Normalizes error messages into canonical signatures that can
    be compared, clustered, and tracked over time.
    """

    def __init__(self) -> None:
        self._signatures: Dict[str, Signature] = {}
        self._next_id = 0

    def create_signature(self, error_log: str) -> Signature:
        """Create a normalized signature from an error log.

        Args:
            error_log: Raw error log text.

        Returns:
            Normalized Signature.
        """
        normalized = self._normalize(error_log)
        keywords = self._extract_keywords(error_log)
        error_type = self._extract_error_type(error_log)
        family = self._classify_family(error_log)

        sig = Signature(
            id=f"sig_{self._next_id}",
            normalized=normalized,
            keywords=keywords,
            error_type=error_type,
            family=family,
            source=error_log,
        )
        self._next_id += 1
        self._signatures[sig.id] = sig
        return sig

    def match_signature(self, sig1: Signature, sig2: Signature) -> float:
        """Compute similarity between two signatures.

        Args:
            sig1: First signature.
            sig2: Second signature.

        Returns:
            Similarity score (0.0 to 1.0).
        """
        if sig1.normalized == sig2.normalized:
            return 1.0

        # Keyword overlap
        if not sig1.keywords or not sig2.keywords:
            return 0.0
        overlap = len(sig1.keywords & sig2.keywords)
        union = len(sig1.keywords | sig2.keywords)
        kw_score = overlap / union if union else 0.0

        # Error type match bonus
        type_bonus = 0.2 if sig1.error_type and sig1.error_type == sig2.error_type else 0.0

        # Family match bonus
        family_bonus = 0.1 if sig1.family and sig1.family == sig2.family else 0.0

        return min(1.0, kw_score + type_bonus + family_bonus)

    def cluster_signatures(self, signatures: List[Signature], threshold: float = 0.6) -> List[SignatureCluster]:
        """Cluster similar signatures together.

        Args:
            signatures: Signatures to cluster.
            threshold: Minimum similarity to group.

        Returns:
            List of signature clusters.
        """
        clusters: List[SignatureCluster] = []
        assigned: Set[str] = set()

        for sig in signatures:
            if sig.id in assigned:
                continue
            cluster_sigs = [sig]
            assigned.add(sig.id)

            for other in signatures:
                if other.id in assigned:
                    continue
                if self.match_signature(sig, other) >= threshold:
                    cluster_sigs.append(other)
                    assigned.add(other.id)

            all_keywords: Set[str] = set()
            for s in cluster_sigs:
                all_keywords |= s.keywords

            clusters.append(SignatureCluster(
                cluster_id=f"cluster_{len(clusters)}",
                signatures=cluster_sigs,
                common_keywords=all_keywords,
                size=len(cluster_sigs),
            ))

        return clusters

    def get_signature_family(self, sig: Signature) -> str:
        """Get the family classification for a signature.

        Args:
            sig: The signature.

        Returns:
            Family name.
        """
        return sig.family

    # -- helpers --

    def _normalize(self, text: str) -> str:
        result = text.lower().strip()
        result = re.sub(r'\d+', 'N', result)
        result = re.sub(r'/[\w/.-]+', 'PATH', result)
        result = re.sub(r'0x[0-9a-f]+', 'HEX', result)
        result = re.sub(r'\s+', ' ', result)
        return result[:300]

    def _extract_keywords(self, text: str) -> Set[str]:
        stop = {"the", "and", "for", "was", "has", "with", "this", "that", "from", "not", "are", "but", "had", "its", "can"}
        words: Set[str] = set()
        for w in text.lower().split():
            cleaned = "".join(c for c in w if c.isalnum())
            if len(cleaned) >= 3 and cleaned not in stop:
                words.add(cleaned)
        return words

    def _extract_error_type(self, text: str) -> Optional[str]:
        match = re.search(r'(\w+Error|\w+Exception)', text)
        return match.group(1) if match else None

    def _classify_family(self, text: str) -> str:
        lower = text.lower()
        if "timeout" in lower:
            return "timeout"
        if "connection" in lower or "network" in lower:
            return "network"
        if "import" in lower or "module" in lower:
            return "import"
        if "assertion" in lower or "assert" in lower:
            return "assertion"
        if "permission" in lower or "access" in lower:
            return "permission"
        if "memory" in lower or "oom" in lower:
            return "resource"
        return "unknown"
