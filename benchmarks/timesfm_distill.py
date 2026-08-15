"""Optional TimesFM 2.5 LoRA quantile distillation benchmark.

The module deliberately keeps imports at the boundary: importing it and using the
small record/metric helpers does not import torch, transformers, or peft.  The
training path is optional and consumes ``laplace-distill-v1`` JSONL records.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import platform
import random
import time
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

try:
    import numpy as np
except ImportError:  # optional for pure import/record validation
    np = None

MODEL_ID = "google/timesfm-2.5-200m-transformers"
MODEL_REVISION = "5a9806b9b291fad9233b5249d88263f1846304d3"
METHODS = (
    "laplace",
    "Laplace-fixed-context",
    "Laplace-gmm-body",
    "Laplace-q-fixed-bandwidth",
    "TimesFM-zero-shot",
    "TimesFM-laplace-qd",
)
LEVELS = tuple(i / 10.0 for i in range(1, 10))
RECONSTRUCTION_MULTIPLIERS = (0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0)
RAW_QUANTILE_SCHEMA = [
    "study",
    "series",
    "method",
    "step",
    "y",
    "mean",
    *(f"q{i}" for i in range(10, 100, 10)),
    "raw_logpdf",
    "reconstruction_multiplier",
]
DEFAULT_CONTEXT = 128
DEFAULT_HORIZON = 1
LL_FLOOR = -20.0
SCHEMA = "laplace-distill-v1"


class OptionalDependencyError(RuntimeError):
    """Raised when a train/evaluate command needs an absent optional package."""


def _need_numpy() -> Any:
    if np is None:
        raise OptionalDependencyError("TimesFM numerical helpers require optional numpy")
    return np


def _attr(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _prediction_array(output: Any, preserve_torch: bool = False) -> Any:
    """Find a prediction tensor in common Transformers/TimesFM output objects."""
    if isinstance(output, np.ndarray):
        return output
    if hasattr(output, "detach"):
        return output if preserve_torch else output.detach().cpu().numpy()
    for name in ("full_predictions", "quantile_forecast", "predictions", "sequences", "output"):
        value = _attr(output, name)
        if value is not None:
            return _prediction_array(value, preserve_torch)
    if isinstance(output, Mapping):
        for value in output.values():
            try:
                arr = np.asarray(value)
            except Exception:
                continue
            if arr.ndim:
                return arr
    return np.asarray(output)




def _rows(arr: Any, preserve_torch: bool = False) -> Any:
    """Select the requested one-step horizon without detaching torch tensors."""
    if preserve_torch and hasattr(arr, "ndim") and hasattr(arr, "unsqueeze"):
        if arr.ndim == 0:
            raise ValueError("prediction output must have a channel dimension")
        if arr.ndim == 1:
            return arr.unsqueeze(0)
        return arr[:, DEFAULT_HORIZON - 1, ...] if arr.ndim > 2 else arr
    arr = np.asarray(arr)
    if arr.ndim == 0:
        raise ValueError("prediction output must have a channel dimension")
    if arr.ndim == 1:
        return arr[None, :]
    return arr[:, DEFAULT_HORIZON - 1, ...] if arr.ndim > 2 else arr
def extract_mean_quantiles(output: Any, config: Any = None, *, preserve_torch: bool = False) -> tuple[Any, Any]:
    """Extract one-step mean and ordered q10..q90 from a TimesFM output.

    Hugging Face TimesFM stores the point forecast inside ``full_predictions``
    at ``config.decode_index``.  The remaining channels, in their existing
    order, are the configured quantiles.  Only explicit output fields are
    accepted so an unrelated tensor cannot silently acquire this contract.
    """
    _need_numpy()
    full = _attr(output, "full_predictions", None)
    if full is not None:
        decode_index = _attr(config, "decode_index", None)
        if isinstance(decode_index, bool) or not isinstance(decode_index, int):
            raise ValueError("TimesFM config must define an integer decode_index")
        arr = _rows(_prediction_array(full, preserve_torch), preserve_torch)
        expected_channels = len(LEVELS) + 1
        if arr.shape[-1] != expected_channels:
            raise ValueError(
                f"TimesFM full_predictions must contain exactly {expected_channels} channels"
            )
        if not 0 <= decode_index < expected_channels:
            raise ValueError("TimesFM decode_index is outside full_predictions")
        quantile_indices = [i for i in range(expected_channels) if i != decode_index]
        quantiles = arr[:, quantile_indices]

        explicit_mean = _attr(output, "mean_predictions", None)
        if explicit_mean is None:
            mean = arr[:, decode_index]
        else:
            mean_rows = _rows(
                _prediction_array(explicit_mean, preserve_torch), preserve_torch
            )
            if mean_rows.shape[0] != arr.shape[0] or mean_rows.shape[-1] < 1:
                raise ValueError("TimesFM mean_predictions shape does not match full_predictions")
            mean = mean_rows[:, 0]
        if preserve_torch and hasattr(arr, "device"):
            return mean, quantiles
        return np.asarray(mean, dtype=float), np.asarray(quantiles, dtype=float)

    mean = _attr(output, "mean_predictions", None)
    if mean is None:
        mean = _attr(output, "point_forecast", None)
    quantiles = _attr(output, "quantile_forecast", None)
    if quantiles is None:
        quantiles = _attr(output, "quantiles", None)
    if mean is None or quantiles is None:
        raise ValueError(
            "TimesFM output must expose full_predictions or explicit mean and quantile fields"
        )
    mean_rows = _rows(_prediction_array(mean, preserve_torch), preserve_torch)
    qarr = _rows(_prediction_array(quantiles, preserve_torch), preserve_torch)
    if qarr.shape[-1] != len(LEVELS):
        raise ValueError("TimesFM quantile field must contain exactly nine channels")
    if mean_rows.shape[0] != qarr.shape[0] or mean_rows.shape[-1] < 1:
        raise ValueError("TimesFM mean and quantile field shapes do not match")
    m = mean_rows[:, 0]
    if preserve_torch and hasattr(qarr, "device"):
        return m, qarr
    return np.asarray(m, dtype=float), np.asarray(qarr, dtype=float)


def isotonic_projection(values: Any) -> np.ndarray:
    _need_numpy()
    """Project each row onto nondecreasing quantiles using the PAVA algorithm."""
    x = np.asarray(values, dtype=float)
    if x.ndim == 1:
        x = x[None, :]
        one = True
    elif x.ndim == 2:
        one = False
    else:
        raise ValueError("quantiles must be a vector or a matrix")
    if not np.isfinite(x).all():
        raise ValueError("quantiles must be finite")
    out = np.empty_like(x)
    for r, row in enumerate(x):
        block_values: list[float] = []
        block_weights: list[int] = []
        for value in row:
            block_values.append(float(value)); block_weights.append(1)
            while len(block_values) >= 2 and block_values[-2] > block_values[-1]:
                w = block_weights[-2] + block_weights[-1]
                v = (block_values[-2] * block_weights[-2] + block_values[-1] * block_weights[-1]) / w
                block_values[-2:] = [v]; block_weights[-2:] = [w]
        pos = 0
        for value, weight in zip(block_values, block_weights):
            out[r, pos : pos + weight] = value; pos += weight
    return out[0] if one else out


def _context_scales(context: Any, n: int) -> np.ndarray:
    c = np.asarray(context, dtype=float)
    if c.ndim == 1:
        c = c[None, :]
    if c.ndim != 2 or c.shape[0] != n:
        raise ValueError(f"context must have shape ({n}, context_length)")
    if c.shape[1] == 0:
        return np.ones(n)
    med = np.median(c, axis=1)
    scale = 1.4826 * np.median(np.abs(c - med[:, None]), axis=1)
    # A constant context still has a valid normalized objective; avoid division
    # by zero without allowing tiny scales to dominate optimization.
    return np.maximum(np.where(np.isfinite(scale), scale, 0.0), 1e-6)


def normalized_huber_loss(predicted: Any, target: Any, context: Any, delta: float = 1.0) -> float:
    _need_numpy()
    """Mean Huber error after per-context robust (MAD) scale normalization."""
    p = np.asarray(predicted, dtype=float); t = np.asarray(target, dtype=float)
    if p.shape != t.shape:
        raise ValueError(f"predicted and target shapes differ: {p.shape} != {t.shape}")
    if p.ndim == 1:
        p = p[None, :]; t = t[None, :]
    if p.ndim != 2 or p.shape[0] == 0:
        raise ValueError("predicted and target must be non-empty vectors/matrices")
    if delta <= 0:
        raise ValueError("delta must be positive")
    scale = _context_scales(context, p.shape[0])
    e = np.abs((p - t) / scale[:, None])
    loss = np.where(e <= delta, 0.5 * e * e, delta * (e - 0.5 * delta))
    return float(np.mean(loss))


def teacher_loss(predicted: Any, target: Any, contexts: Any, delta: float = 1.0) -> float:
    """Named seam used by training and tests (teacher target excludes realized y)."""
    return normalized_huber_loss(predicted, target, contexts, delta)


def validate_series_disjoint(records: Sequence[Mapping[str, Any]]) -> None:
    """Require each series id to occur in exactly one train/validation/test split."""
    splits: dict[str, set[str]] = defaultdict(set)
    for rec in records:
        if rec.get("schema") not in (None, SCHEMA):
            raise ValueError(f"unsupported schema: {rec.get('schema')!r}")
        sid = str(rec.get("series", "")); split = rec.get("split")
        if not sid or split not in {"train", "validation", "test"}:
            raise ValueError("record requires series and split=train|validation|test")
        splits[sid].add(str(split))
    bad = {s: sorted(v) for s, v in splits.items() if len(v) != 1}
    if bad:
        raise ValueError(f"series occur in multiple splits: {bad}")


def validate_records(records: Sequence[Mapping[str, Any]], context_length: int | None = None) -> None:
    """Apply the canonical teacher audit at every train/evaluate boundary."""
    if not records:
        raise ValueError("records must not be empty")
    if context_length is None:
        try:
            lengths = {len(record["context"]) for record in records}
        except (KeyError, TypeError) as exc:
            raise ValueError("each record requires a context list") from exc
        if len(lengths) != 1:
            raise ValueError(f"records have inconsistent context lengths: {sorted(lengths)}")
        context_length = lengths.pop()
    try:
        from laplace_distill import audit_records
    except ImportError:
        from benchmarks.laplace_distill import audit_records
    audit_records(records, context_length)


def records_sha256(records: Iterable[Mapping[str, Any]]) -> str:
    records = list(records)
    try:
        from laplace_distill import fingerprint_records
    except ImportError:
        try:
            from benchmarks.laplace_distill import fingerprint_records
        except ImportError:
            fingerprint_records = None
    if fingerprint_records is not None:
        return str(fingerprint_records(records))
    payload = "\n".join(json.dumps(r, sort_keys=True, separators=(",", ":")) for r in records).encode()
    return hashlib.sha256(payload).hexdigest()


def select_device(torch: Any) -> tuple[Any, Any]:
    """Select CUDA, then MPS, then CPU, always using float32 off CUDA."""
    if torch.cuda.is_available():
        return torch.device("cuda"), torch.float32
    mps = getattr(getattr(torch, "backends", None), "mps", None)
    if mps is not None and mps.is_available():
        return torch.device("mps"), torch.float32
    return torch.device("cpu"), torch.float32


def disable_positivity_inference(config: Any) -> Any:
    """Disable change-stream positivity transforms where a TimesFM config exposes one."""
    for name in ("infer_is_positive", "is_positive", "use_positive", "force_positive", "enforce_positive"):
        if hasattr(config, name):
            setattr(config, name, False)
        elif isinstance(config, dict) and name in config:
            config[name] = False
    return config


def _require_optional() -> tuple[Any, Any, Any]:
    try:
        import torch
        from transformers import TimesFm2_5ModelForPrediction
        from peft import LoraConfig, get_peft_model, PeftModel
    except ImportError as exc:
        raise OptionalDependencyError(
            "TimesFM distillation requires torch, transformers (TimesFm2_5ModelForPrediction), and peft; "
            "install the optional benchmark dependencies"
        ) from exc
    return torch, TimesFm2_5ModelForPrediction, (LoraConfig, get_peft_model, PeftModel)


def set_deterministic_seed(seed: int, torch: Any = None) -> None:
    random.seed(seed); np.random.seed(seed)
    if torch is not None:
        torch.manual_seed(seed)
        if hasattr(torch, "cuda"):
            torch.cuda.manual_seed_all(seed)
        if hasattr(torch, "use_deterministic_algorithms"):
            torch.use_deterministic_algorithms(True, warn_only=True)

def source_tree_manifest() -> dict[str, Any]:
    """Return the canonical teacher/student source-tree manifest."""
    try:
        from laplace_distill import source_tree_manifest as build_source_manifest
    except ImportError:
        from benchmarks.laplace_distill import (
            source_tree_manifest as build_source_manifest,
        )
    return build_source_manifest()


def build_manifest(
    *,
    records: Sequence[Mapping[str, Any]],
    model_id: str,
    config: Any,
    seed: int,
    started: float,
    finished: float,
    trainable_parameters: int,
    adapter_path: str | None = None,
    training_settings: Mapping[str, Any] | None = None,
    model_revision: str = MODEL_REVISION,
    device: Any = None,
    dtype: Any = None,
) -> dict[str, Any]:
    config_obj = config.to_dict() if hasattr(config, "to_dict") else config
    config_json = json.dumps(config_obj, sort_keys=True, default=str, separators=(",", ":"))
    import importlib.metadata

    deps = {}
    for package in ("numpy", "torch", "transformers", "peft", "safetensors"):
        try:
            deps[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            deps[package] = None
    context_lengths = {len(r.get("context", ())) for r in records}
    context_length = context_lengths.pop() if len(context_lengths) == 1 else None
    decode_index = _attr(config, "decode_index", None)
    lock_path = Path(__file__).with_name("distill_requirements.lock")
    dependency_lock = (
        {
            "file": lock_path.name,
            "sha256": hashlib.sha256(lock_path.read_bytes()).hexdigest(),
        }
        if lock_path.is_file()
        else None
    )
    return {
        "schema": "timesfm-distill-v2",
        "model": model_id,
        "model_revision": model_revision,
        "seed": int(seed),
        "data_sha256": records_sha256(records),
        "config_sha256": hashlib.sha256(config_json.encode()).hexdigest(),
        "started": started,
        "finished": finished,
        "duration_seconds": max(0.0, finished - started),
        "trainable_parameters": int(trainable_parameters),
        "adapter_path": Path(adapter_path).name if adapter_path else None,
        "context_length": context_length,
        "horizon": DEFAULT_HORIZON,
        "levels": list(LEVELS),
        "output_contract": {
            "mean_field": "mean_predictions",
            "decode_index": decode_index,
            "quantile_channels": [
                i for i in range(len(LEVELS) + 1) if i != decode_index
            ],
        },
        "runtime": {
            "python": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "os": platform.platform(),
            "machine": platform.machine(),
            "device": str(device) if device is not None else None,
            "dtype": str(dtype) if dtype is not None else None,
            "dependencies": deps,
            "dependency_lock": dependency_lock,
        },
        "source_tree": source_tree_manifest(),
        "training": dict(training_settings or {}),
    }


def _teacher_targets(records: Sequence[Mapping[str, Any]]) -> tuple[np.ndarray, np.ndarray]:
    _need_numpy()
    contexts = np.asarray([r["context"] for r in records], dtype=np.float32)
    targets = np.asarray([[r["teacher"]["mean"], *r["teacher"]["quantiles"]] for r in records], dtype=np.float32)
    return contexts, targets


def _num_trainable(model: Any) -> int:
    return int(sum(p.numel() for p in model.parameters() if getattr(p, "requires_grad", False)))


def train_adapter(records: Sequence[Mapping[str, Any]], adapter_dir: str, *, model_id: str = MODEL_ID,
                  model_revision: str = MODEL_REVISION, seed: int = 0, epochs: int = 1,
                  batch_size: int = 8, lr: float = 1e-4,
                  lora_r: int = 4, lora_alpha: int = 8, lora_dropout: float = 0.05,
                  forward_fn: Callable[[Any, Any], Any] | None = None) -> dict[str, Any]:
    """Train LoRA on teacher mean/quantiles only and save adapter + manifest."""
    _need_numpy()
    validate_records(records)
    train = [r for r in records if r["split"] == "train"]
    valid = [r for r in records if r["split"] == "validation"]
    if not train or not valid:
        raise ValueError("both train and validation records are required")
    torch, TimesFmClass, peft = _require_optional()
    LoraConfig, get_peft_model, _ = peft
    started = time.time(); set_deterministic_seed(seed, torch)
    device, dtype = select_device(torch)
    base = TimesFmClass.from_pretrained(model_id, revision=model_revision, torch_dtype=dtype)
    config = disable_positivity_inference(base.config)
    lora = LoraConfig(
        r=lora_r,
        lora_alpha=lora_alpha,
        lora_dropout=lora_dropout,
        target_modules="all-linear",
        revision=model_revision,
    )
    model = get_peft_model(base, lora).to(device); model.train()
    optimizer = torch.optim.AdamW((p for p in model.parameters() if p.requires_grad), lr=lr)
    contexts, targets = _teacher_targets(train)
    val_contexts, val_targets = _teacher_targets(valid)
    best = math.inf; best_epoch = 0
    rng = np.random.default_rng(seed)
    for epoch in range(max(1, epochs)):
        for order in np.array_split(rng.permutation(len(train)), max(1, math.ceil(len(train) / batch_size))):
            if not len(order):
                continue
            xb = torch.as_tensor(contexts[order], dtype=dtype, device=device)
            yb = torch.as_tensor(targets[order], dtype=dtype, device=device)
            raw = forward_fn(model, xb) if forward_fn else model(past_values=xb, forecast_context_len=xb.shape[1])
            mean, quantiles = extract_mean_quantiles(raw, config, preserve_torch=True)
            if not hasattr(mean, "device"):
                mean = torch.as_tensor(mean, dtype=dtype, device=device)
            if not hasattr(quantiles, "device"):
                quantiles = torch.as_tensor(quantiles, dtype=dtype, device=device)
            pred = torch.cat((mean.reshape(-1, 1), quantiles), dim=1)
            loss = _torch_normalized_huber(pred, yb, xb)
            optimizer.zero_grad(); loss.backward(); optimizer.step()
        model.eval()
        val_loss_sum = 0.0
        val_count = 0
        with torch.no_grad():
            for start in range(0, len(valid), batch_size):
                vx = torch.as_tensor(val_contexts[start : start + batch_size], dtype=dtype, device=device)
                vy = torch.as_tensor(val_targets[start : start + batch_size], dtype=dtype, device=device)
                raw = forward_fn(model, vx) if forward_fn else model(past_values=vx, forecast_context_len=vx.shape[1])
                mean, quantiles = extract_mean_quantiles(raw, config, preserve_torch=True)
                if not hasattr(mean, "device"):
                    mean = torch.as_tensor(mean, dtype=dtype, device=device)
                if not hasattr(quantiles, "device"):
                    quantiles = torch.as_tensor(quantiles, dtype=dtype, device=device)
                vp = torch.cat((mean.reshape(-1, 1), quantiles), dim=1)
                n_batch = int(vx.shape[0])
                val_loss_sum += float(_torch_normalized_huber(vp, vy, vx).item()) * n_batch
                val_count += n_batch
        val_loss = val_loss_sum / max(val_count, 1)
        model.train()
        if val_loss < best:
            best = val_loss; best_epoch = epoch + 1
            # PEFT save_pretrained writes only adapter weights/config.
            model.save_pretrained(adapter_dir)
    finished = time.time()
    manifest = build_manifest(
        records=records,
        model_id=model_id,
        model_revision=model_revision,
        config=config,
        seed=seed,
        started=started,
        finished=finished,
        trainable_parameters=_num_trainable(model),
        adapter_path=adapter_dir,
        device=device,
        dtype=dtype,
        training_settings={
            "epochs": int(epochs),
            "selected_epoch": int(best_epoch),
            "best_validation_teacher_loss": float(best),
            "batch_size": int(batch_size),
            "learning_rate": float(lr),
            "loss": "context-MAD-scale Huber",
            "lora_target_modules": "all-linear",
            "lora_r": int(lora_r),
            "lora_alpha": int(lora_alpha),
            "lora_dropout": float(lora_dropout),
        },
    )
    Path(adapter_dir, "run_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest

def _linear_median_indices(width: int) -> tuple[int, int]:
    """Return the two NumPy-compatible middle indices."""
    if width < 1:
        raise ValueError("median width must be positive")
    return (width - 1) // 2, width // 2


def _torch_row_median(values: Any) -> Any:
    """Match NumPy's linear median for even and odd row widths."""
    ordered = values.sort(dim=1).values
    lower, upper = _linear_median_indices(int(ordered.shape[1]))
    return (ordered[:, lower] + ordered[:, upper]) * 0.5


def _torch_normalized_huber(pred: Any, target: Any, context: Any, delta: float = 1.0) -> Any:
    med = _torch_row_median(context)
    scale = (1.4826 * _torch_row_median((context - med[:, None]).abs())).clamp_min(1e-6)
    e = (pred - target).abs() / scale[:, None]
    return torch_where(e <= delta, 0.5 * e * e, delta * (e - 0.5 * delta)).mean()


def load_timesfm_model(model_id: str = MODEL_ID, model_revision: str = MODEL_REVISION,
                       adapter_dir: str | None = None) -> tuple[Any, Any, Any, Any]:
    torch, TimesFmClass, peft = _require_optional()
    _, _, PeftModel = peft
    device, dtype = select_device(torch)
    model = TimesFmClass.from_pretrained(model_id, revision=model_revision, torch_dtype=dtype)
    config = disable_positivity_inference(model.config)
    if adapter_dir:
        model = PeftModel.from_pretrained(model, adapter_dir)
    return model.to(device).eval(), config, device, torch


def infer_test_targets(records: Sequence[Mapping[str, Any]], model: Any, config: Any,
                       device: Any, torch: Any, batch_size: int = 32) -> list[tuple[float, np.ndarray]]:
    """Run deterministic one-step inference, preserving native mean/q channels."""
    _need_numpy()
    contexts = np.asarray([r["context"] for r in records], dtype=np.float32)
    out: list[tuple[float, np.ndarray]] = []
    with torch.no_grad():
        for start in range(0, len(records), batch_size):
            xb = torch.as_tensor(contexts[start : start + batch_size], dtype=torch.float32, device=device)
            mean, quantiles = extract_mean_quantiles(
                model(past_values=xb, forecast_context_len=xb.shape[1]), config
            )
            mean = np.asarray(mean, dtype=float).reshape(-1)
            quantiles = np.asarray(quantiles, dtype=float).reshape(-1, 9)
            out.extend((float(m), q.copy()) for m, q in zip(mean, quantiles))
    return out


def adapter_runtime_size(adapter_dir: str) -> tuple[list[str], int]:
    """Return the stable PEFT files and bytes needed to load the adapter."""
    names = ["adapter_config.json", "adapter_model.safetensors"]
    paths = [Path(adapter_dir, name) for name in names]
    missing = [path.name for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"missing adapter runtime files: {missing}")
    return names, sum(path.stat().st_size for path in paths)


def fixed_context_laplace_predictions(
    records: Sequence[Mapping[str, Any]],
) -> list[Any]:
    """Run a fresh Laplace forecaster on only each record's fixed context."""
    from skaters import laplace

    predictions = []
    for record in records:
        forecaster = laplace(1)
        state = None
        pending = None
        for value in record["context"]:
            emitted, state = forecaster(float(value), state)
            pending = emitted[0] if isinstance(emitted, (list, tuple)) else emitted
        if pending is None:
            raise ValueError("fixed-context Laplace requires a nonempty context")
        predictions.append(pending)
    return predictions


def evaluate_models(
    records: Sequence[Mapping[str, Any]],
    *,
    model_id: str = MODEL_ID,
    model_revision: str = MODEL_REVISION,
    adapter_dir: str,
    output_path: str | None = None,
    quantile_output_path: str | None = None,
    batch_size: int = 32,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Infer base and adapted TimesFM on the same held-out records and score them."""
    validate_records(records)
    reconstruction_multiplier, reconstruction = select_reconstruction_multiplier(records)
    test = [r for r in records if r["split"] == "test"]
    if not test:
        raise ValueError("no test records")
    started = time.perf_counter()
    fixed_context_predictions = fixed_context_laplace_predictions(test)
    fixed_context_seconds = time.perf_counter() - started
    base, config, device, torch = load_timesfm_model(model_id, model_revision)
    warm = torch.as_tensor(
        np.asarray([test[0]["context"]], dtype=np.float32),
        dtype=torch.float32,
        device=device,
    )
    with torch.no_grad():
        base(past_values=warm, forecast_context_len=warm.shape[1])
    started = time.perf_counter()
    base_predictions = infer_test_targets(test, base, config, device, torch, batch_size)
    zero_seconds = time.perf_counter() - started
    del base
    adapted, aconfig, device, torch = load_timesfm_model(
        model_id, model_revision, adapter_dir
    )
    warm = torch.as_tensor(
        np.asarray([test[0]["context"]], dtype=np.float32),
        dtype=torch.float32,
        device=device,
    )
    with torch.no_grad():
        adapted(past_values=warm, forecast_context_len=warm.shape[1])
    started = time.perf_counter()
    adapted_predictions = infer_test_targets(
        test, adapted, aconfig, device, torch, batch_size
    )
    adapted_seconds = time.perf_counter() - started
    predictions = {
        "laplace": [r["teacher"]["predictive"] for r in test],
        "Laplace-fixed-context": fixed_context_predictions,
        "Laplace-gmm-body": [
            r["teacher"]["predictive"].get("body", r["teacher"]["predictive"])
            for r in test
        ],
        "Laplace-q-fixed-bandwidth": [
            (r["teacher"]["mean"], r["teacher"]["quantiles"]) for r in test
        ],
        "TimesFM-zero-shot": base_predictions,
        "TimesFM-laplace-qd": adapted_predictions,
    }
    rows, summary = evaluate_rows(
        test,
        predictions,
        output_path,
        quantile_output_path=quantile_output_path,
        reconstruction_multiplier=reconstruction_multiplier,
        _validated=True,
    )
    adapter_files, adapter_bytes = adapter_runtime_size(adapter_dir)
    native_crossing_rows = {
        "TimesFM-zero-shot": sum(
            bool(np.any(np.diff(np.asarray(quantiles, dtype=float)) < 0.0))
            for _mean, quantiles in base_predictions
        ),
        "TimesFM-laplace-qd": sum(
            bool(np.any(np.diff(np.asarray(quantiles, dtype=float)) < 0.0))
            for _mean, quantiles in adapted_predictions
        ),
    }
    summary["evaluation"] = {
        "schema": "timesfm-distill-evaluation-v2",
        "data_sha256": records_sha256(test),
        "model": model_id,
        "model_revision": model_revision,
        "test_contexts": len(test),
        "batch_size": batch_size,
        "device": str(device),
        "dtype": str(torch.float32),
        "zero_shot_seconds": zero_seconds,
        "fixed_context_laplace_seconds": fixed_context_seconds,
        "distilled_seconds": adapted_seconds,
        "adapter_files": adapter_files,
        "adapter_bytes": adapter_bytes,
        "reconstruction": reconstruction,
        "quantile_postprocessing": {
            "raw_storage": "native q10..q90 channels before ordering repair",
            "scoring": "row-wise PAVA isotonic projection before density reconstruction",
            "native_crossing_rows": native_crossing_rows,
        },
        "source_tree": source_tree_manifest(),
    }
    return rows, summary


def torch_where(condition: Any, a: Any, b: Any) -> Any:
    import torch
    return torch.where(condition, a, b)


def _dist_from_prediction(pred: Any, reconstruction_multiplier: float = 0.5) -> Any:
    from skaters.dist import Dist

    if hasattr(pred, "logpdf") and hasattr(pred, "crps"):
        return pred
    if isinstance(pred, Mapping):
        if "predictive" in pred:
            return Dist.from_dict(pred["predictive"])
        if pred.get("spliced"):
            return Dist.from_dict(pred)
        if "components" in pred:
            return Dist.from_dict(pred)
        if "quantiles" in pred:
            return quantile_dist(
                LEVELS, pred["quantiles"], reconstruction_multiplier
            )
    if isinstance(pred, (tuple, list)) and len(pred) == 2:
        return quantile_dist(LEVELS, pred[1], reconstruction_multiplier)
    raise TypeError("prediction must be a Dist, predictive dict, or (mean, quantiles)")


def quantile_dist(
    levels: Sequence[float],
    quantiles: Sequence[float],
    reconstruction_multiplier: float = 0.5,
) -> Any:
    """Fixed-bandwidth Gaussian mixture from ordered central quantiles."""
    from skaters.dist import Dist

    probabilities = np.asarray(levels, dtype=float).reshape(-1)
    values = np.asarray(quantiles, dtype=float).reshape(-1)
    multiplier = float(reconstruction_multiplier)
    if probabilities.size < 2 or probabilities.size != values.size:
        raise ValueError("levels and quantiles must have the same length of at least two")
    if not np.all(np.isfinite(probabilities)) or not np.all(np.isfinite(values)):
        raise ValueError("levels and quantiles must be finite")
    if not math.isfinite(multiplier) or multiplier <= 0.0:
        raise ValueError("reconstruction_multiplier must be finite and positive")
    order = np.argsort(probabilities)
    probabilities = probabilities[order]
    values = isotonic_projection(values[order])
    if probabilities[0] <= 0.0 or probabilities[-1] >= 1.0:
        raise ValueError("quantile levels must lie strictly between zero and one")
    if np.any(np.diff(probabilities) <= 0.0):
        raise ValueError("quantile levels must be strictly increasing")
    components = []
    for index, value in enumerate(values):
        lower = probabilities[index - 1] if index > 0 else 0.0
        upper = probabilities[index + 1] if index < len(values) - 1 else 1.0
        weight = max((upper - lower) / 2.0, 1e-6)
        if index == 0:
            spacing = abs(values[1] - values[0])
        elif index == len(values) - 1:
            spacing = abs(values[-1] - values[-2])
        else:
            spacing = abs(values[index + 1] - values[index - 1]) / 2.0
        components.append((
            weight,
            float(value),
            max(multiplier * float(spacing), 1e-9),
        ))
    return Dist(components)


def select_reconstruction_multiplier(
    records: Sequence[Mapping[str, Any]],
    candidates: Sequence[float] = RECONSTRUCTION_MULTIPLIERS,
) -> tuple[float, dict[str, Any]]:
    """Select one density bandwidth on validation targets, never test targets."""
    validation = [r for r in records if r.get("split") == "validation"]
    if not validation:
        raise ValueError("validation records are required to select density reconstruction")
    if not candidates:
        raise ValueError("at least one reconstruction multiplier is required")
    scores: dict[float, float] = {}
    for candidate in candidates:
        by_series: dict[str, list[float]] = defaultdict(list)
        for record in validation:
            dist = quantile_dist(
                LEVELS, record["teacher"]["quantiles"], float(candidate)
            )
            raw_logpdf = float(dist.logpdf(float(record["y"])))
            if not math.isfinite(raw_logpdf):
                raise ValueError("density reconstruction produced nonfinite validation logpdf")
            by_series[str(record["series"])].append(max(raw_logpdf, LL_FLOOR))
        scores[float(candidate)] = float(
            np.mean([np.mean(values) for values in by_series.values()])
        )
    selected = max(scores, key=lambda value: (scores[value], -value))
    return selected, {
        "kind": "fixed-bandwidth Gaussian-mixture reconstruction",
        "selection_split": "validation",
        "criterion": f"equal-series mean logpdf with floor {LL_FLOOR:g}",
        "candidate_multipliers": [float(value) for value in candidates],
        "candidate_scores": {f"{key:g}": value for key, value in scores.items()},
        "selected_multiplier": selected,
        "selection_rows": len(validation),
        "selection_series": len({str(r["series"]) for r in validation}),
        "quantile_levels": list(LEVELS),
    }


def _raw_prediction_quantiles(pred: Any) -> tuple[float | None, np.ndarray] | None:
    if isinstance(pred, Mapping) and "quantiles" in pred:
        mean, quantiles = pred.get("mean"), pred["quantiles"]
    elif isinstance(pred, (tuple, list)) and len(pred) == 2:
        mean, quantiles = pred
    else:
        return None
    values = np.asarray(quantiles, dtype=float).reshape(-1)
    if values.size != len(LEVELS):
        raise ValueError("raw prediction must contain exactly nine quantiles")
    return (None if mean is None else float(mean)), values


def _default_quantile_output_path(output_path: str) -> str:
    target = Path(output_path)
    suffix = target.suffix or ".csv"
    return str(target.with_name(f"{target.stem}_raw_quantiles{suffix}"))


def load_persisted_score_rows(path: str | os.PathLike[str]) -> list[dict[str, Any]]:
    """Reload canonical six-decimal score rows for authoritative summarization."""
    rows = []
    with Path(path).open(newline="") as fh:
        for stored in csv.DictReader(fh):
            study = stored["study"]
            regime = study.split(":", 1)[1] if study.startswith("distill:") else study
            rows.append(
                {
                    "series": stored["series"],
                    "regime": regime,
                    "method": stored["method"],
                    "origin": int(float(stored["step"])),
                    "y": float(stored["y"]),
                    "logpdf": float(stored["logpdf"]),
                    "crps": float(stored["crps"]),
                }
            )
    return rows


def evaluate_rows(
    records: Sequence[Mapping[str, Any]],
    predictions: Mapping[str, Sequence[Any]],
    output_path: str | None = None,
    study: str = "timesfm_distill",
    *,
    quantile_output_path: str | None = None,
    reconstruction_multiplier: float = 0.5,
    _validated: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Score all methods on identical targets and persist canonical score rows."""
    _need_numpy()
    if not _validated:
        validate_records(records)
    for method in METHODS:
        if method not in predictions or len(predictions[method]) != len(records):
            raise ValueError(f"predictions for {method} must have exactly one item per record")
    writer = None
    raw_fh = None
    raw_writer = None
    raw_path = None
    if output_path is not None:
        if os.path.exists(output_path):
            raise FileExistsError(
                f"refusing to append duplicate predictions: remove {output_path} first"
            )
        raw_path = quantile_output_path or _default_quantile_output_path(output_path)
        if os.path.exists(raw_path):
            raise FileExistsError(
                f"refusing to overwrite raw quantiles: remove {raw_path} first"
            )
        try:
            from predictions import PredictionWriter
        except ImportError:
            from benchmarks.predictions import PredictionWriter
        writer = PredictionWriter(output_path)
        raw_fh = Path(raw_path).open("x", newline="")
        raw_writer = csv.writer(raw_fh)
        raw_writer.writerow(RAW_QUANTILE_SCHEMA)
    rows: list[dict[str, Any]] = []
    try:
        for i, rec in enumerate(records):
            y = float(rec["y"])
            key = {
                "series": rec["series"],
                "origin": int(rec["origin"]),
                "y": y,
            }
            for method in METHODS:
                # The Laplace baseline is always the exact teacher serialization,
                # never a caller-provided approximation.
                pred = (
                    rec["teacher"]["predictive"]
                    if method == "laplace"
                    else predictions[method][i]
                )
                dist = _dist_from_prediction(pred, reconstruction_multiplier)
                raw_logpdf = float(dist.logpdf(y))
                lp = (
                    max(raw_logpdf, LL_FLOOR)
                    if math.isfinite(raw_logpdf)
                    else LL_FLOOR
                )
                crps = float(dist.crps(y))
                row = {
                    **key,
                    "regime": rec.get("regime", "unknown"),
                    "method": method,
                    "raw_logpdf": raw_logpdf,
                    "logpdf": lp,
                    "crps": crps,
                    "density_kind": (
                        "exact/full-history"
                        if method == "laplace"
                        else "exact/fixed-context"
                        if method == "Laplace-fixed-context"
                        else "diagnostic/exact-body"
                        if method == "Laplace-gmm-body"
                        else "fixed-bandwidth Gaussian-mixture reconstruction"
                    ),
                }
                if method == "laplace":
                    row["predictive"] = rec["teacher"]["predictive"]
                rows.append(row)
                study_name = f"distill:{rec.get('regime', 'unknown')}"
                if writer is not None:
                    writer.step(
                        study_name,
                        rec["series"],
                        method,
                        int(rec["origin"]),
                        y,
                        dist=dist,
                        logpdf=lp,
                        crps=crps,
                        floor=LL_FLOOR,
                    )
                raw_prediction = _raw_prediction_quantiles(pred)
                if raw_writer is not None and raw_prediction is not None:
                    mean, raw_quantiles = raw_prediction
                    raw_writer.writerow(
                        [
                            study_name,
                            rec["series"],
                            method,
                            int(rec["origin"]),
                            format(y, ".17g"),
                            "" if mean is None else format(mean, ".17g"),
                            *(format(float(value), ".17g") for value in raw_quantiles),
                            format(raw_logpdf, ".17g"),
                            format(float(reconstruction_multiplier), ".17g"),
                        ]
                    )
    finally:
        if writer is not None:
            writer.close()
        if raw_fh is not None:
            raw_fh.close()
    score_rows = load_persisted_score_rows(output_path) if output_path else rows
    summary = summarize_scores(score_rows)
    summary["persistence"] = {
        "score_source": "canonical persisted CSV" if output_path else "in-memory",
        "canonical_scores": Path(output_path).name if output_path else None,
        "raw_quantiles": Path(raw_path).name if raw_path else None,
        "canonical_precision": "six decimal places" if output_path else None,
        "raw_quantile_precision": "17 significant digits" if raw_path else None,
    }
    return rows, summary


def summarize_scores(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    _need_numpy()
    """Summarize LL (higher is better) and CRPS (lower is better), incl. pairwise counts."""
    grouped: dict[str, dict[str, list[Mapping[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        grouped[str(row.get("regime", "overall"))][str(row["method"])].append(row)
    def stats(group: Mapping[str, Sequence[Mapping[str, Any]]]) -> dict[str, dict[str, float | int | str]]:
        out_stats = {}
        for method, method_rows in group.items():
            by_series: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
            for row in method_rows:
                by_series[str(row["series"])].append(row)
            ll_by_series = [float(np.mean([r["logpdf"] for r in rs])) for rs in by_series.values()]
            crps_by_series = [float(np.mean([r["crps"] for r in rs])) for rs in by_series.values()]
            out_stats[method] = {
                "ll": float(np.mean(ll_by_series)), "crps": float(np.mean(crps_by_series)),
                "n": len(method_rows), "series": len(by_series),
                "aggregation": "per-series-equal",
            }
        return out_stats
    def paired_stats(group: Mapping[str, Sequence[Mapping[str, Any]]]) -> dict[str, Any]:
        base_rows: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
        for row in group.get("laplace", []):
            base_rows[str(row["series"])].append(row)
        base = {
            series: {
                "logpdf": float(np.mean([r["logpdf"] for r in series_rows])),
                "crps": float(np.mean([r["crps"] for r in series_rows])),
            }
            for series, series_rows in base_rows.items()
        }
        result: dict[str, Any] = {}
        for method in METHODS:
            if method == "laplace":
                continue
            by_series: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
            for row in group.get(method, []):
                by_series[str(row["series"])].append(row)
            dll, ratios = [], []
            for series, method_rows in by_series.items():
                if series not in base:
                    continue
                dll.append(float(np.mean([r["logpdf"] for r in method_rows]) - base[series]["logpdf"]))
                ratios.append(float(np.mean([r["crps"] for r in method_rows]) / max(abs(base[series]["crps"]), 1e-12)))
            result[method] = {
                "median_dll": float(np.median(dll)) if dll else float("nan"),
                "dll_quartiles": [float(x) for x in np.quantile(dll, [0.25, 0.75])] if dll else [float("nan")] * 2,
                "median_crps_ratio": float(np.median(ratios)) if ratios else float("nan"),
            }
        return result

    paired = {regime: paired_stats(group) for regime, group in grouped.items()}

    overall_group: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        overall_group[str(row["method"])].append(row)
    out: dict[str, Any] = {
        "by_regime": {reg: stats(group) for reg, group in grouped.items()},
        "overall": stats(overall_group), "pairwise": {},
    }
    paired["overall"] = paired_stats(overall_group)
    out["paired"] = paired
    for ai, a in enumerate(METHODS):
        for b in METHODS[ai + 1:]:
            wins = {"ll": {a: 0, b: 0, "draw": 0},
                    "crps": {a: 0, b: 0, "draw": 0},
                    "dm": {a: 0, b: 0, "draw": 0}, "n": 0}
            by_series: dict[str, dict[str, list[Mapping[str, Any]]]] = defaultdict(lambda: defaultdict(list))
            dll, crps_ratios = [], []
            for row in rows:
                if row["method"] in (a, b):
                    by_series[str(row["series"])][str(row["method"])].append(row)
            for series_methods in by_series.values():
                if a not in series_methods or b not in series_methods:
                    continue
                av_ll = float(np.mean([r["logpdf"] for r in series_methods[a]]))
                bv_ll = float(np.mean([r["logpdf"] for r in series_methods[b]]))
                av_crps = float(np.mean([r["crps"] for r in series_methods[a]]))
                bv_crps = float(np.mean([r["crps"] for r in series_methods[b]]))
                dll.append(av_ll - bv_ll)
                crps_ratios.append(av_crps / max(abs(bv_crps), 1e-12))
                wins["n"] += 1
                for metric, av, bv, higher in (("ll", av_ll, bv_ll, True),
                                                ("crps", av_crps, bv_crps, False)):
                    winner = (a if (av > bv if higher else av < bv)
                              else b if (bv > av if higher else bv < av) else "draw")
                    wins[metric][winner] += 1
            wins["effect"] = {
                "a": a,
                "b": b,
                "median_dll_a_minus_b": float(np.median(dll)) if dll else float("nan"),
                "median_crps_ratio_a_over_b": float(np.median(crps_ratios)) if crps_ratios else float("nan"),
            }
            try:
                try:
                    from predictions import dm_contest
                except ImportError:
                    from benchmarks.predictions import dm_contest
                for series_methods in by_series.values():
                    if a not in series_methods or b not in series_methods:
                        continue
                    verdict = dm_contest(
                        [r["logpdf"] for r in series_methods[a]],
                        [r["logpdf"] for r in series_methods[b]],
                    )[0]
                    wins["dm"][a if verdict == "A" else b if verdict == "B" else "draw"] += 1
            except ImportError:
                pass
            out["pairwise"][f"{a}_vs_{b}"] = wins
    return out


def _read_jsonl(path: str) -> list[dict[str, Any]]:
    try:
        from laplace_distill import read_jsonl
    except ImportError:
        try:
            from benchmarks.laplace_distill import read_jsonl
        except ImportError:
            read_jsonl = None
    if read_jsonl is not None:
        return read_jsonl(path)
    import gzip
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]
def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("mode", choices=("train", "evaluate", "run"))
    ap.add_argument("--data", required=True)
    ap.add_argument("--adapter", default="timesfm-lora")
    ap.add_argument("--output", default="timesfm_predictions.csv")
    ap.add_argument("--summary", default=None)
    ap.add_argument("--quantiles-output", default=None)
    ap.add_argument("--model", default=MODEL_ID)
    ap.add_argument("--revision", default=MODEL_REVISION)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--epochs", type=int, default=1)
    ap.add_argument("--batch-size", type=int, default=8)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--lora-r", type=int, default=4)
    ap.add_argument("--lora-alpha", type=int, default=8)
    ap.add_argument("--lora-dropout", type=float, default=0.05)
    args = ap.parse_args(argv)
    records = _read_jsonl(args.data)
    if args.mode in ("train", "run"):
        train_adapter(records, args.adapter, model_id=args.model, model_revision=args.revision,
                      seed=args.seed, epochs=args.epochs, batch_size=args.batch_size, lr=args.lr,
                      lora_r=args.lora_r, lora_alpha=args.lora_alpha,
                      lora_dropout=args.lora_dropout)
    if args.mode in ("evaluate", "run"):
        _rows_out, summary = evaluate_models(records, model_id=args.model, model_revision=args.revision,
                                              adapter_dir=args.adapter,
                                              output_path=args.output,
                                              quantile_output_path=args.quantiles_output,
                                              batch_size=args.batch_size)
        summary_path = args.summary or (args.output + ".summary.json")
        Path(summary_path).write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
        print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    main()
