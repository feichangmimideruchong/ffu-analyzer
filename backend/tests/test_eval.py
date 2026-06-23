import importlib.util
from pathlib import Path

import retrieval

_SPEC = importlib.util.spec_from_file_location(
    "run_eval", Path(__file__).resolve().parent.parent / "eval" / "run_eval.py"
)
run_eval = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(run_eval)


class TestClampScore:
    def test_in_range(self):
        assert run_eval._clamp_score(0.7) == 0.7

    def test_above_one(self):
        assert run_eval._clamp_score(1.5) == 1.0

    def test_below_zero(self):
        assert run_eval._clamp_score(-0.2) == 0.0

    def test_non_numeric(self):
        assert run_eval._clamp_score("high") == 0.0

    def test_none(self):
        assert run_eval._clamp_score(None) == 0.0


class TestAsBool:
    def test_true_string(self):
        assert run_eval._as_bool("true") is True

    def test_false_string(self):
        assert run_eval._as_bool("false") is False

    def test_native_bool(self):
        assert run_eval._as_bool(True) is True
        assert run_eval._as_bool(False) is False


class TestHitAtK:
    def test_hit_when_source_present(self, monkeypatch):
        monkeypatch.setattr(
            retrieval, "search", lambda q, k=8: [{"filename": "09.1 AF Ekalund.pdf"}]
        )
        hit, names = run_eval.hit_at_k("q", ["09.1 AF"], 8)
        assert hit is True
        assert names == ["09.1 AF Ekalund.pdf"]

    def test_miss_when_source_absent(self, monkeypatch):
        monkeypatch.setattr(
            retrieval, "search", lambda q, k=8: [{"filename": "13.1 Anbud.xlsx"}]
        )
        hit, _ = run_eval.hit_at_k("q", ["09.1 AF"], 8)
        assert hit is False

    def test_empty_expected_sources_is_not_a_hit(self, monkeypatch):
        monkeypatch.setattr(retrieval, "search", lambda q, k=8: [{"filename": "x.pdf"}])
        hit, _ = run_eval.hit_at_k("q", [], 8)
        assert hit is False
