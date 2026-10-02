"""Reproducible TiRex-2 benchmark for skaters Issue #138.

The protocol is deliberately narrow: the first 24 eligible series in the frozen
M4-hourly source, context 128, one-step forecasts, 64 chronological validation
origins followed by 64 untouched test origins. TiRex-2 and a reset-per-origin
Laplace comparator see exactly the same context. Full-history online Laplace is
reported separately as the deployment-oriented baseline.

TiRex-2 exposes q10..q90. A Gaussian-mixture bandwidth is selected only from
validation quantiles and then frozen for test density scoring. Raw quantiles and
canonical per-step score rows are both persisted; summaries are reloaded from
those persisted files rather than from in-memory scores.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import sys
import tarfile
import time
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import arm_adapters as aa
import corpus
from predictions import PredictionWriter, load, mean_scores, pairwise_record
from skaters.api import laplace

SCHEMA = "tirex2-issue138-v1"
STUDY = "issue138:m4-hourly"
LEVELS = tuple(i / 10.0 for i in range(1, 10))
DENSITY_CANDIDATES = (0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0)
LL_FLOOR = -20.0
M4_HOURLY_SHA256 = "ea59b7783573c49077a835ab6465c7d66f1474783360f310988a9a737fbca62f"
M4_HOURLY_BYTES = 2_347_115
RAW_SCHEMA = [
    "study", "series", "split", "step", "origin", "y",
    *[f"q{int(level * 100):02d}" for level in LEVELS],
    "density_spacing_multiplier", "raw_logpdf",
]
METHODS = ("laplace", "Laplace-fixed-context", "TiRex-2")


def sha256_file(path: str | os.PathLike[str]) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _write_json(path: str | os.PathLike[str], value: Any) -> None:
    Path(path).write_bytes(_json_bytes(value))


def _f17(value: float) -> str:
    return format(float(value), ".17g")


def _require_new(paths: Iterable[str | os.PathLike[str]]) -> None:
    existing = [str(path) for path in paths if Path(path).exists()]
    if existing:
        raise FileExistsError("refusing to overwrite existing outputs: " + ", ".join(existing))


def load_m4_panel(
    cache_path: str | os.PathLike[str],
    *,
    n_series: int,
    context_length: int,
    validation_length: int,
    test_length: int,
    max_history: int,
) -> list[dict[str, Any]]:
    """Load the deterministic leading M4-hourly panel from frozen source bytes."""
    source = Path(cache_path)
    if not source.is_file():
        raise FileNotFoundError(f"missing frozen M4-hourly source: {source}")
    if source.stat().st_size != M4_HOURLY_BYTES or sha256_file(source) != M4_HOURLY_SHA256:
        raise ValueError("frozen M4-hourly source checksum/size mismatch")
    corpus._M4_CACHE = str(source)
    needed = context_length + validation_length + test_length
    panel: list[dict[str, Any]] = []
    for series, title, changes in corpus.iter_arm("m4-hourly"):
        values = np.asarray(changes[-max_history:], dtype=float)
        if len(values) < needed or not np.all(np.isfinite(values)):
            continue
        panel.append({"series": str(series), "title": str(title), "values": values})
        if len(panel) == n_series:
            break
    if len(panel) != n_series:
        raise ValueError(f"requested {n_series} qualifying series, found {len(panel)}")
    return panel


def build_origins(
    panel: Sequence[Mapping[str, Any]],
    *,
    context_length: int,
    validation_length: int,
    test_length: int,
) -> tuple[list[dict[str, Any]], np.ndarray]:
    """Create chronological validation/test origins without target leakage."""
    origins: list[dict[str, Any]] = []
    contexts: list[np.ndarray] = []
    for item in panel:
        values = np.asarray(item["values"], dtype=float)
        first = len(values) - validation_length - test_length
        for origin in range(first, len(values)):
            split = "validation" if origin < len(values) - test_length else "test"
            split_start = first if split == "validation" else len(values) - test_length
            context = values[origin - context_length:origin]
            if len(context) != context_length:
                raise ValueError(f"short context for {item['series']} at {origin}")
            origins.append({
                "series": str(item["series"]),
                "split": split,
                "step": origin - split_start,
                "origin": origin,
                "y": float(values[origin]),
            })
            contexts.append(context.astype(np.float32, copy=False))
    return origins, np.stack(contexts)


def select_density_multiplier(
    origins: Sequence[Mapping[str, Any]],
    quantiles: np.ndarray,
    candidates: Sequence[float] = DENSITY_CANDIDATES,
) -> tuple[float, dict[str, Any]]:
    """Select one global bandwidth by equal-series validation mean log score."""
    if len(origins) != len(quantiles):
        raise ValueError("origin/quantile length mismatch")
    validation = [(origin, row) for origin, row in zip(origins, quantiles)
                  if origin["split"] == "validation"]
    if not validation:
        raise ValueError("no validation origins")
    candidate_scores: dict[str, float] = {}
    for candidate in candidates:
        by_series: dict[str, list[float]] = {}
        for origin, row in validation:
            dist = aa.fixed_bandwidth_quantile_dist(
                LEVELS, row, spacing_multiplier=float(candidate)
            )
            logpdf = float(dist.logpdf(float(origin["y"])))
            by_series.setdefault(str(origin["series"]), []).append(
                max(logpdf, LL_FLOOR) if math.isfinite(logpdf) else LL_FLOOR
            )
        candidate_scores[str(candidate)] = float(np.mean([
            np.mean(values) for values in by_series.values()
        ]))
    selected = max((float(candidate) for candidate in candidates),
                   key=lambda candidate: candidate_scores[str(candidate)])
    return selected, {
        "kind": "fixed-bandwidth Gaussian-mixture reconstruction",
        "selection_split": "validation",
        "criterion": f"equal-series mean logpdf with floor {LL_FLOOR:g}",
        "candidate_multipliers": [float(value) for value in candidates],
        "candidate_scores": candidate_scores,
        "selected_multiplier": selected,
        "selection_rows": len(validation),
        "selection_series": len({str(origin["series"]) for origin, _ in validation}),
        "quantile_levels": list(LEVELS),
    }


def online_laplace_dists(values: Sequence[float], first_origin: int) -> list[Any]:
    """Return causal one-step Laplace forecasts from ``first_origin`` onward."""
    forecaster = laplace(1)
    state = None
    pending = None
    output: list[Any] = []
    for index, value in enumerate(values):
        if pending is not None and index >= first_origin:
            output.append(pending[0])
        pending, state = forecaster(float(value), state)
    expected = len(values) - first_origin
    if len(output) != expected:
        raise ValueError(f"Laplace produced {len(output)} forecasts, expected {expected}")
    return output


def fixed_context_laplace_dist(context: Sequence[float]) -> Any:
    """Reset Laplace and return the next forecast after exactly one context."""
    forecaster = laplace(1)
    state = None
    prediction = None
    for value in context:
        prediction, state = forecaster(float(value), state)
    if prediction is None:
        raise ValueError("empty context")
    return prediction[0]


def write_raw_quantiles(
    path: str | os.PathLike[str],
    origins: Sequence[Mapping[str, Any]],
    quantiles: np.ndarray,
    spacing_multiplier: float,
) -> None:
    with open(path, "x", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(RAW_SCHEMA)
        for origin, row in zip(origins, quantiles):
            dist = aa.fixed_bandwidth_quantile_dist(
                LEVELS, row, spacing_multiplier=spacing_multiplier
            )
            raw_logpdf = float(dist.logpdf(float(origin["y"])))
            writer.writerow([
                STUDY,
                origin["series"],
                origin["split"],
                origin["step"],
                origin["origin"],
                _f17(origin["y"]),
                *[_f17(value) for value in row],
                _f17(spacing_multiplier),
                _f17(raw_logpdf),
            ])


def write_canonical_predictions(
    path: str | os.PathLike[str],
    panel: Sequence[Mapping[str, Any]],
    origins: Sequence[Mapping[str, Any]],
    contexts: np.ndarray,
    quantiles: np.ndarray,
    spacing_multiplier: float,
    *,
    validation_length: int,
    test_length: int,
) -> None:
    by_series_origins: dict[str, list[int]] = {}
    for index, origin in enumerate(origins):
        by_series_origins.setdefault(str(origin["series"]), []).append(index)
    writer = PredictionWriter(str(path))
    try:
        for item in panel:
            series = str(item["series"])
            values = np.asarray(item["values"], dtype=float)
            first_origin = len(values) - validation_length - test_length
            full = online_laplace_dists(values, first_origin)[-test_length:]
            indices = [index for index in by_series_origins[series]
                       if origins[index]["split"] == "test"]
            if len(indices) != test_length or len(full) != test_length:
                raise ValueError(f"incomplete test rows for {series}")
            for step, (index, full_dist) in enumerate(zip(indices, full)):
                origin = origins[index]
                fixed_dist = fixed_context_laplace_dist(contexts[index])
                tirex_dist = aa.fixed_bandwidth_quantile_dist(
                    LEVELS,
                    quantiles[index],
                    spacing_multiplier=spacing_multiplier,
                )
                y = float(origin["y"])
                writer.step(STUDY, series, "laplace", step, y, dist=full_dist,
                            floor=LL_FLOOR)
                writer.step(STUDY, series, "Laplace-fixed-context", step, y,
                            dist=fixed_dist, floor=LL_FLOOR)
                writer.step(STUDY, series, "TiRex-2", step, y, dist=tirex_dist,
                            floor=LL_FLOOR)
            writer.flush()
    finally:
        writer.close()


def _load_raw_quantiles(path: str | os.PathLike[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with open(path, newline="") as fh:
        for row in csv.DictReader(fh):
            rows.append({
                **row,
                "step": int(row["step"]),
                "origin": int(row["origin"]),
                "y": float(row["y"]),
                "quantiles": np.asarray([float(row[f"q{int(level * 100):02d}"])
                                          for level in LEVELS]),
                "raw_logpdf": float(row["raw_logpdf"]),
            })
    return rows


def summarize_persisted(
    predictions_path: str | os.PathLike[str],
    raw_path: str | os.PathLike[str],
) -> dict[str, Any]:
    """Derive all reported scores from the two persisted row stores."""
    loaded = load(str(predictions_path))
    scores = mean_scores(loaded, floor=LL_FLOOR)
    series = sorted({name for name, _ in loaded})
    methods = sorted({method for _, method in loaded})
    expected = {(name, method) for name in series for method in METHODS}
    if set(loaded) != expected:
        missing = sorted(expected - set(loaded))
        extra = sorted(set(loaded) - expected)
        raise ValueError(f"canonical method coverage mismatch; missing={missing}, extra={extra}")
    by_series: dict[str, dict[str, Any]] = {}
    for name in series:
        by_series[name] = {
            method: scores[(name, method)] for method in methods
        }
    overall: dict[str, Any] = {}
    for method in methods:
        method_rows = [scores[(name, method)] for name in series]
        coverage = [float(np.mean((loaded[(name, method)]["y"] >= loaded[(name, method)]["q05"])
                                  & (loaded[(name, method)]["y"] <= loaded[(name, method)]["q95"])))
                    for name in series]
        overall[method] = {
            "aggregation": "equal-series mean",
            "logpdf": float(np.mean([row["logpdf"] for row in method_rows])),
            "crps": float(np.mean([row["crps"] for row in method_rows])),
            "central_90_coverage": float(np.mean(coverage)),
            "rows": int(sum(row["n"] for row in method_rows)),
            "series": len(series),
        }
    pairwise: dict[str, Any] = {}
    for baseline in ("Laplace-fixed-context", "laplace"):
        dll = np.asarray([
            scores[(name, "TiRex-2")]["logpdf"] - scores[(name, baseline)]["logpdf"]
            for name in series
        ])
        ratios = np.asarray([
            scores[(name, "TiRex-2")]["crps"] / scores[(name, baseline)]["crps"]
            for name in series
        ])
        pairwise[f"TiRex-2_vs_{baseline}"] = {
            "median_dll_a_minus_b": float(np.median(dll)),
            "mean_dll_a_minus_b": float(np.mean(dll)),
            "median_crps_ratio_a_over_b": float(np.median(ratios)),
            "ll_series_wins": int(np.sum(dll > 0.0)),
            "crps_series_wins": int(np.sum(ratios < 1.0)),
            "dm": pairwise_record(loaded, "TiRex-2", baseline),
            "series": len(series),
        }
    raw_rows = [row for row in _load_raw_quantiles(raw_path) if row["split"] == "test"]
    by_level: dict[str, float] = {}
    all_losses: list[float] = []
    for index, level in enumerate(LEVELS):
        losses = []
        for row in raw_rows:
            error = row["y"] - row["quantiles"][index]
            loss = max(level * error, (level - 1.0) * error)
            losses.append(float(loss))
            all_losses.append(float(loss))
        by_level[f"q{int(level * 100):02d}"] = float(np.mean(losses))
    return {
        "by_series": by_series,
        "overall": overall,
        "pairwise": pairwise,
        "quantile_loss": {
            "definition": "mean pinball loss; lower is better",
            "overall": float(np.mean(all_losses)),
            "by_level": by_level,
            "rows": len(raw_rows),
        },
    }


def archive_source(
    output_path: str | os.PathLike[str],
    source_path: str | os.PathLike[str],
) -> dict[str, Any]:
    """Create a byte-reproducible source archive with a self-describing manifest."""
    source = Path(source_path)
    manifest = {
        "schema": "tirex2-issue138-source-v1",
        "files": [{
            "path": "issue138_sources/M4-hourly.csv",
            "bytes": source.stat().st_size,
            "sha256": sha256_file(source),
        }],
    }
    with open(output_path, "xb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as zipped:
            with tarfile.open(mode="w", fileobj=zipped, format=tarfile.PAX_FORMAT) as archive:
                source_info = tarfile.TarInfo("issue138_sources/M4-hourly.csv")
                source_info.size = source.stat().st_size
                source_info.mtime = source_info.uid = source_info.gid = 0
                source_info.uname = source_info.gname = ""
                with open(source, "rb") as source_fh:
                    archive.addfile(source_info, source_fh)
                payload = _json_bytes(manifest)
                manifest_info = tarfile.TarInfo("issue138_sources/SOURCE_MANIFEST.json")
                manifest_info.size = len(payload)
                manifest_info.mtime = manifest_info.uid = manifest_info.gid = 0
                manifest_info.uname = manifest_info.gname = ""
                import io
                archive.addfile(manifest_info, io.BytesIO(payload))
    return manifest


def dependency_versions() -> dict[str, str | None]:
    versions: dict[str, str | None] = {}
    for package in ("numpy", "torch", "tirex-2", "xlstm", "flashrnn", "huggingface-hub"):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = None
    return versions


def source_tree_manifest() -> dict[str, Any]:
    """Hash every local source and lock file that determines benchmark output."""
    root = Path(__file__).resolve().parents[1]
    paths = [
        root / "benchmarks" / name
        for name in (
            "tirex2_issue138.py",
            "tirex2_requirements.lock",
            "arm_adapters.py",
            "foundation_study.py",
            "predictions.py",
            "corpus.py",
            "fred.py",
        )
    ]
    paths.append(root / "pyproject.toml")
    paths.extend(sorted((root / "src" / "skaters").rglob("*.py")))
    files = {
        path.relative_to(root).as_posix(): {
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in paths
        if path.is_file()
    }
    payload = json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
    return {
        "sha256": hashlib.sha256(payload).hexdigest(),
        "files": files,
    }


def checkpoint_metadata(model_id: str, revision: str) -> dict[str, Any]:
    from huggingface_hub import snapshot_download

    snapshot = Path(snapshot_download(
        repo_id=model_id,
        revision=revision,
        allow_patterns=["model.ckpt", "model-config.yaml"],
        local_files_only=True,
    ))
    weights = snapshot / "model.ckpt"
    config = snapshot / "model-config.yaml"
    return {
        "model": model_id,
        "revision": revision,
        "checkpoint_file": weights.name,
        "checkpoint_bytes": weights.stat().st_size,
        "checkpoint_sha256": sha256_file(weights),
        "config_sha256": sha256_file(config),
    }


def validate_protocol(
    protocol: Mapping[str, Any],
    *,
    n_series: int,
    context_length: int,
    validation_length: int,
    test_length: int,
    max_history: int,
    batch_size: int,
    device: str,
    model_id: str,
    revision: str,
) -> None:
    """Reject any frozen protocol that disagrees with executed inference."""
    expected_top_level = {
        "schema": SCHEMA,
        "series": n_series,
        "context_length": context_length,
        "validation_length": validation_length,
        "test_length": test_length,
        "max_history": max_history,
        "horizon": 1,
        "model": model_id,
        "model_revision": revision,
        "quantile_levels": list(LEVELS),
        "covariates": "none",
    }
    for key, expected in expected_top_level.items():
        if protocol.get(key) != expected:
            raise ValueError(
                f"protocol {key}={protocol.get(key)!r}, expected {expected!r}"
            )
    expected_nested = {
        "test_time_augmentation": {
            "tta_sign_flip": False,
            "tta_diff": False,
        },
        "runtime": {
            "device": device,
            "batch_size": batch_size,
        },
        "splits": {
            "validation": (
                f"{validation_length} origins immediately before the test window"
            ),
            "test": (
                f"final {test_length} origins, not used for density selection"
            ),
            "target_exclusion": (
                "Each model input ends immediately before the realized target."
            ),
        },
    }
    for key, expected in expected_nested.items():
        if protocol.get(key) != expected:
            raise ValueError(
                f"protocol {key}={protocol.get(key)!r}, expected {expected!r}"
            )
    source = protocol.get("source")
    if not isinstance(source, Mapping):
        raise ValueError("protocol source must be an object")
    expected_source = {
        "bytes": M4_HOURLY_BYTES,
        "sha256": M4_HOURLY_SHA256,
        "selection": (
            f"First {n_series} qualifying rows in source order after the "
            "repository's causal level-to-change transform."
        ),
        "preprocessing": (
            f"Use at most the final {max_history} changes per series. Strictly "
            "positive levels become log differences; otherwise first differences, "
            "matching benchmarks/corpus.py."
        ),
    }
    for key, expected in expected_source.items():
        if source.get(key) != expected:
            raise ValueError(
                f"protocol source.{key}={source.get(key)!r}, expected {expected!r}"
            )
    density = protocol.get("density_reconstruction")
    if not isinstance(density, Mapping):
        raise ValueError("protocol density_reconstruction must be an object")
    candidates = density.get("candidate_spacing_multipliers")
    if candidates != list(DENSITY_CANDIDATES):
        raise ValueError(
            f"protocol density candidates={candidates!r}, "
            f"expected {list(DENSITY_CANDIDATES)!r}"
        )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--m4-cache", default=corpus._M4_CACHE)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--raw-quantiles", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--source-archive", required=True)
    parser.add_argument("--series", type=int, default=24)
    parser.add_argument("--context", type=int, default=128)
    parser.add_argument("--validation", type=int, default=64)
    parser.add_argument("--test", type=int, default=64)
    parser.add_argument("--max-history", type=int, default=1000)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--model", default=aa.TIREX2_MODEL_ID)
    parser.add_argument("--revision", default=aa.TIREX2_MODEL_REVISION)
    args = parser.parse_args(argv)

    outputs = [args.output, args.raw_quantiles, args.summary, args.manifest,
               args.source_archive]
    _require_new(outputs)
    protocol_path = Path(args.protocol)
    if not protocol_path.is_file():
        raise FileNotFoundError(f"missing frozen protocol: {protocol_path}")
    protocol = json.loads(protocol_path.read_text())
    validate_protocol(
        protocol,
        n_series=args.series,
        context_length=args.context,
        validation_length=args.validation,
        test_length=args.test,
        max_history=args.max_history,
        batch_size=args.batch_size,
        device=args.device,
        model_id=args.model,
        revision=args.revision,
    )

    started = time.time()
    panel = load_m4_panel(
        args.m4_cache,
        n_series=args.series,
        context_length=args.context,
        validation_length=args.validation,
        test_length=args.test,
        max_history=args.max_history,
    )
    origins, contexts = build_origins(
        panel,
        context_length=args.context,
        validation_length=args.validation,
        test_length=args.test,
    )
    aa.DEVICE = args.device
    inference_started = time.perf_counter()
    quantiles = aa.tirex2_quantiles_from_contexts(
        contexts,
        model_id=args.model,
        revision=args.revision,
        batch_size=args.batch_size,
    )
    inference_seconds = time.perf_counter() - inference_started
    selected, density = select_density_multiplier(origins, quantiles)
    write_raw_quantiles(args.raw_quantiles, origins, quantiles, selected)
    write_canonical_predictions(
        args.output,
        panel,
        origins,
        contexts,
        quantiles,
        selected,
        validation_length=args.validation,
        test_length=args.test,
    )
    source_manifest = archive_source(args.source_archive, args.m4_cache)
    evaluation = summarize_persisted(args.output, args.raw_quantiles)
    checkpoint = checkpoint_metadata(args.model, args.revision)
    finished = time.time()

    summary = {
        "schema": SCHEMA,
        "protocol_sha256": sha256_file(protocol_path),
        "protocol": protocol,
        "density_reconstruction": density,
        "evaluation": evaluation,
        "persistence": {
            "canonical_scores": Path(args.output).name,
            "canonical_precision": "six decimal places",
            "raw_quantiles": Path(args.raw_quantiles).name,
            "raw_quantile_precision": "17 significant digits",
            "score_source": "canonical persisted CSV",
            "quantile_score_source": "persisted raw-quantile CSV",
        },
        "limitations": protocol.get("limitations", []),
    }
    _write_json(args.summary, summary)
    manifest = {
        "schema": SCHEMA,
        "started": started,
        "finished": finished,
        "duration_seconds": max(0.0, finished - started),
        "inference_seconds": inference_seconds,
        "runtime": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "device": args.device,
            "batch_size": args.batch_size,
            "dependencies": dependency_versions(),
        },
        "source_tree": source_tree_manifest(),
        "model": checkpoint,
        "source": {
            "path": Path(args.m4_cache).name,
            "bytes": Path(args.m4_cache).stat().st_size,
            "sha256": sha256_file(args.m4_cache),
            "archive": Path(args.source_archive).name,
            "archive_manifest": source_manifest,
        },
        "protocol": {
            "path": protocol_path.name,
            "sha256": sha256_file(protocol_path),
        },
        "panel": {
            "series": [item["series"] for item in panel],
            "n_series": len(panel),
            "context_length": args.context,
            "validation_length": args.validation,
            "test_length": args.test,
            "horizon": 1,
            "max_history": args.max_history,
        },
        "outputs": {
            Path(args.output).name: sha256_file(args.output),
            Path(args.raw_quantiles).name: sha256_file(args.raw_quantiles),
            Path(args.summary).name: sha256_file(args.summary),
            Path(args.source_archive).name: sha256_file(args.source_archive),
        },
    }
    _write_json(args.manifest, manifest)
    print(json.dumps({
        "schema": SCHEMA,
        "series": len(panel),
        "validation_rows": sum(origin["split"] == "validation" for origin in origins),
        "test_rows": sum(origin["split"] == "test" for origin in origins),
        "canonical_rows": len(panel) * args.test * len(METHODS),
        "selected_density_multiplier": selected,
        "inference_seconds": inference_seconds,
        "summary": summary["evaluation"]["pairwise"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
