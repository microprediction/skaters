"""Lightweight seams for the optional TimesFM benchmark (no model dependencies)."""
from pathlib import Path
import csv

import pytest

np = pytest.importorskip("numpy")

from benchmarks.timesfm_distill import (
    LEVELS,
    MODEL_ID,
    MODEL_REVISION,
    adapter_runtime_size,
    METHODS,
    build_manifest,
    _linear_median_indices,
    _teacher_targets,
    _dist_from_prediction,
    evaluate_rows,
    fixed_context_laplace_predictions,
    extract_mean_quantiles,
    infer_test_targets,
    isotonic_projection,
    load_persisted_score_rows,
    normalized_huber_loss,
    summarize_scores,
    select_reconstruction_multiplier,
    _torch_normalized_huber,
    validate_series_disjoint,
    validate_records,
)


class Config:
    decode_index = 5


def test_quantile_mapping_uses_decode_index_and_ordered_deciles():
    full = np.arange(20, dtype=float).reshape(2, 10)
    explicit_mean = full[:, 5:6].copy()
    mean, quantiles = extract_mean_quantiles(
        {"full_predictions": full, "mean_predictions": explicit_mean}, Config()
    )
    assert np.array_equal(mean, full[:, 5])
    assert np.array_equal(quantiles, full[:, [0, 1, 2, 3, 4, 6, 7, 8, 9]])
    assert len(LEVELS) == 9

def test_three_dimensional_output_uses_horizon_zero():
    full = np.zeros((1, 3, 10), dtype=float)
    full[:, 0, :] = np.arange(10)
    full[:, 2, :] = 100 + np.arange(10)
    mean, _quantiles = extract_mean_quantiles({"full_predictions": full}, Config())
    assert mean[0] == 5.0

def test_preserve_tensor_path_also_uses_horizon_zero():
    class FakeTensor:
        def __init__(self, values):
            self.values = values
            self.ndim = values.ndim
            self.shape = values.shape
            self.device = "fake"

        def detach(self):
            return self

        def unsqueeze(self, axis):
            return FakeTensor(np.expand_dims(self.values, axis))

        def __getitem__(self, item):
            return self.values[item]

    full = np.zeros((1, 128, 10), dtype=float)
    full[:, 0, :] = np.arange(10)
    full[:, -1, :] = 100 + np.arange(10)
    mean, quantiles = extract_mean_quantiles(
        {"full_predictions": FakeTensor(full)}, Config(), preserve_torch=True
    )
    assert mean[0] == 5.0
    assert np.array_equal(quantiles[0], [0, 1, 2, 3, 4, 6, 7, 8, 9])


def test_ambiguous_prediction_arrays_are_rejected():
    full = np.zeros((1, 10), dtype=float)
    with pytest.raises(ValueError, match="explicit mean and quantile"):
        extract_mean_quantiles({"predictions": full}, Config())
    with pytest.raises(ValueError, match="exactly 10 channels"):
        extract_mean_quantiles({"full_predictions": full[:, :9]}, Config())


def test_real_pinned_model_exposes_decode_channel_contract():
    torch = pytest.importorskip("torch")
    transformers = pytest.importorskip("transformers")
    snapshot = (
        Path.home()
        / ".cache"
        / "huggingface"
        / "hub"
        / f"models--{MODEL_ID.replace('/', '--')}"
        / "snapshots"
        / MODEL_REVISION
    )
    if not snapshot.is_dir():
        pytest.skip("pinned TimesFM snapshot is not cached")
    model = transformers.TimesFm2_5ModelForPrediction.from_pretrained(
        snapshot, local_files_only=True, torch_dtype=torch.float32
    ).eval()
    assert model.config.decode_index == 5
    with torch.no_grad():
        output = model(
            past_values=torch.zeros((1, 128), dtype=torch.float32),
            forecast_context_len=128,
        )
    assert torch.equal(
        output.mean_predictions,
        output.full_predictions[..., model.config.decode_index],
    )
    mean, quantiles = extract_mean_quantiles(output, model.config, preserve_torch=True)
    assert torch.equal(mean, output.mean_predictions[:, 0])
    assert torch.equal(
        quantiles,
        output.full_predictions[:, 0, [0, 1, 2, 3, 4, 6, 7, 8, 9]],
    )


def test_inference_preserves_native_crossing_quantiles():
    native = np.asarray([0.0, 2.0, 1.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0])

    class NoGrad:
        def __enter__(self):
            return None

        def __exit__(self, *args):
            return False

    class FakeTorch:
        float32 = "float32"

        @staticmethod
        def no_grad():
            return NoGrad()

        @staticmethod
        def as_tensor(values, **_kwargs):
            return np.asarray(values)

    class FakeModel:
        def __call__(self, *, past_values, forecast_context_len):
            assert forecast_context_len == past_values.shape[1]
            full = np.zeros((len(past_values), 1, 10), dtype=float)
            full[:, 0, [0, 1, 2, 3, 4, 6, 7, 8, 9]] = native
            full[:, 0, 5] = 9.0
            return {"full_predictions": full}

    records = [{"context": [1.0, 2.0, 3.0]}]
    predictions = infer_test_targets(
        records,
        FakeModel(),
        Config(),
        "cpu",
        FakeTorch(),
        batch_size=1,
    )
    assert predictions[0][0] == 9.0
    assert np.array_equal(predictions[0][1], native)
    assert np.any(np.diff(predictions[0][1]) < 0.0)


def test_isotonic_projection_handles_crossing_quantiles():
    projected = isotonic_projection([3.0, 1.0, 2.0, 5.0])
    assert np.all(np.diff(projected) >= 0)
    assert np.allclose(projected, [2.0, 2.0, 2.0, 5.0])


def test_normalized_huber_zero_and_shape_mismatch():
    context = np.arange(8, dtype=float)[None, :]
    target = np.zeros((1, 10))
    assert normalized_huber_loss(target, target, context) == 0.0
    with pytest.raises(ValueError, match="shapes differ"):
        normalized_huber_loss(np.zeros((1, 9)), target, context)

def test_linear_median_indices_cover_even_context_without_torch():
    assert _linear_median_indices(128) == (63, 64)
    assert _linear_median_indices(127) == (63, 63)
    with pytest.raises(ValueError, match="positive"):
        _linear_median_indices(0)




def test_torch_and_numpy_huber_match_for_even_context():
    torch = pytest.importorskip("torch")
    context = np.asarray([[0.0, 1.0, 4.0, 9.0]], dtype=float)
    target = np.asarray([[1.0, 2.0]], dtype=float)
    predicted = np.asarray([[2.0, -1.0]], dtype=float)
    expected = normalized_huber_loss(predicted, target, context)
    actual = _torch_normalized_huber(
        torch.tensor(predicted), torch.tensor(target), torch.tensor(context)
    )
    assert float(actual) == pytest.approx(expected)

def test_series_disjoint_split_enforcement():
    records = [{"schema": "laplace-distill-v1", "series": "a", "split": "train"}]
    validate_series_disjoint(records)
    with pytest.raises(ValueError, match="multiple splits"):
        validate_series_disjoint(records + [{**records[0], "split": "test"}])


def _predictive(mean=0.0):
    return {"components": [[1.0, mean, 1.0]]}


def _record(series, origin, y):
    from skaters import Dist

    predictive = _predictive(0.0)
    dist = Dist.from_dict(predictive)
    return {
        "schema": "laplace-distill-v1", "series": series, "regime": "level",
        "split": "test", "origin": origin, "context": [0.0] * 128, "y": y,
        "teacher": {
            "mean": dist.mean,
            "levels": list(LEVELS),
            "quantiles": [dist.quantile(level) for level in LEVELS],
            "predictive": predictive,
        },
    }


def test_full_teacher_audit_runs_at_consumer_boundary():
    record = _record("a", 128, 0.1)
    record["teacher"]["mean"] = 1.0
    with pytest.raises(ValueError, match="teacher mean"):
        validate_records([record])


def test_adapter_size_ignores_nonruntime_files(tmp_path):
    (tmp_path / "adapter_config.json").write_bytes(b"abc")
    (tmp_path / "adapter_model.safetensors").write_bytes(b"12345")
    (tmp_path / "README.md").write_bytes(b"not loaded")
    names, size = adapter_runtime_size(str(tmp_path))
    assert names == ["adapter_config.json", "adapter_model.safetensors"]
    assert size == 8


def test_consumer_infers_nondefault_context_length():
    record = _record("a", 256, 0.1)
    record["context"] = [0.0] * 256
    validate_records([record])


def test_evaluation_uses_identical_targets_and_persisted_score_source(tmp_path):
    records = [_record("a", 128, 0.1), _record("b", 129, -0.2)]
    predictions = {m: [_predictive(0.0), _predictive(0.0)] for m in METHODS}
    q_predictions = [
        (record["teacher"]["mean"], record["teacher"]["quantiles"])
        for record in records
    ]
    for method in (
        "Laplace-q-fixed-bandwidth",
        "TimesFM-zero-shot",
        "TimesFM-laplace-qd",
    ):
        predictions[method] = q_predictions
    native_crossing = (
        0.0,
        np.asarray([0.3, 0.1, 0.2, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]),
    )
    predictions["TimesFM-zero-shot"] = [native_crossing] * len(records)
    score_path = tmp_path / "pred.csv"
    out, summary = evaluate_rows(records, predictions, str(score_path))
    assert [tuple((r["series"], r["origin"], r["y"])) for r in out] == [
        key
        for rec in records
        for key in [(rec["series"], rec["origin"], rec["y"])] * len(METHODS)
    ]
    assert {r["method"] for r in out} == set(METHODS)
    assert any(
        r.get("predictive") == records[0]["teacher"]["predictive"]
        for r in out
        if r["method"] == "laplace"
    )
    persisted = load_persisted_score_rows(score_path)
    persisted_summary = summarize_scores(persisted)
    assert summary["overall"] == persisted_summary["overall"]
    assert summary["paired"] == persisted_summary["paired"]
    assert summary["persistence"]["score_source"] == "canonical persisted CSV"
    raw_path = tmp_path / "pred_raw_quantiles.csv"
    with raw_path.open(newline="") as fh:
        raw_rows = list(csv.DictReader(fh))
    assert len(raw_rows) == len(records) * 3
    assert {row["method"] for row in raw_rows} == {
        "Laplace-q-fixed-bandwidth",
        "TimesFM-zero-shot",
        "TimesFM-laplace-qd",
    }
    assert all(row["q10"] and row["q90"] and row["raw_logpdf"] for row in raw_rows)
    zero_raw = next(row for row in raw_rows if row["method"] == "TimesFM-zero-shot")
    assert float(zero_raw["q10"]) == 0.3
    assert float(zero_raw["q20"]) == 0.1


def test_summary_directionality_and_pairwise_counts():
    rows = []
    for series in ("a", "b"):
        rows.extend([
            {"series": series, "regime": "r", "method": "laplace", "logpdf": -1.0, "crps": 1.0},
            {"series": series, "regime": "r", "method": "TimesFM-zero-shot", "logpdf": -2.0, "crps": 2.0},
            {"series": series, "regime": "r", "method": "TimesFM-laplace-qd", "logpdf": -3.0, "crps": 3.0},
        ])
    summary = summarize_scores(rows)
    assert summary["overall"]["laplace"]["ll"] > summary["overall"]["TimesFM-zero-shot"]["ll"]
    assert summary["overall"]["laplace"]["crps"] < summary["overall"]["TimesFM-zero-shot"]["crps"]
    assert summary["paired"]["overall"]["TimesFM-zero-shot"]["median_dll"] == -1.0
    assert summary["paired"]["overall"]["TimesFM-zero-shot"]["median_crps_ratio"] == 2.0
    pair = summary["pairwise"]["laplace_vs_TimesFM-zero-shot"]
    assert pair["n"] == 2 and pair["ll"]["laplace"] == 2 and pair["crps"]["laplace"] == 2
    assert pair["effect"]["median_dll_a_minus_b"] == 1.0
    assert pair["effect"]["median_crps_ratio_a_over_b"] == 0.5


def test_fixed_context_laplace_excludes_realized_target():
    record = _record("a", 128, 1.0)
    first = fixed_context_laplace_predictions([record])[0]
    changed = {**record, "y": -999.0}
    second = fixed_context_laplace_predictions([changed])[0]
    assert first.to_dict() == second.to_dict()


def test_density_selection_uses_validation_rows_only():
    validation = _record("validation-series", 128, 0.1)
    validation["split"] = "validation"
    test = _record("test-series", 128, 0.2)
    selected, diagnostics = select_reconstruction_multiplier(
        [validation, test], candidates=(0.5, 1.0, 2.0)
    )
    changed_test = {**test, "y": 1e9}
    selected_after_test_change, changed_diagnostics = select_reconstruction_multiplier(
        [validation, changed_test], candidates=(0.5, 1.0, 2.0)
    )
    assert selected_after_test_change == selected
    assert changed_diagnostics == diagnostics
    assert diagnostics["selection_rows"] == 1
    assert diagnostics["selection_series"] == 1


def test_manifest_records_revision_runtime_contract_and_relative_adapter_path():
    record = _record("a", 128, 0.1)
    manifest = build_manifest(
        records=[record],
        model_id=MODEL_ID,
        model_revision=MODEL_REVISION,
        config=Config(),
        seed=133,
        started=1.0,
        finished=2.0,
        trainable_parameters=10,
        adapter_path="/private/tmp/timesfm-issue133",
        device="mps",
        dtype="torch.float32",
    )
    assert manifest["schema"] == "timesfm-distill-v2"
    assert manifest["adapter_path"] == "timesfm-issue133"
    assert manifest["output_contract"]["decode_index"] == 5
    assert manifest["output_contract"]["quantile_channels"] == [
        0, 1, 2, 3, 4, 6, 7, 8, 9
    ]
    assert {"numpy", "torch", "transformers", "peft", "safetensors"} <= set(
        manifest["runtime"]["dependencies"]
    )
    assert manifest["runtime"]["device"] == "mps"
    assert manifest["source_tree"]["files"]
    assert all(not Path(path).is_absolute() for path in manifest["source_tree"]["files"])


def test_teacher_targets_ignore_realized_y():
    first = _record("a", 128, 1.0)
    second = {**first, "y": -999.0}
    c1, t1 = _teacher_targets([first])
    c2, t2 = _teacher_targets([second])
    assert np.array_equal(c1, c2)
    assert np.array_equal(t1, t2)


def test_exact_spliced_teacher_round_trips():
    from skaters import Dist
    from skaters.tails import SplicedDist

    predictive = SplicedDist(
        Dist.gaussian(), -2.0, 2.0, 0.02, 0.02, 0.1, 1.0, 0.1, 1.0
    ).to_dict()
    restored = _dist_from_prediction(predictive)
    assert predictive["spliced"] is True
    assert restored.to_dict() == predictive
