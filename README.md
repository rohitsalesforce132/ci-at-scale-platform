# CI-at-Scale Platform

> Production-grade CI health management platform inspired by the Mendral/PostHog case study: *"What CI Actually Looks Like at a 100-Person Team"*

## PostHog CI at a Glance

| Metric | Value |
|--------|-------|
| CI jobs/week | 575,894 |
| Log lines | 1.18 billion |
| Test executions | 33.4M |
| Unique tests | 22,477 |
| Pass rate | 99.98% |
| Commits to main/day | 65 |
| PRs tested/day | 105 |
| Parallel jobs/commit | 221 |
| Compute on failures | 14% |
| Re-runs | 3.5% |

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    CI-at-Scale Platform                         │
├─────────────────┬───────────────────┬──────────────────────────┤
│  Log Ingestion  │ Flake Detection   │  Failure Diagnosis       │
│  (billion-line) │ (quarantine)      │  (AI-powered)            │
├─────────────────┼───────────────────┼──────────────────────────┤
│  CI Orchestrator│ Notification      │  Test Analytics          │
│  (pipelines)    │ Routing           │  (intelligence)          │
├─────────────────┼───────────────────┼──────────────────────────┤
│  Monorepo       │ Reliability       │  PR Automation           │
│  (builds/queue) │ (SLAs/incidents)  │  (merge/conflicts)       │
├─────────────────┴───────────────────┴──────────────────────────┤
│              Continuous Analysis (health/trends/patterns)       │
└─────────────────────────────────────────────────────────────────┘
```

## 10 Subsystems

1. **Log Ingestion** — Ingest, parse, index, and correlate CI logs at billion-line scale
2. **Flake Detection** — Detect flaky tests, quarantine, correlate with code changes, signature matching
3. **Failure Diagnosis** — AI-powered diagnosis, root cause analysis, fix suggestion, PR automation
4. **CI Orchestrator** — Pipeline management, job scheduling, run tracking, commit impact analysis
5. **Notification Routing** — Smart routing, commit blaming, Slack integration, escalation policies
6. **Test Analytics** — Health scoring, prioritization, coverage tracking, test deduplication
7. **Monorepo** — Dependency graphs, build optimization, merge queues, branch management
8. **Reliability** — SLA tracking, reliability scoring, incident management, capacity planning
9. **PR Automation** — Auto fix PRs, check gates, conflict resolution, reviewer assignment
10. **Continuous Analysis** — Health monitoring, trend analysis, pattern detection, feedback loops

## Quick Start

```bash
# Run all tests
pytest tests/test_all.py -v

# Run a specific subsystem's tests
pytest tests/test_all.py -k "TestLogIngester" -v
```

## Design Principles

- **Pure Python stdlib** — Zero external dependencies
- **163 deterministic tests** — All passing, no flakiness
- **Type hints everywhere** — Full type annotations on public APIs
- **Dataclasses** — Structured data throughout
- **Composable** — Each subsystem works independently or together

## Project Structure

```
ci-at-scale-platform/
├── src/
│   ├── log_ingestion/        # Log processing at billion-line scale
│   ├── flake_detection/      # Flaky test detection & quarantine
│   ├── failure_diagnosis/    # AI-powered failure diagnosis
│   ├── ci_orchestrator/      # Pipeline orchestration
│   ├── notification_routing/ # Smart notification routing
│   ├── test_analytics/       # Test intelligence & analytics
│   ├── monorepo/             # Monorepo CI management
│   ├── reliability/          # CI reliability & SLA management
│   ├── pr_automation/        # Automated PR management
│   └── continuous_analysis/  # Continuous CI health analysis
├── tests/
│   └── test_all.py           # 163 tests
├── README.md
└── STAR.md
```

## Context

This platform is based on the Mendral blog post analyzing PostHog's CI at scale. PostHog is a ~100 person team running a large public monorepo with massive CI volume. Mendral is a GitHub App that ingests logs, detects/traces flakes, opens PRs with fixes, acts as a Slack team member, and does continuous analysis.

The key challenges at 100+ engineer scale:
- **Flaky tests** destroy trust in CI and waste 14% of compute
- **Log ingestion** at 1.18B lines/week requires efficient indexing
- **Failure routing** must be smart — not everyone needs every alert
- **Failure diagnosis** must be fast — engineers can't spend hours debugging CI
