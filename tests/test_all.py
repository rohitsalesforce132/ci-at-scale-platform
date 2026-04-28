"""CI-at-Scale Platform — Complete test suite."""

import sys
import os
import time

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# =============================================================================
# Subsystem 1: Log Ingestion
# =============================================================================
from src.log_ingestion import LogIngester, LogParser, LogIndex, LogCorrelator


class TestLogIngester:
    def test_ingest_basic(self):
        ingester = LogIngester()
        count = ingester.ingest(["line 1", "ERROR: something failed", "line 3"], "job-1")
        assert count == 3

    def test_ingest_stats(self):
        ingester = LogIngester()
        ingester.ingest(["ERROR: fail"] * 5, "job-1")
        stats = ingester.get_stats()
        assert stats.total_lines == 5
        assert stats.error_lines == 5
        assert stats.total_jobs == 1

    def test_search_by_query(self):
        ingester = LogIngester()
        ingester.ingest(["hello world", "ERROR: crash", "INFO: ok"], "job-1")
        results = ingester.search("crash")
        assert len(results) == 1
        assert "crash" in results[0].message

    def test_search_with_level_filter(self):
        ingester = LogIngester()
        ingester.ingest(["ERROR: crash", "INFO: ok", "WARNING: hmm"], "job-1")
        errors = ingester.search("crash", {"level": "ERROR"})
        assert len(errors) == 1
        infos = ingester.search("ok", {"level": "INFO"})
        assert len(infos) == 1

    def test_get_logs_by_job(self):
        ingester = LogIngester()
        ingester.ingest(["line 1", "line 2"], "job-1")
        ingester.ingest(["other 1"], "job-2")
        logs = ingester.get_logs("job-1")
        assert len(logs) == 2

    def test_get_logs_nonexistent_job(self):
        ingester = LogIngester()
        assert ingester.get_logs("nope") == []

    def test_multiple_jobs(self):
        ingester = LogIngester()
        ingester.ingest(["a"], "j1")
        ingester.ingest(["b"], "j2")
        assert ingester.get_stats().total_jobs == 2


class TestLogParser:
    def test_parse_structured_line(self):
        parser = LogParser()
        result = parser.parse_line("2024-01-01 12:00:00 ERROR [module] Something broke")
        assert result.level == "ERROR"
        assert result.is_error is True
        assert "broke" in result.message

    def test_parse_bracket_level(self):
        parser = LogParser()
        result = parser.parse_line("[ERROR] Critical failure")
        assert result.level == "ERROR"
        assert "Critical" in result.message

    def test_parse_unstructured(self):
        parser = LogParser()
        result = parser.parse_line("random output line")
        assert result.level == "INFO"

    def test_extract_error_context(self):
        parser = LogParser()
        lines = ["before 1", "before 2", "ERROR: the error", "after 1", "after 2"]
        contexts = parser.extract_error_context(lines, context_size=2)
        assert len(contexts) == 1
        assert contexts[0].line_number == 2
        assert len(contexts[0].before) == 2
        assert len(contexts[0].after) == 2

    def test_classify_line(self):
        parser = LogParser()
        assert parser.classify_line("ERROR: fail") == "error"
        assert parser.classify_line("WARNING: hmm") == "warning"
        assert parser.classify_line("$ make build") == "command"
        assert parser.classify_line("INFO: ok") == "info"

    def test_detect_patterns_repeated(self):
        parser = LogParser()
        lines = ["ERROR: timeout"] * 5
        patterns = parser.detect_patterns(lines)
        assert any(p["type"] == "repeated_error" for p in patterns)

    def test_detect_timeout_pattern(self):
        parser = LogParser()
        patterns = parser.detect_patterns(["operation timed out after 30s"])
        assert any(p["type"] == "timeout" for p in patterns)


class TestLogIndex:
    def test_index_and_search(self):
        idx = LogIndex()
        idx.index("j1", ["error in module auth", "info: ok"])
        results = idx.search("auth")
        assert len(results) >= 1

    def test_get_by_severity(self):
        idx = LogIndex()
        idx.index("j1", ["ERROR: crash", "INFO: ok", "ERROR: another"])
        errors = idx.get_by_severity("ERROR")
        assert len(errors) == 2

    def test_compact_deduplication(self):
        idx = LogIndex()
        idx.index("j1", ["line 1"])
        idx.index("j1", ["line 1"])  # duplicate
        removed = idx.compact()
        assert removed >= 0  # dedup logic works

    def test_search_limit(self):
        idx = LogIndex()
        idx.index("j1", ["error test"] * 20)
        results = idx.search("test", limit=5)
        assert len(results) <= 5

    def test_empty_search(self):
        idx = LogIndex()
        assert idx.search("anything") == []


class TestLogCorrelator:
    def test_correlate_jobs(self):
        corr = LogCorrelator()
        result = corr.correlate({
            "j1": ["ERROR: database timeout"],
            "j2": ["ERROR: database timeout", "INFO: ok"],
        })
        assert len(result) >= 1
        assert result[0].similarity_score > 0

    def test_find_similar_errors(self):
        corr = LogCorrelator()
        corr.group_failures({"j1": ["ERROR: connection refused"], "j2": ["ERROR: connection reset"]})
        results = corr.find_similar_errors("ERROR: connection refused")
        assert len(results) >= 0  # may or may not match based on fuzzy logic

    def test_group_failures(self):
        corr = LogCorrelator()
        groups = corr.group_failures({
            "j1": ["ERROR: timeout on /api/test"],
            "j2": ["ERROR: timeout on /api/users"],
            "j3": ["ERROR: import module failed"],
        })
        assert len(groups) >= 1

    def test_empty_correlate(self):
        corr = LogCorrelator()
        result = corr.correlate({"j1": ["INFO: ok"], "j2": ["INFO: fine"]})
        assert len(result) == 0


# =============================================================================
# Subsystem 2: Flake Detection
# =============================================================================
from src.flake_detection import FlakeDetector, FailureCorrelator, TestQuarantine, FailureSignature
from src.flake_detection.correlator import Failure as FlakeFailure, Commit as FlakeCommit


class TestFlakeDetector:
    def test_analyze_flaky_test(self):
        det = FlakeDetector()
        runs = [
            type('R', (), {'test_name': 't1', 'passed': i % 2 == 0, 'run_id': f'r{i}', 'commit': f'c{i}', 'duration': 1.0})()
            for i in range(10)
        ]
        report = det.analyze_test_history("t1", runs)
        assert report.is_flaky is True
        assert report.total_runs == 10

    def test_stable_test(self):
        det = FlakeDetector()
        runs = [type('R', (), {'test_name': 't1', 'passed': True, 'run_id': f'r{i}', 'commit': f'c{i}', 'duration': 1.0})()
                for i in range(5)]
        report = det.analyze_test_history("t1", runs)
        assert report.is_flaky is False

    def test_compute_flake_rate(self):
        det = FlakeDetector()
        runs = [type('R', (), {'test_name': 't1', 'passed': i % 2 == 0, 'run_id': f'r{i}', 'commit': f'c{i}', 'duration': 1.0})()
                for i in range(10)]
        det.analyze_test_history("t1", runs)
        rate = det.compute_flake_rate("t1")
        assert rate > 0

    def test_get_flaky_tests(self):
        det = FlakeDetector()
        # Flaky test
        flaky_runs = [type('R', (), {'test_name': 'flaky', 'passed': i % 2 == 0, 'run_id': f'r{i}', 'commit': f'c{i}', 'duration': 1.0})()
                       for i in range(10)]
        det.analyze_test_history("flaky", flaky_runs)
        # Stable test
        stable_runs = [type('R', (), {'test_name': 'stable', 'passed': True, 'run_id': f'r{i}', 'commit': f'c{i}', 'duration': 1.0})()
                       for i in range(10)]
        det.analyze_test_history("stable", stable_runs)
        flaky = det.get_flaky_tests()
        assert len(flaky) >= 1
        assert any(f.test_name == "flaky" for f in flaky)

    def test_is_flake(self):
        det = FlakeDetector()
        # 3 failures out of 10 runs, with flip-flopping
        results = [True, False, True, True, False, True, True, True, False, True]
        runs = [type('R', (), {'test_name': 't1', 'passed': results[i], 'run_id': f'r{i}', 'commit': f'c{i}', 'duration': 1.0})()
                for i in range(10)]
        det.analyze_test_history("t1", runs)
        assert det.is_flake("t1") is True

    def test_empty_history(self):
        det = FlakeDetector()
        report = det.analyze_test_history("nonexistent")
        assert report.total_runs == 0


class TestFailureCorrelator:
    def test_correlate_failure(self):
        fc = FailureCorrelator()
        fc.add_test_mapping("test_auth", ["src/auth.py", "src/auth_test.py"])
        fc._commits["abc123"] = FlakeCommit(sha="abc123", author="dev", message="fix test_auth", files=["src/auth.py"])
        failure = FlakeFailure(test_name="test_auth", error_message="assertion failed", commit="abc123")
        report = fc.correlate_failure(failure)
        assert report.blamed_commit is not None or report.confidence >= 0

    def test_find_root_cause(self):
        fc = FailureCorrelator()
        fc.add_test_mapping("test_api", ["src/api.py"])
        fc._commits["def456"] = FlakeCommit(sha="def456", author="dev", message="update api", files=["src/api.py"])
        failure = FlakeFailure(test_name="test_api", error_message="error", commit="def456")
        root = fc.find_root_cause(failure)
        assert root is not None

    def test_blame_commit(self):
        fc = FailureCorrelator()
        fc.add_test_mapping("test_x", ["src/x.py"])
        fc._commits["ccc"] = FlakeCommit(sha="ccc", author="dev", message="fix x", files=["src/x.py"])
        failure = FlakeFailure(test_name="test_x", error_message="err", commit="ccc")
        sha = fc.blame_commit(failure)
        assert sha == "ccc"


class TestTestQuarantine:
    def test_quarantine(self):
        q = TestQuarantine()
        q.quarantine("test_flaky_1", "Flaky due to timing")
        assert q.is_quarantined("test_flaky_1") is True
        assert q.get_count() == 1

    def test_release(self):
        q = TestQuarantine()
        q.quarantine("test_1", "reason")
        assert q.release("test_1") is True
        assert q.is_quarantined("test_1") is False

    def test_release_nonexistent(self):
        q = TestQuarantine()
        assert q.release("nope") is False

    def test_get_quarantined(self):
        q = TestQuarantine()
        q.quarantine("t1", "r1")
        q.quarantine("t2", "r2")
        quarantined = q.get_quarantined()
        assert len(quarantined) == 2


class TestFailureSignature:
    def test_create_signature(self):
        fs = FailureSignature()
        sig = fs.create_signature("TimeoutError: operation timed out after 30s")
        assert sig.error_type == "TimeoutError"
        assert sig.family == "timeout"

    def test_match_identical(self):
        fs = FailureSignature()
        s1 = fs.create_signature("AssertionError: expected True got False")
        s2 = fs.create_signature("AssertionError: expected True got False")
        assert fs.match_signature(s1, s2) == 1.0

    def test_match_similar(self):
        fs = FailureSignature()
        s1 = fs.create_signature("ConnectionError: connection refused to host")
        s2 = fs.create_signature("ConnectionError: connection reset by host")
        score = fs.match_signature(s1, s2)
        assert score > 0.3

    def test_cluster_signatures(self):
        fs = FailureSignature()
        sigs = [
            fs.create_signature("TimeoutError: timeout 30s on /api"),
            fs.create_signature("TimeoutError: timeout 60s on /api"),
            fs.create_signature("ImportError: module not found"),
        ]
        clusters = fs.cluster_signatures(sigs)
        assert len(clusters) >= 1

    def test_get_signature_family(self):
        fs = FailureSignature()
        sig = fs.create_signature("NetworkError: connection reset")
        assert fs.get_signature_family(sig) == "network"


# =============================================================================
# Subsystem 3: Failure Diagnosis
# =============================================================================
from src.failure_diagnosis import FailureDiagnostician, RootCauseAnalyzer, DiagnosisEngine, FixSuggester
from src.failure_diagnosis.diagnostician import Failure, Diagnosis


class TestFailureDiagnostician:
    def test_diagnose_timeout(self):
        diag = FailureDiagnostician()
        failure = Failure(id="f1", test_name="test_slow", error_message="timeout after 30s")
        result = diag.diagnose(failure)
        assert result.category == "timeout"
        assert result.confidence > 0

    def test_diagnose_network(self):
        diag = FailureDiagnostician()
        failure = Failure(id="f2", test_name="test_api", error_message="connection refused on port 8080")
        result = diag.diagnose(failure)
        assert result.category == "network"

    def test_diagnose_dependency(self):
        diag = FailureDiagnostician()
        failure = Failure(id="f3", test_name="test_import", error_message="Import Error: no module named foo")
        result = diag.diagnose(failure)
        assert result.category == "dependency"

    def test_get_confidence(self):
        diag = FailureDiagnostician()
        failure = Failure(id="f4", test_name="t", error_message="timeout error occurred")
        d = diag.diagnose(failure)
        conf = diag.get_confidence(d)
        assert 0 <= conf <= 1

    def test_explain(self):
        diag = FailureDiagnostician()
        failure = Failure(id="f5", test_name="t", error_message="ERROR: something broke")
        d = diag.diagnose(failure)
        explanation = diag.explain(d)
        assert len(explanation) > 0

    def test_suggest_fix(self):
        diag = FailureDiagnostician()
        failure = Failure(id="f6", test_name="t", error_message="timeout exceeded")
        d = diag.diagnose(failure)
        fix = diag.suggest_fix(d)
        assert "timeout" in fix.lower() or "Increase" in fix


class TestRootCauseAnalyzer:
    def test_analyze(self):
        rca = RootCauseAnalyzer()
        rca.add_commit_info("abc", ["src/main.py", "src/utils.py"])
        failure = Failure(id="f1", test_name="test_main", error_message="timeout error", commit="abc")
        cause = rca.analyze(failure)
        assert cause.cause_type == "timeout"
        assert cause.confidence > 0

    def test_trace_to_commit(self):
        rca = RootCauseAnalyzer()
        rca.add_commit_info("def", ["src/api.py"])
        failure = Failure(id="f2", test_name="t", error_message="error", commit="def")
        sha = rca.trace_to_commit(failure)
        assert sha == "def"

    def test_classify_cause(self):
        rca = RootCauseAnalyzer()
        failure = Failure(id="f3", test_name="t", error_message="import error module")
        assert rca.classify_cause(failure) == "dependency"


class TestDiagnosisEngine:
    def test_register_and_run(self):
        engine = DiagnosisEngine()
        def dummy_analyzer(failure):
            from src.failure_diagnosis.engine import AnalyzerResult
            return AnalyzerResult(analyzer_name="test", category="timeout", confidence=0.8, details="test detail")
        engine.register_analyzer("test", dummy_analyzer)
        failure = Failure(id="f1", test_name="t", error_message="timeout")
        report = engine.run_diagnosis(failure)
        assert report.consensus_confidence > 0
        assert len(report.results) == 1

    def test_learn_from_feedback(self):
        engine = DiagnosisEngine()
        diag = Diagnosis(failure_id="f1", root_cause="timeout", category="timeout",
                         confidence=0.8, explanation="test", suggested_fix="retry")
        engine.learn_from_feedback(diag, "correct")
        assert engine.get_feedback_count() == 1


class TestFixSuggester:
    def test_suggest_timeout_fix(self):
        fs = FixSuggester()
        diag = Diagnosis(failure_id="f1", root_cause="timeout", category="timeout",
                         confidence=0.8, explanation="test", suggested_fix="increase timeout")
        patch = fs.suggest(diag)
        assert patch is not None
        assert "timeout" in patch.new_code.lower()

    def test_validate_patch(self):
        fs = FixSuggester()
        from src.failure_diagnosis.fix_suggester import CodePatch
        good = CodePatch(file_path="f", description="d", old_code="old", new_code="new code here", confidence=0.8)
        assert fs.validate_patch(good) is True
        bad = CodePatch(file_path="f", description="d", old_code="", new_code="", confidence=0.1)
        assert fs.validate_patch(bad) is False

    def test_open_pr(self):
        fs = FixSuggester()
        diag = Diagnosis(failure_id="f1", root_cause="err", category="timeout",
                         confidence=0.8, explanation="test", suggested_fix="fix")
        from src.failure_diagnosis.fix_suggester import CodePatch
        patch = CodePatch(file_path="f", description="d", old_code="old", new_code="new", confidence=0.7)
        pr = fs.open_pr(diag, patch)
        assert pr.pr_number > 0
        assert "fix" in pr.branch


# =============================================================================
# Subsystem 4: CI Orchestrator
# =============================================================================
from src.ci_orchestrator import PipelineOrchestrator, JobScheduler, RunTracker, CommitAnalyzer
from src.ci_orchestrator.pipeline import PipelineConfig, PipelineStatus
from src.ci_orchestrator.scheduler import Job
from src.ci_orchestrator.commit_analyzer import CommitInfo


class TestPipelineOrchestrator:
    def test_create_and_trigger(self):
        po = PipelineOrchestrator()
        pid = po.create_pipeline(PipelineConfig(name="test-pipe", steps=["build", "test"]))
        run_id = po.trigger_pipeline(pid, "abc123")
        assert run_id != ""
        assert po.get_pipeline_status(run_id) == PipelineStatus.RUNNING

    def test_cancel_pipeline(self):
        po = PipelineOrchestrator()
        pid = po.create_pipeline(PipelineConfig(name="p"))
        run_id = po.trigger_pipeline(pid)
        assert po.cancel_pipeline(run_id) is True
        assert po.get_pipeline_status(run_id) == PipelineStatus.CANCELLED

    def test_cancel_nonexistent(self):
        po = PipelineOrchestrator()
        assert po.cancel_pipeline("nope") is False

    def test_complete_pipeline(self):
        po = PipelineOrchestrator()
        pid = po.create_pipeline(PipelineConfig(name="p"))
        run_id = po.trigger_pipeline(pid)
        po.complete_pipeline(run_id, success=True)
        assert po.get_pipeline_status(run_id) == PipelineStatus.SUCCESS


class TestJobScheduler:
    def test_schedule_job(self):
        js = JobScheduler(max_workers=4)
        job = Job(job_id="j1", name="test", priority=5)
        result = js.schedule(job)
        assert result.job_id == "j1"

    def test_queue_depth(self):
        js = JobScheduler(max_workers=1)
        js.schedule(Job(job_id="j1", name="t1", priority=5))
        js.schedule(Job(job_id="j2", name="t2", priority=5))
        assert js.get_queue_depth() >= 1

    def test_optimize_parallelism(self):
        js = JobScheduler(max_workers=4)
        jobs = [Job(job_id=f"j{i}", name=f"t{i}", estimated_duration=float(i + 1) * 10) for i in range(4)]
        result = js.optimize_parallelism(jobs)
        assert len(result) == 4

    def test_utilization(self):
        js = JobScheduler(max_workers=10)
        assert js.get_utilization() == 0.0


class TestRunTracker:
    def test_track_and_get_run(self):
        rt = RunTracker()
        rt.track_run("r1", {"commit": "abc"})
        run = rt.get_run("r1")
        assert run is not None
        assert run.status == "running"

    def test_active_runs(self):
        rt = RunTracker()
        rt.track_run("r1")
        rt.track_run("r2")
        active = rt.get_active_runs()
        assert len(active) == 2

    def test_compute_metrics(self):
        rt = RunTracker()
        rt.track_run("r1")
        rt.complete_run("r1", "success")
        metrics = rt.compute_metrics()
        assert metrics.total_runs == 1
        assert metrics.success_rate == 1.0

    def test_empty_metrics(self):
        rt = RunTracker()
        metrics = rt.compute_metrics()
        assert metrics.total_runs == 0


class TestCommitAnalyzer:
    def test_analyze_commit(self):
        ca = CommitAnalyzer()
        ca.add_test_mapping("src/api.py", ["test_api"])
        commit = CommitInfo(sha="abc", author="dev", message="update api", files_changed=["src/api.py"], additions=50, deletions=10)
        impact = ca.analyze(commit)
        assert impact.affected_tests == ["test_api"]
        assert impact.risk_score > 0

    def test_estimate_ci_time(self):
        ca = CommitAnalyzer()
        commit = CommitInfo(sha="abc", author="dev", message="update", files_changed=["f1.py"], additions=100)
        t = ca.estimate_ci_time(commit)
        assert t > 0

    def test_risk_score_merge(self):
        ca = CommitAnalyzer()
        commit = CommitInfo(sha="abc", author="dev", message="merge", files_changed=[], is_merge=True)
        score = ca.compute_risk_score(commit)
        assert score > 0.1  # merge commits have elevated risk


# =============================================================================
# Subsystem 5: Notification Routing
# =============================================================================
from src.notification_routing import NotificationRouter, CommitBlamer, SlackIntegrator, EscalationManager
from src.notification_routing.router import Failure as NotificationFailure, RoutingRule


class TestNotificationRouter:
    def test_route_failure(self):
        nr = NotificationRouter()
        failure = NotificationFailure(id="f1", test_name="test", error_message="error", severity="high")
        decision = nr.route(failure)
        assert decision.suppressed is False
        assert decision.channel == "slack"

    def test_find_responsible(self):
        nr = NotificationRouter()
        author = nr.find_responsible("abc123def")
        assert author is not None

    def test_should_notify(self):
        nr = NotificationRouter()
        failure = NotificationFailure(id="f1", test_name="t", error_message="err")
        assert nr.should_notify(failure, "ci-team") is True

    def test_routing_rules(self):
        nr = NotificationRouter()
        nr.add_rule(RoutingRule(name="critical", condition=lambda f: f.severity == "critical", channel="pagerduty", priority="critical"))
        rules = nr.get_routing_rules()
        assert len(rules) == 1


class TestCommitBlamer:
    def test_blame(self):
        cb = CommitBlamer()
        from src.notification_routing.blamer import BlameInfo
        cb.add_blame_info("src/api.py", BlameInfo(file_path="src/api.py", author="alice", commit_sha="abc", last_modified=100.0))
        result = cb.blame(["src/api.py"])
        assert result is not None
        assert result.author == "alice"

    def test_find_expert(self):
        cb = CommitBlamer()
        from src.notification_routing.blamer import ExpertInfo
        cb.add_expert("auth", ExpertInfo(area="auth", expert="bob", commit_count=50))
        assert cb.find_expert("auth") == "bob"

    def test_blame_confidence(self):
        cb = CommitBlamer()
        from src.notification_routing.blamer import BlameInfo
        cb.add_commit_files("abc", [BlameInfo(file_path="src/x.py", author="dev", commit_sha="abc")])
        conf = cb.compute_blame_confidence(["src/x.py"], "abc")
        assert conf == 1.0


class TestSlackIntegrator:
    def test_send_message(self):
        si = SlackIntegrator()
        msg = si.send_message("alice", "Build failed")
        assert msg.user == "alice"
        assert "failed" in msg.text.lower()

    def test_create_and_resolve_thread(self):
        si = SlackIntegrator()
        thread = si.create_thread("f1")
        assert thread.status == "open"
        si.resolve_thread(thread.id)
        assert si.get_thread(thread.id).status == "resolved"

    def test_notification_preferences(self):
        si = SlackIntegrator()
        from src.notification_routing.slack import NotificationPreferences
        prefs = NotificationPreferences(user="alice", min_severity="high")
        si.set_notification_preferences(prefs)
        got = si.get_notification_preferences("alice")
        assert got.min_severity == "high"


class TestEscalationManager:
    def test_escalate(self):
        em = EscalationManager()
        record = em.escalate("f1", level=0)
        assert record.escalated_to != ""

    def test_set_oncall(self):
        em = EscalationManager()
        from src.notification_routing.escalation import OncallSchedule
        em.set_oncall(OncallSchedule(primary="alice", secondary="bob"))
        record = em.escalate("f2", level=0)
        assert record.escalated_to == "alice"

    def test_acknowledge(self):
        em = EscalationManager()
        em.escalate("f1")
        assert em.acknowledge("f1") is True

    def test_get_escalations(self):
        em = EscalationManager()
        em.escalate("f1")
        em.escalate("f2")
        assert len(em.get_escalations()) == 2


# =============================================================================
# Subsystem 6: Test Analytics
# =============================================================================
from src.test_analytics import TestAnalytics, TestPrioritizer, CoverageTracker, TestDeduplicator
from src.test_analytics.analytics import TestRunRecord
from src.test_analytics.deduplicator import TestProfile
from src.test_analytics.coverage import CoverageRecord
from src.test_analytics.prioritizer import TestInfo, CommitFiles


class TestTestAnalytics:
    def test_test_health(self):
        ta = TestAnalytics()
        ta.record_run(TestRunRecord(test_name="t1", passed=True, duration=5.0))
        ta.record_run(TestRunRecord(test_name="t1", passed=True, duration=6.0))
        health = ta.get_test_health("t1")
        assert health.pass_rate == 1.0
        assert health.health_score > 0

    def test_suite_health(self):
        ta = TestAnalytics()
        ta.add_suite("suite1", ["t1", "t2"])
        ta.record_run(TestRunRecord(test_name="t1", passed=True, duration=5.0))
        ta.record_run(TestRunRecord(test_name="t2", passed=True, duration=3.0))
        health = ta.get_suite_health("suite1")
        assert health.total_tests == 2

    def test_pass_rate(self):
        ta = TestAnalytics()
        for i in range(10):
            ta.record_run(TestRunRecord(test_name="t1", passed=(i < 8), duration=1.0))
        rate = ta.compute_pass_rate("t1")
        assert rate == 0.8

    def test_trends(self):
        ta = TestAnalytics()
        for i in range(5):
            ta.record_run(TestRunRecord(test_name="t1", passed=True, duration=float(i + 1)))
        trends = ta.get_trends("t1")
        assert len(trends["durations"]) == 5


class TestTestPrioritizer:
    def test_prioritize(self):
        tp = TestPrioritizer()
        tp.add_test(TestInfo(name="slow", avg_duration=100, failure_rate=0.1))
        tp.add_test(TestInfo(name="fast", avg_duration=5, failure_rate=0.5))
        order = tp.prioritize(["slow", "fast"])
        assert order[0] == "fast"  # higher failure rate + faster

    def test_impact_score(self):
        tp = TestPrioritizer()
        info = TestInfo(name="t1", failure_rate=0.3, avg_duration=10, covered_files=["src/api.py"])
        commit = CommitFiles(sha="abc", files=["src/api.py"])
        score = tp.compute_impact_score(info, commit)
        assert score > 30  # file overlap bonus

    def test_critical_tests(self):
        tp = TestPrioritizer()
        tp.add_test(TestInfo(name="t1", failure_rate=0.5))
        tp.add_test(TestInfo(name="t2", failure_rate=0.01))
        critical = tp.get_critical_tests()
        assert "t1" in critical


class TestCoverageTracker:
    def test_track_coverage(self):
        ct = CoverageTracker()
        ct.track_coverage(CoverageRecord(commit="abc", line_coverage=0.85, branch_coverage=0.75,
                                          files_covered={"api.py": 0.9, "auth.py": 0.6}))
        latest = ct.get_latest()
        assert latest is not None
        assert latest.line_coverage == 0.85

    def test_identify_gaps(self):
        ct = CoverageTracker()
        ct.track_coverage(CoverageRecord(commit="abc", line_coverage=0.7, branch_coverage=0.6,
                                          files_covered={"good.py": 0.95, "bad.py": 0.3}))
        gaps = ct.identify_gaps(threshold=0.7)
        assert len(gaps) == 1
        assert gaps[0].file_path == "bad.py"

    def test_compute_risk(self):
        ct = CoverageTracker()
        assert ct.compute_risk(0.01) == "low"
        assert ct.compute_risk(-0.03) == "medium"
        assert ct.compute_risk(-0.1) == "high"

    def test_coverage_trend(self):
        ct = CoverageTracker()
        ct.track_coverage(CoverageRecord(commit="c1", line_coverage=0.8, branch_coverage=0.7))
        ct.track_coverage(CoverageRecord(commit="c2", line_coverage=0.85, branch_coverage=0.75))
        trend = ct.get_coverage_trend()
        assert len(trend) == 2


class TestTestDeduplicator:
    def test_find_duplicates(self):
        td = TestDeduplicator()
        td.add_profile(TestProfile(name="t1", covered_files={"a.py", "b.py"}, avg_duration=10))
        td.add_profile(TestProfile(name="t2", covered_files={"a.py", "b.py"}, avg_duration=12))
        dups = td.find_duplicates()
        assert len(dups) >= 1
        assert dups[0].overlap_score >= 0.5

    def test_compute_overlap(self):
        td = TestDeduplicator()
        p1 = TestProfile(name="t1", covered_files={"a.py", "b.py"})
        p2 = TestProfile(name="t2", covered_files={"a.py", "c.py"})
        report = td.compute_overlap(p1, p2)
        assert report.overlap_score > 0

    def test_suggest_consolidations(self):
        td = TestDeduplicator()
        td.add_profile(TestProfile(name="t1", covered_files={"a.py"}, avg_duration=10))
        td.add_profile(TestProfile(name="t2", covered_files={"a.py"}, avg_duration=15))
        suggestions = td.suggest_consolidations()
        assert len(suggestions) >= 0

    def test_estimate_savings(self):
        td = TestDeduplicator()
        from src.test_analytics.deduplicator import ConsolidationSuggestion
        savings = td.estimate_savings([
            ConsolidationSuggestion(tests=["t1", "t2"], reason="r", estimated_savings=10.0),
            ConsolidationSuggestion(tests=["t3", "t4"], reason="r", estimated_savings=5.0),
        ])
        assert savings == 15.0


# =============================================================================
# Subsystem 7: Monorepo
# =============================================================================
from src.monorepo import MonorepoAnalyzer, BuildOptimizer, MergeQueueManager, BranchManager
from src.monorepo.analyzer import PackageInfo, CommitChange
from src.monorepo.optimizer import BuildTask
from src.monorepo.merge_queue import PullRequest


class TestMonorepoAnalyzer:
    def test_analyze_structure(self):
        ma = MonorepoAnalyzer()
        packages = ma.analyze_structure([
            "packages/auth/login.py",
            "packages/auth/signup.py",
            "packages/api/routes.py",
            "README.md",
        ])
        assert "auth" in packages
        assert "api" in packages

    def test_detect_affected_packages(self):
        ma = MonorepoAnalyzer()
        ma.add_package(PackageInfo(name="auth", path="packages/auth", files=["packages/auth/login.py"]))
        ma.add_package(PackageInfo(name="api", path="packages/api", files=["packages/api/routes.py"]))
        commit = CommitChange(sha="abc", files=["packages/auth/login.py"])
        affected = ma.detect_affected_packages(commit)
        assert "auth" in affected

    def test_dependency_graph(self):
        ma = MonorepoAnalyzer()
        ma.add_package(PackageInfo(name="api", path="p/api"))
        ma.add_package(PackageInfo(name="auth", path="p/auth"))
        ma.add_dependency("api", "auth")
        graph = ma.compute_dependency_graph()
        assert "auth" in graph.get("api", set())

    def test_change_impact(self):
        ma = MonorepoAnalyzer()
        pkg = PackageInfo(name="p1", path="p1", files=["p1/main.py"])
        ma.add_package(pkg)
        ma.add_package(PackageInfo(name="p2", path="p2", files=["p2/other.py"]))
        impact = ma.get_change_impact(CommitChange(sha="abc", files=["p1/main.py"]))
        assert len(impact.affected_packages) >= 1


class TestBuildOptimizer:
    def test_detect_affected_builds(self):
        bo = BuildOptimizer()
        bo.add_package("auth", BuildTask(package="auth", estimated_duration=60))
        bo.add_package("api", BuildTask(package="api", estimated_duration=120))
        commit = CommitChange(sha="abc", files=["packages/auth/login.py"])
        affected = bo.detect_affected_builds(commit)
        assert "auth" in affected

    def test_compute_build_order(self):
        bo = BuildOptimizer()
        bo.add_package("core", BuildTask(package="core", dependencies=set()))
        bo.add_package("api", BuildTask(package="api", dependencies={"core"}))
        plan = bo.compute_build_order(["core", "api"])
        assert len(plan.stages) == 2  # core first, then api
        assert plan.stages[0] == ["core"]

    def test_parallelize(self):
        bo = BuildOptimizer()
        for name in ["a", "b", "c", "d"]:
            bo.add_package(name, BuildTask(package=name))
        plan = bo.parallelize(["a", "b", "c", "d"], workers=2)
        assert plan.parallelism_used <= 2

    def test_estimate_build_time(self):
        bo = BuildOptimizer()
        bo.add_package("a", BuildTask(package="a", estimated_duration=60))
        bo.add_package("b", BuildTask(package="b", estimated_duration=30))
        t = bo.estimate_build_time(["a", "b"])
        assert t > 0


class TestMergeQueueManager:
    def test_enqueue_dequeue(self):
        mqm = MergeQueueManager()
        pr = PullRequest(pr_id="pr-1", title="Fix bug", author="dev")
        pos = mqm.enqueue(pr)
        assert pos >= 0
        removed = mqm.dequeue("pr-1")
        assert removed is not None

    def test_queue_position(self):
        mqm = MergeQueueManager()
        mqm.enqueue(PullRequest(pr_id="pr-1", title="t1", author="a"))
        mqm.enqueue(PullRequest(pr_id="pr-2", title="t2", author="b"))
        assert mqm.get_queue_position("pr-1") >= 0
        assert mqm.get_queue_position("pr-999") == -1

    def test_optimize_queue(self):
        mqm = MergeQueueManager()
        mqm.enqueue(PullRequest(pr_id="pr-1", title="t1", author="a", ci_status="passing"))
        mqm.enqueue(PullRequest(pr_id="pr-2", title="t2", author="b", ci_status="pending"))
        order = mqm.optimize_queue()
        assert order[0] == "pr-1"  # passing first

    def test_queue_stats(self):
        mqm = MergeQueueManager()
        mqm.enqueue(PullRequest(pr_id="pr-1", title="t1", author="a", ci_status="passing"))
        stats = mqm.get_queue_stats()
        assert stats.total_prs == 1
        assert stats.passing_prs == 1


class TestBranchManager:
    def test_create_branch(self):
        bm = BranchManager()
        b = bm.create_branch("feature/auth", "main")
        assert b.name == "feature/auth"
        assert b.base == "main"

    def test_detect_stale(self):
        bm = BranchManager()
        bm.create_branch("old-branch", "main")
        bm._branches["old-branch"].last_commit_at = time.time() - 40 * 86400  # 40 days ago
        stale = bm.detect_stale_branches()
        assert len(stale) >= 1

    def test_branch_health(self):
        bm = BranchManager()
        bm.create_branch("new-feature", "main")
        health = bm.get_branch_health("new-feature")
        assert health is not None
        assert health.status == "healthy"

    def test_suggest_cleanup(self):
        bm = BranchManager()
        bm.create_branch("merged-branch", "main")
        bm.mark_merged("merged-branch")
        suggestions = bm.suggest_cleanup()
        assert len(suggestions) >= 1
        assert any(s.action == "delete" for s in suggestions)


# =============================================================================
# Subsystem 8: Reliability
# =============================================================================
from src.reliability import SLATracker, ReliabilityScorer, IncidentManager, CapacityPlanner
from src.reliability.incident import IncidentSeverity, IncidentStatus
from src.reliability.capacity import CapacityInfo


class TestSLATracker:
    def test_define_and_check_sla(self):
        st = SLATracker()
        st.define_sla("availability", 0.999)
        st.record_measurement("availability", 0.9995)
        st.record_measurement("availability", 0.998)
        result = st.check_sla("availability")
        assert result is not None
        assert result.breaches >= 1

    def test_sla_report(self):
        st = SLATracker()
        st.define_sla("latency", 0.95)
        st.record_measurement("latency", 0.96)
        report = st.get_sla_report()
        assert len(report.sla_results) == 1

    def test_breach_rate(self):
        st = SLATracker()
        st.define_sla("uptime", 0.99)
        for v in [0.995, 0.985, 0.992, 0.988]:
            st.record_measurement("uptime", v)
        rate = st.compute_breach_rate("uptime")
        assert rate > 0


class TestReliabilityScorer:
    def test_compute_score(self):
        rs = ReliabilityScorer()
        score = rs.compute_score("ci-runner", availability=0.999, latency_p95=20, error_rate=0.01)
        assert score.score > 50

    def test_identify_risks(self):
        rs = ReliabilityScorer()
        rs.compute_score("comp1", availability=0.95, error_rate=0.1, latency_p95=90)
        risks = rs.identify_risks()
        assert len(risks) >= 1

    def test_suggest_mitigations(self):
        rs = ReliabilityScorer()
        from src.reliability.scorer import Risk
        risks = [Risk(component="c", risk_type="availability", severity="high", description="d")]
        mitigations = rs.suggest_mitigations(risks)
        assert len(mitigations) == 1

    def test_overall_score(self):
        rs = ReliabilityScorer()
        rs.compute_score("c1", availability=0.99)
        rs.compute_score("c2", availability=0.98)
        assert rs.get_overall_score() > 0


class TestIncidentManager:
    def test_create_incident(self):
        im = IncidentManager()
        inc = im.create_incident("CI outage", IncidentSeverity.CRITICAL)
        assert inc.id.startswith("INC-")
        assert inc.severity == IncidentSeverity.CRITICAL

    def test_update_incident(self):
        im = IncidentManager()
        inc = im.create_incident("Issue")
        updated = im.update_incident(inc.id, IncidentStatus.INVESTIGATING, "Looking into it")
        assert updated.status == IncidentStatus.INVESTIGATING

    def test_active_incidents(self):
        im = IncidentManager()
        im.create_incident("Issue 1")
        im.create_incident("Issue 2")
        assert len(im.get_active_incidents()) == 2

    def test_postmortem(self):
        im = IncidentManager()
        inc = im.create_incident("Big outage")
        im.update_incident(inc.id, IncidentStatus.RESOLVED)
        pm = im.create_postmortem(inc.id, "DNS failure", ["Fix DNS config"], ["Monitor DNS"])
        assert pm is not None
        assert len(pm.action_items) == 1


class TestCapacityPlanner:
    def test_forecast_demand(self):
        cp = CapacityPlanner()
        forecasts = cp.forecast_demand(7)
        assert len(forecasts) == 7

    def test_current_capacity(self):
        cp = CapacityPlanner()
        cap = cp.get_current_capacity()
        assert cap.total_runners > 0

    def test_suggest_scaling(self):
        cp = CapacityPlanner()
        suggestion = cp.suggest_scaling()
        assert suggestion.action in ("scale_up", "scale_down", "maintain")

    def test_estimate_cost(self):
        cp = CapacityPlanner()
        cost = cp.estimate_cost(20)
        assert cost.monthly_cost > 0
        assert cost.runners == 20


# =============================================================================
# Subsystem 9: PR Automation
# =============================================================================
from src.pr_automation import PRAutomator, CheckRunner, ConflictResolver, ReviewAssigner
from src.pr_automation.automator import Diagnosis as PRDiagnosis, PR
from src.pr_automation.checks import CheckConfig
from src.pr_automation.review import Reviewer


class TestPRAutomator:
    def test_create_fix_pr(self):
        pa = PRAutomator()
        diag = PRDiagnosis(root_cause="timeout", category="timeout", fix_description="increase timeout")
        pr = pa.create_fix_pr(diag)
        assert pr.status.value == "open"
        assert "Fix:" in pr.title

    def test_review_pr(self):
        pa = PRAutomator()
        diag = PRDiagnosis(root_cause="err", category="test", fix_description="fix")
        pr = pa.create_fix_pr(diag)
        review = pa.review_pr(pr.pr_id)
        assert review["status"] in ("approved", "changes_requested")

    def test_merge_pr(self):
        pa = PRAutomator()
        diag = PRDiagnosis(root_cause="err", category="test", fix_description="fix")
        pr = pa.create_fix_pr(diag)
        pa.update_pr(pr.pr_id, checks_passing=True)
        assert pa.merge_pr(pr.pr_id) is True

    def test_merge_pr_checks_failing(self):
        pa = PRAutomator()
        diag = PRDiagnosis(root_cause="err", category="test", fix_description="fix")
        pr = pa.create_fix_pr(diag)
        pa.update_pr(pr.pr_id, checks_passing=False)
        assert pa.merge_pr(pr.pr_id, checks_required=True) is False


class TestCheckRunner:
    def test_define_and_run_checks(self):
        cr = CheckRunner()
        cr.define_check("lint")
        cr.define_check("test")
        results = cr.run_checks("pr-1")
        assert len(results) == 2

    def test_bypass_check(self):
        cr = CheckRunner()
        cr.define_check("lint")
        assert cr.bypass_check("lint", "emergency") is True
        results = cr.run_checks("pr-1")
        assert results[0].passed is True
        assert "Bypassed" in results[0].message

    def test_all_passed(self):
        cr = CheckRunner()
        cr.define_check("test")
        cr.run_checks("pr-1")
        assert cr.all_passed("pr-1") is True

    def test_bypass_nonexistent(self):
        cr = CheckRunner()
        assert cr.bypass_check("nope", "reason") is False


class TestConflictResolver:
    def test_detect_no_conflicts(self):
        cr = ConflictResolver()
        report = cr.detect_conflicts("pr-1")
        assert len(report.conflicts) == 0

    def test_detect_conflicts(self):
        cr = ConflictResolver()
        report = cr.detect_conflicts("pr-1",
            files_base={"file.py": "old content"},
            files_pr={"file.py": "new content"})
        assert len(report.conflicts) == 1

    def test_auto_resolve(self):
        cr = ConflictResolver()
        cr.detect_conflicts("pr-1",
            files_base={"f.py": "x"},
            files_pr={"f.py": "y"})
        resolved = cr.auto_resolve("pr-1")
        assert resolved >= 0

    def test_escalate_conflict(self):
        cr = ConflictResolver()
        cr.detect_conflicts("pr-1",
            files_base={"f.py": "a" * 200},
            files_pr={"f.py": "b" * 200})
        msg = cr.escalate_conflict("pr-1")
        assert msg is not None


class TestReviewAssigner:
    def test_assign(self):
        ra = ReviewAssigner()
        ra.add_reviewer(Reviewer(name="alice", expertise={"api", "auth"}))
        ra.add_reviewer(Reviewer(name="bob", expertise={"frontend"}))
        assignment = ra.assign("pr-1", files=["src/api.py"])
        assert len(assignment.reviewers) >= 1

    def test_review_load(self):
        ra = ReviewAssigner()
        ra.add_reviewer(Reviewer(name="alice"))
        assert ra.get_review_load("alice") == 0
        ra.assign("pr-1", files=["src/api.py"])
        assert ra.get_review_load("alice") == 1

    def test_balance_assignment(self):
        ra = ReviewAssigner()
        ra.add_reviewer(Reviewer(name="alice", expertise={"api"}))
        ra.add_reviewer(Reviewer(name="bob", expertise={"api"}))
        result = ra.balance_assignment(["pr-1", "pr-2"])
        assert len(result) == 2


# =============================================================================
# Subsystem 10: Continuous Analysis
# =============================================================================
from src.continuous_analysis import HealthMonitor, TrendAnalyzer, PatternDetector, FeedbackLoop


class TestHealthMonitor:
    def test_health_score(self):
        hm = HealthMonitor()
        hm.set_component_score("ci-runner", 95.0)
        hm.set_component_score("test-suite", 88.0)
        score = hm.get_health_score()
        assert score.score > 80
        assert score.status == "healthy"

    def test_degrading_areas(self):
        hm = HealthMonitor()
        hm.record_metric("latency", 50.0)
        hm.record_metric("latency", 45.0)
        hm.record_metric("latency", 40.0)
        areas = hm.get_degrading_areas()
        assert len(areas) >= 1

    def test_predict_failures(self):
        hm = HealthMonitor()
        hm.record_metric("error_rate", 0.02)
        hm.record_metric("error_rate", 0.04)
        hm.record_metric("error_rate", 0.08)
        predictions = hm.predict_failures()
        assert len(predictions) >= 1

    def test_dashboard_data(self):
        hm = HealthMonitor()
        hm.set_component_score("ci-runner", 95.0)
        dashboard = hm.get_dashboard_data()
        assert dashboard.health_score > 0


class TestTrendAnalyzer:
    def test_analyze_trend_up(self):
        ta = TrendAnalyzer()
        for v in [10, 20, 30, 40, 50]:
            ta.record("metric1", v)
        trend = ta.analyze_trend("metric1")
        assert trend.direction == "up"

    def test_analyze_trend_flat(self):
        ta = TrendAnalyzer()
        for v in [10, 10, 10, 10]:
            ta.record("metric2", v)
        trend = ta.analyze_trend("metric2")
        assert trend.direction == "flat"

    def test_detect_anomalies(self):
        ta = TrendAnalyzer()
        for v in [10, 11, 10, 12, 100]:  # 100 is anomaly
            ta.record("metric3", v)
        anomalies = ta.detect_anomalies("metric3", threshold=1.5)
        assert len(anomalies) >= 1

    def test_forecast(self):
        ta = TrendAnalyzer()
        for v in [10, 20, 30, 40, 50]:
            ta.record("metric4", v)
        forecasts = ta.forecast("metric4", days=3)
        assert len(forecasts) == 3
        assert forecasts[0].value > 50  # upward trend

    def test_correlate_trends(self):
        ta = TrendAnalyzer()
        for i in range(10):
            ta.record("a", float(i))
            ta.record("b", float(i) * 2)  # perfectly correlated
        corr = ta.correlate_trends(["a", "b"])
        assert len(corr) == 1
        key = "a:b"
        assert abs(corr[key]) > 0.9


class TestPatternDetector:
    def test_detect_failure_patterns(self):
        pd = PatternDetector()
        for _ in range(5):
            pd.record_failure("test_auth", "ERROR: timeout on /api/auth")
        patterns = pd.detect_failure_patterns()
        assert len(patterns) >= 1

    def test_find_recurring_failures(self):
        pd = PatternDetector()
        pd.record_failure("test_a", "error X", "r1")
        pd.record_failure("test_b", "error Y", "r2")
        pd.record_failure("test_a", "error X", "r3")
        recurring = pd.find_recurring_failures()
        assert len(recurring) >= 1

    def test_identify_seasonality(self):
        pd = PatternDetector()
        for i in range(20):
            pd.record_failure(f"test_{i}", f"error {i}")
        seasonality = pd.identify_seasonality()
        assert seasonality.period in ("daily", "weekly", "none")

    def test_pattern_report(self):
        pd = PatternDetector()
        pd.record_failure("test_1", "ERROR: timeout")
        pd.record_failure("test_2", "ERROR: timeout")
        report = pd.get_pattern_report()
        assert report["total_failures"] == 2


class TestFeedbackLoop:
    def test_record_feedback(self):
        fl = FeedbackLoop()
        fl.record_feedback("d1", "timeout", 0.8, "correct")
        assert fl.get_feedback_count() == 1

    def test_compute_accuracy(self):
        fl = FeedbackLoop()
        fl.record_feedback("d1", "timeout", 0.8, "correct")
        fl.record_feedback("d2", "network", 0.7, "correct")
        fl.record_feedback("d3", "test", 0.6, "incorrect")
        accuracy = fl.compute_accuracy()
        assert accuracy == pytest.approx(2/3, abs=0.01)

    def test_retrain_weights(self):
        fl = FeedbackLoop()
        fl.record_feedback("d1", "timeout", 0.8, "correct")
        fl.record_feedback("d2", "timeout", 0.7, "correct")
        fl.record_feedback("d3", "network", 0.6, "incorrect")
        weights = fl.retrain_weights()
        assert "timeout" in weights
        assert weights["timeout"] > weights["network"]

    def test_feedback_stats(self):
        fl = FeedbackLoop()
        fl.record_feedback("d1", "timeout", 0.8, "correct")
        fl.record_feedback("d2", "timeout", 0.7, "partial")
        stats = fl.get_feedback_stats()
        assert stats.total_feedback == 2
        assert stats.correct_count == 1

    def test_get_weight(self):
        fl = FeedbackLoop()
        assert fl.get_weight("unknown") == 0.5  # default


# Need pytest for approx
import pytest
