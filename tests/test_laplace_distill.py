import copy
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))

from benchmarks.laplace_distill import (
    SCHEMA,
    audit_records,
    build_records,
    fingerprint_records,
    iter_corpus,
    read_jsonl,
    generate_series_records,
    merge_jsonl,
    partition_series,
    predictive_from_record,
    synthetic_regimes,
    write_producer_manifest,
    write_jsonl,
)
from skaters import Dist

def test_predictive_round_trip_preserves_scores_and_summary():
    rows = generate_series_records([0.1, -0.2, 0.4, 0.0, 0.3, -0.1], "s", "r", "train", 3, burn_in=0)
    row = rows[0]
    restored = predictive_from_record(row)
    assert restored.to_dict() == row["teacher"]["predictive"]
    assert restored.logpdf(row["y"]) == pytest.approx(Dist.from_dict(row["teacher"]["predictive"]).logpdf(row["y"]))
    assert restored.crps(row["y"]) == pytest.approx(Dist.from_dict(row["teacher"]["predictive"]).crps(row["y"]))
    assert row["teacher"]["levels"] == pytest.approx([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9])
    assert row["teacher"]["quantiles"] == sorted(row["teacher"]["quantiles"])


def test_partition_is_deterministic_and_series_disjoint():
    ids = [f"s{i}" for i in range(30)]
    a = partition_series(ids, seed=42)
    b = partition_series(reversed(ids), seed=42)
    assert a == b
    assert set(a) == set(ids)
    assert all(sum(v == split for v in a.values()) for split in ("train", "validation", "test"))


def test_audit_rejects_malformed_crossing_nonfinite_and_cross_split_rows():
    rows = build_records(n=24, limit=4, context_length=4, max_records=3, burn_in=0)
    bad = copy.deepcopy(rows[0]); bad["teacher"]["quantiles"][3] = float("nan")
    with pytest.raises(ValueError): audit_records([bad], 4)
    bad = copy.deepcopy(rows[0]); bad["teacher"]["quantiles"][0] = bad["teacher"]["quantiles"][-1] + 1
    with pytest.raises(ValueError): audit_records([bad], 4)
    bad = copy.deepcopy(rows[0]); bad["context"] = bad["context"][:-1]
    with pytest.raises(ValueError): audit_records([bad], 4)
    other = copy.deepcopy(rows[0]); other["split"] = "test"
    with pytest.raises(ValueError): audit_records([rows[0], other], 4)


def test_audit_rejects_corrupted_context_overlap():
    rows = generate_series_records(
        [0.1, -0.2, 0.4, 0.0, 0.3, -0.1, 0.2], "s", "r", "train", 3, burn_in=0
    )
    bad = copy.deepcopy(rows)
    bad[1]["context"][0] += 1.0
    with pytest.raises(ValueError, match="chronology/leakage"):
        audit_records(bad, 3)


def test_audit_rejects_gap_two_overlap_and_prior_target_corruption():
    rows = generate_series_records(
        [0.1, -0.2, 0.4, 0.0, 0.3, -0.1, 0.2], "s", "r", "train", 3, burn_in=0
    )
    sparse = [rows[0], rows[2]]
    audit_records(sparse, 3)
    for index in (0, 1):
        bad = copy.deepcopy(sparse)
        bad[1]["context"][index] += 1.0
        with pytest.raises(ValueError, match="chronology/leakage"):
            audit_records(bad, 3)


def test_context_precedes_target_and_seed_is_byte_identical(tmp_path):
    rows_a = build_records(n=30, limit=4, context_length=5, max_records=4, seed=17, burn_in=0)
    rows_b = build_records(n=30, limit=4, context_length=5, max_records=4, seed=17, burn_in=0)
    assert rows_a == rows_b
    for row in rows_a:
        assert row["schema"] == SCHEMA
        assert row["origin"] >= 5
        assert len(row["context"]) == 5
    p1 = tmp_path / "a.jsonl"; p2 = tmp_path / "b.jsonl"
    assert write_jsonl(p1, rows_a) == write_jsonl(p2, rows_b)
    assert p1.read_bytes() == p2.read_bytes()
    assert fingerprint_records(rows_a) == fingerprint_records(rows_b)
    manifest_path, manifest = write_producer_manifest(
        p1,
        rows_a,
        {"mode": "test", "context": 5},
        tmp_path / "producer.json",
    )
    assert manifest_path.name == "producer.json"
    assert manifest["output"]["file"] == "a.jsonl"
    assert manifest["output"]["records_sha256"] == fingerprint_records(rows_a)
    assert manifest["producer_runtime"]["python"]
    assert manifest["source_tree"]["files"]
    assert "cross-platform byte identity is not claimed" in manifest["byte_identity_scope"]


def test_synthetic_regimes_are_deterministic_and_cover_required_behaviors():
    a = synthetic_regimes(20, seed=3)
    b = synthetic_regimes(20, seed=3)
    assert a == b
    assert {"seasonal-ar-economic", "sticky-repeating", "garch-returns", "random-walk-price-change"} == set(a)
    assert all(len(v) == 20 for v in a.values())

def test_source_override_pins_selected_arm_without_changing_default():
    rows = build_records(n=20, limit=4, context_length=4, max_records=2,
                         seed=4, source="synthetic", split_override="test", burn_in=0)
    assert rows and {row["split"] for row in rows} == {"test"}


def test_fred_core_fails_before_accepting_an_empty_cache(tmp_path, monkeypatch):
    from benchmarks import fred

    monkeypatch.setattr(fred, "_CACHE", str(tmp_path))
    with pytest.raises(FileNotFoundError, match="missing canonical FRED cache files"):
        list(iter_corpus("fred-core", limit=8))

def test_last_window_cap_runs_forecaster_to_end_and_preserves_pending_semantics():
    values = list(range(10))

    def factory():
        def forecast(y, state):
            count = 1 if state is None else state + 1
            return [Dist.gaussian(float(y) + count / 1000.0, 1.0)], count
        return forecast

    rows = generate_series_records(values, "s", "r", "test", context_length=3,
                                   max_records=2, burn_in=0,
                                   forecaster_factory=factory)
    assert [row["origin"] for row in rows] == [8, 9]
    assert rows[0]["context"] == [5.0, 6.0, 7.0]
    assert rows[1]["context"] == [6.0, 7.0, 8.0]
    assert rows[0]["teacher"]["mean"] == pytest.approx(7.008)
    assert rows[1]["teacher"]["mean"] == pytest.approx(8.009)


def test_m4_adapter_fails_before_implicit_download(tmp_path, monkeypatch):
    import types

    fake = types.ModuleType("corpus")
    fake._M4_CACHE = str(tmp_path / "missing.csv")
    fake.iter_arm = lambda *_args, **_kwargs: pytest.fail("iter_arm must not run")
    monkeypatch.setitem(sys.modules, "corpus", fake)
    with pytest.raises(FileNotFoundError, match="missing canonical M4 hourly"):
        list(iter_corpus("m4-hourly", limit=3))


def test_m4_adapter_enforces_limit(monkeypatch):
    import types
    from benchmarks import laplace_distill

    fake = types.ModuleType("corpus")
    fake._M4_CACHE = "unused-by-test.csv"
    fake.iter_arm = lambda arm, limit=1000: (
        (str(i), "M4", [0.0, 1.0]) for i in range(10)
    )
    monkeypatch.setitem(sys.modules, "corpus", fake)
    monkeypatch.setattr(laplace_distill, "_preflight_m4", lambda _path: None)
    assert len(list(iter_corpus("m4-hourly", limit=3))) == 3


def test_regime_balanced_partitions_have_all_splits():
    rows = build_records(n=304, limit=12, context_length=4, max_records=1, burn_in=0, seed=5)
    for regime in {"seasonal-ar-economic", "sticky-repeating", "garch-returns", "random-walk-price-change"}:
        assert {row["split"] for row in rows if row["regime"] == regime} == {"train", "validation", "test"}

def test_merge_mode_audits_combined_rows_and_creates_parent_dirs(tmp_path):
    a = generate_series_records([1.0, 2.0, 3.0, 4.0], "a", "r", "train", 2, burn_in=0)
    b = generate_series_records([4.0, 3.0, 2.0, 1.0], "b", "r", "test", 2, burn_in=0)
    pa = tmp_path / "in" / "a.jsonl"; pb = tmp_path / "in" / "b.jsonl"
    out = tmp_path / "nested" / "merged.jsonl"
    write_jsonl(pa, a); write_jsonl(pb, b)
    digest = merge_jsonl([pa, pb], out, context_length=2)
    assert out.exists() and digest
    assert len(out.read_bytes().splitlines()) == len(a) + len(b)

def test_gzip_jsonl_is_deterministic_and_fingerprint_is_uncompressed(tmp_path):
    rows = generate_series_records([1.0, 2.0, 3.0, 4.0], "gz", "r", "train", 2, burn_in=0)
    plain = tmp_path / "records.jsonl"
    gz1 = tmp_path / "records-a.jsonl.gz"
    gz2 = tmp_path / "records-b.jsonl.gz"
    digest_plain = write_jsonl(plain, rows)
    digest_gz1 = write_jsonl(gz1, rows)
    digest_gz2 = write_jsonl(gz2, rows)
    assert digest_plain == digest_gz1 == digest_gz2 == fingerprint_records(rows)
    assert gz1.read_bytes() == gz2.read_bytes()
    assert read_jsonl(gz1) == read_jsonl(plain) == json.loads(json.dumps(rows))
