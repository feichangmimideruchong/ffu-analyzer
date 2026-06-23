import observability


class TestObservability:
    def setup_method(self):
        observability._records.clear()

    def test_empty_stats(self):
        assert observability.stats() == {"count": 0}

    def test_records_and_aggregates(self):
        observability.record(latency_ms=100.0, stages={"search_ms": 20.0}, hits=3, tool_iterations=1)
        observability.record(latency_ms=200.0, stages={"search_ms": 40.0}, hits=0, tool_iterations=2)
        stats = observability.stats()
        assert stats["count"] == 2
        assert stats["avg_latency_ms"] == 150.0
        assert stats["avg_stage_ms"]["search_ms"] == 30.0
        assert stats["not_found_rate"] == 0.5

    def test_not_found_flag(self):
        observability.record(latency_ms=10.0, stages={}, hits=0, tool_iterations=1)
        assert observability.stats()["recent"][0]["not_found"] is True

    def test_caps_at_100(self):
        for i in range(150):
            observability.record(latency_ms=float(i), stages={}, hits=1, tool_iterations=1)
        assert observability.stats()["count"] == 100
