import copy
import json
import sys
import types
from pathlib import Path

import pytest

np = pytest.importorskip("numpy")

from benchmarks import arm_adapters as aa
from benchmarks.tirex2_issue138 import (
    archive_source,
    build_origins,
    online_laplace_dists,
    select_density_multiplier,
    validate_protocol,
)


def _validate_frozen_protocol(protocol):
    validate_protocol(
        protocol,
        n_series=24,
        context_length=128,
        validation_length=64,
        test_length=64,
        max_history=1000,
        batch_size=128,
        device="cpu",
        model_id=aa.TIREX2_MODEL_ID,
        revision=aa.TIREX2_MODEL_REVISION,
    )


def test_protocol_validation_rejects_execution_mismatches():
    path = (
        Path(__file__).resolve().parents[1]
        / "benchmarks"
        / "tirex2_artifacts"
        / "protocol_issue138.json"
    )
    protocol = json.loads(path.read_text())
    _validate_frozen_protocol(protocol)
    mutations = [
        ("horizon", 2),
        ("quantile_levels", [0.5]),
        ("runtime.device", "cuda"),
        ("runtime.batch_size", 64),
        ("test_time_augmentation.tta_diff", True),
        ("density_reconstruction.candidate_spacing_multipliers", [1.0]),
    ]
    for dotted_key, value in mutations:
        changed = copy.deepcopy(protocol)
        target = changed
        parts = dotted_key.split(".")
        for part in parts[:-1]:
            target = target[part]
        target[parts[-1]] = value
        with pytest.raises(ValueError, match="protocol"):
            _validate_frozen_protocol(changed)


def test_tirex2_adapter_uses_native_ordered_quantiles(monkeypatch):
    torch = pytest.importorskip("torch")
    calls = {}

    class TimeseriesType:
        def __init__(self, target, past_covariates, future_covariates):
            self.target = target
            self.past_covariates = past_covariates
            self.future_covariates = future_covariates

    class Model:
        def _quantile_levels(self):
            return list(aa.LEVELS9)

        def forecast(self, timeseries, prediction_length, **kwargs):
            calls.update(kwargs)
            calls["contexts"] = [item.target.clone() for item in timeseries]
            row = np.arange(9, dtype=float)[None, :, None]
            return [np.repeat(row, prediction_length, axis=2) for _ in timeseries]

    monkeypatch.setitem(sys.modules, "tirex2", types.SimpleNamespace(
        TimeseriesType=TimeseriesType,
        load_model=lambda *args, **kwargs: pytest.fail("cached fake model should be used"),
    ))
    monkeypatch.setattr(aa, "_tirex2", Model())
    quantiles = aa.tirex2_quantiles_from_contexts(
        np.asarray([[1.0, 2.0], [3.0, 4.0]]),
        h=2,
        batch_size=7,
    )
    assert quantiles.shape == (2, 9)
    assert np.array_equal(quantiles[0], np.arange(9, dtype=float))
    assert torch.equal(calls["contexts"][0], torch.tensor([[1.0, 2.0]]))
    assert calls["batch_size"] == 7
    assert calls["tta_sign_flip"] is False
    assert calls["tta_diff"] is False


def test_build_origins_excludes_each_realized_target():
    panel = [{"series": "s", "values": np.arange(10, dtype=float)}]
    origins, contexts = build_origins(
        panel,
        context_length=3,
        validation_length=2,
        test_length=2,
    )
    assert [row["split"] for row in origins] == [
        "validation", "validation", "test", "test"
    ]
    assert np.array_equal(contexts[0], [3.0, 4.0, 5.0])
    assert origins[0]["y"] == 6.0
    assert np.array_equal(contexts[-1], [6.0, 7.0, 8.0])
    assert origins[-1]["y"] == 9.0


def test_density_selection_ignores_test_targets():
    origins = [
        {"series": "a", "split": "validation", "y": 0.0},
        {"series": "b", "split": "validation", "y": 0.1},
        {"series": "a", "split": "test", "y": 1000.0},
    ]
    quantiles = np.asarray([
        np.linspace(-0.4, 0.4, 9),
        np.linspace(-0.3, 0.5, 9),
        np.linspace(-0.4, 0.4, 9),
    ])
    selected, diagnostics = select_density_multiplier(origins, quantiles)
    origins[-1]["y"] = -1000.0
    selected_after_test_change, diagnostics_after_test_change = select_density_multiplier(
        origins, quantiles
    )
    assert selected_after_test_change == selected
    assert diagnostics_after_test_change["candidate_scores"] == diagnostics["candidate_scores"]
    assert diagnostics["selection_rows"] == 2
    assert diagnostics["selection_series"] == 2


def test_online_laplace_first_forecast_is_causal():
    values = [0.2, -0.1, 0.3, 0.0, 0.4]
    original = online_laplace_dists(values, first_origin=3)
    changed = online_laplace_dists([*values[:3], 999.0, values[4]], first_origin=3)
    assert len(original) == 2
    assert original[0].to_dict() == changed[0].to_dict()


def test_source_archive_is_byte_reproducible(tmp_path):
    source = tmp_path / "source.csv"
    source.write_bytes(b"V1,V2\nH1,1\n")
    first = tmp_path / "first.tar.gz"
    second = tmp_path / "second.tar.gz"
    first_manifest = archive_source(first, source)
    second_manifest = archive_source(second, source)
    assert first.read_bytes() == second.read_bytes()
    assert first_manifest == second_manifest
    assert first_manifest["files"][0]["sha256"]


def test_registry_exposes_tirex2_without_loading_model():
    assert "TiRex-2" in aa.make_registry()
