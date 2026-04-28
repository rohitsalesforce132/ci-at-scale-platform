# GitHub Copilot Instructions

## Project Overview
CI at Scale Platform — automated CI health management for 100+ engineer teams. Based on Mendral/PostHog case study: diagnosing CI failures, quarantining flaky tests, and opening PRs with fixes.

## Architecture
```
src/
├── log_ingestion/       # Billion-line log processing, indexing, correlation
├── flake_detection/     # Flaky test detection, quarantine, failure signatures
├── failure_diagnosis/   # AI-powered root cause analysis, fix suggestions
├── ci_orchestrator/     # Pipeline management, job scheduling, commit analysis
├── notification_routing/# Smart routing to responsible engineers
├── test_analytics/      # Test health scoring, prioritization, deduplication
├── monorepo/            # Dependency graphs, build optimization, merge queues
├── reliability/         # SLA tracking, capacity planning, incident management
├── pr_automation/       # Auto-fix PRs, conflict resolution, reviewer assignment
└── continuous_analysis/ # Health monitoring, trend analysis, pattern detection
```

## Conventions
- Pure Python stdlib only — zero external dependencies
- Type hints on all public methods
- Dataclasses for structured data, Enums for vocabularies
- Tests in tests/test_all.py using pytest

## Running
```bash
pytest tests/test_all.py -v  # Run all 163 tests
```
