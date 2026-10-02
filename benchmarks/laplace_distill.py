"""Deterministic, dependency-light Laplace teacher corpus builder.

The module deliberately contains no model-training imports.  It records the
online Laplace predictive *before* consuming each target, making each row a
proper one-step teacher example.  Optional model consumers can use the JSONL
schema without importing this module's corpus adapters.
"""
from __future__ import annotations

import argparse
from collections import deque
import csv
import gzip
import hashlib
import io
import json
import math
import os
import platform
import random
import sys
import tarfile
import zlib
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

SCHEMA = "laplace-distill-v1"
LEVELS = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)
SPLITS = ("train", "validation", "test")
DEFAULT_CONTEXT = 128
DEFAULT_HORIZON = 1
LL_FLOOR = -20.0

# Frozen source contract for the eight-series Issue #133 FRED arm.  Generation
# is deliberately offline: every file is checked before any series is yielded.
FRED_CORE_SOURCES = {
    "DGS10": ("2eab94df8804a0e4635030bc3695efbac68bf51622b07242d60a1838eae88c99", 16124, "1962-01-02", "2026-07-23"),
    "DFF": ("818dea0a635c317f7c22ff2a469b8a559fe26ddd62b8b6232c5e3138bbc949f2", 26321, "1954-07-01", "2026-07-23"),
    "VIXCLS": ("2037f86109f6b9c26e657d64d226f3d0703517dc357dfa8f3285819456b15ec0", 9236, "1990-01-02", "2026-07-23"),
    "DCOILWTICO": ("f8ef0d9ff8baf6b61d83735be83516d51c6bb89ae1e0258e6f45578f8772cf71", 10205, "1986-01-02", "2026-07-20"),
    "DEXUSEU": ("cdc7166a43d670b5b14780b1665f2cd92af928b362f63304eff13d1dd763fb05", 6906, "1999-01-04", "2026-07-17"),
    "T10Y2Y": ("d489a93ee1bd3fb396de5e4055df0a7050fe9d6a3067e44329722e05c4b6e24e", 12533, "1976-06-01", "2026-07-24"),
    "BAMLH0A0HYM2": ("68f24558080d9185bed7408fc278b9e99fe2c9db2b98c7ce753bae6083b6c589", 787, "2023-07-25", "2026-07-23"),
    "DEXJPUS": ("162578ed3892895645fa31cc85fa2dc600243f23625d90524010687f7ef1aee5", 13921, "1971-01-04", "2026-07-17"),
}
M4_HOURLY_SHA256 = "ea59b7783573c49077a835ab6465c7d66f1474783360f310988a9a737fbca62f"


def _finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _json_line(row: Mapping[str, Any]) -> str:
    return json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def jsonl_bytes(records: Iterable[Mapping[str, Any]]) -> bytes:
    """Canonical JSONL bytes, independent of input mapping insertion order."""
    rows = sorted((dict(r) for r in records), key=lambda r: (str(r.get("series", "")), int(r.get("origin", 0))))
    return ("".join(_json_line(row) + "\n" for row in rows)).encode("utf-8")


def fingerprint_records(records: Iterable[Mapping[str, Any]]) -> str:
    """SHA-256 of canonical JSONL content."""
    return hashlib.sha256(jsonl_bytes(records)).hexdigest()

def read_jsonl(path: str | os.PathLike[str]) -> list[dict[str, Any]]:
    target = Path(path)
    opener = gzip.open if target.suffix == ".gz" else open
    with opener(target, "rt", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def write_jsonl(path: str | os.PathLike[str], records: Iterable[Mapping[str, Any]]) -> str:
    rows = [dict(r) for r in records]
    data = jsonl_bytes(rows)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.suffix == ".gz":
        # Suppress mtime and filename so bytes are reproducible across runs and
        # checkout locations. The returned digest remains uncompressed JSONL.
        with open(target, "wb") as raw, gzip.GzipFile(
                fileobj=raw, mode="wb", filename="", mtime=0) as fh:
            fh.write(data)
    else:
        with open(target, "wb") as fh:
            fh.write(data)
    return hashlib.sha256(data).hexdigest()

def merge_jsonl(inputs: Iterable[str | os.PathLike[str]], output: str | os.PathLike[str],
                context_length: int | None = DEFAULT_CONTEXT) -> str:
    """Audit and canonically merge multiple JSONL inputs."""
    rows: list[dict[str, Any]] = []
    for path in inputs:
        rows.extend(read_jsonl(path))
    audit_records(rows, context_length)
    return write_jsonl(output, rows)


def predictive_from_record(record: Mapping[str, Any]):
    """Reconstruct the exact Dist/SplicedDist serialized by a record."""
    from skaters.dist import Dist
    return Dist.from_dict(record["teacher"]["predictive"])


def _teacher_summary(dist: Any) -> dict[str, Any]:
    qs = [float(dist.quantile(p)) for p in LEVELS]
    return {"mean": float(dist.mean), "levels": list(LEVELS), "quantiles": qs,
            "predictive": dist.to_dict()}


def validate_record(record: Mapping[str, Any], context_length: int | None = None) -> None:
    """Raise ValueError when a JSONL row violates schema or leakage invariants."""
    if not isinstance(record, Mapping):
        raise ValueError("record must be an object")
    required = {"schema", "series", "regime", "split", "origin", "context", "y", "teacher"}
    missing = required.difference(record)
    if missing:
        raise ValueError(f"missing fields: {sorted(missing)}")
    if record["schema"] != SCHEMA:
        raise ValueError("wrong schema")
    if not isinstance(record["series"], str) or not record["series"]:
        raise ValueError("series must be a nonempty string")
    if not isinstance(record["regime"], str) or not record["regime"]:
        raise ValueError("regime must be a nonempty string")
    if record["split"] not in SPLITS:
        raise ValueError("invalid split")
    origin = record["origin"]
    if isinstance(origin, bool) or not isinstance(origin, int) or origin < 0:
        raise ValueError("origin must be a nonnegative integer")
    context = record["context"]
    if not isinstance(context, list) or not context:
        raise ValueError("context must be a nonempty list")
    if context_length is not None and len(context) != context_length:
        raise ValueError("context length mismatch")
    if not all(_finite(x) for x in context) or not _finite(record["y"]):
        raise ValueError("nonfinite context or target")
    teacher = record["teacher"]
    if not isinstance(teacher, Mapping):
        raise ValueError("teacher must be an object")
    if set(teacher) != {"mean", "levels", "quantiles", "predictive"}:
        raise ValueError("teacher fields mismatch")
    if not _finite(teacher["mean"]):
        raise ValueError("nonfinite teacher mean")
    levels = teacher["levels"]
    quantiles = teacher["quantiles"]
    if not isinstance(levels, list) or len(levels) != len(LEVELS):
        raise ValueError("teacher levels must be q10..q90")
    if any(float(a) != b for a, b in zip(levels, LEVELS)):
        raise ValueError("teacher levels must be ordered q10..q90")
    if not isinstance(quantiles, list) or len(quantiles) != len(LEVELS):
        raise ValueError("teacher quantiles length mismatch")
    if not all(_finite(x) for x in quantiles):
        raise ValueError("nonfinite teacher quantile")
    if any(a > b for a, b in zip(quantiles, quantiles[1:])):
        raise ValueError("crossing teacher quantiles")
    pred = teacher["predictive"]
    if not isinstance(pred, Mapping):
        raise ValueError("predictive must be serialized Dist")
    try:
        d = predictive_from_record(record)
        if not _finite(d.mean) or not _finite(d.crps(float(record["y"]))) or not _finite(d.logpdf(float(record["y"]))):
            raise ValueError("nonfinite predictive")
        if abs(float(teacher["mean"]) - float(d.mean)) > 1e-8 * max(1.0, abs(float(d.mean))):
            raise ValueError("teacher mean does not match predictive")
        dqs = [d.quantile(p) for p in LEVELS]
        if any(not _finite(q) for q in dqs) or any(abs(a - b) > 2e-7 * max(1.0, abs(a), abs(b)) for a, b in zip(quantiles, dqs)):
            raise ValueError("teacher quantiles do not match predictive")
    except (KeyError, TypeError, AssertionError, ValueError) as exc:
        if isinstance(exc, ValueError) and str(exc).startswith(("teacher", "crossing", "nonfinite", "predictive")):
            raise
        raise ValueError(f"invalid predictive: {exc}") from exc


def audit_records(records: Iterable[Mapping[str, Any]], context_length: int | None = None) -> dict[str, Any]:
    """Validate rows, enforcing series-level split disjointness and chronology."""
    rows = list(records)
    by_series: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        validate_record(row, context_length)
        by_series.setdefault(str(row["series"]), []).append(row)
    for sid, sr in by_series.items():
        splits = {str(r["split"]) for r in sr}
        if len(splits) != 1:
            raise ValueError(f"series crosses splits: {sid}")
        ordered = sorted(sr, key=lambda r: int(r["origin"]))
        origins = [int(r["origin"]) for r in ordered]
        if len(set(origins)) != len(origins):
            raise ValueError(f"duplicate origin: {sid}")
        for prev, cur in zip(ordered, ordered[1:]):
            gap = int(cur["origin"]) - int(prev["origin"])
            prev_context = list(prev["context"])
            cur_context = list(cur["context"])
            if len(prev_context) != len(cur_context):
                raise ValueError(f"context length changes within series: {sid}")
            if gap <= len(prev_context):
                # For a gap g, the contexts have n-g provable overlapping
                # observations and the earlier target must occupy position -g
                # in the later context.  Intervening targets are unavailable
                # when rows are sparse, so no stronger check is possible.
                overlap_matches = cur_context[:-gap] == prev_context[gap:]
                prior_target_matches = cur_context[-gap] == float(prev["y"])
                if not overlap_matches or not prior_target_matches:
                    raise ValueError(f"context chronology/leakage violation: {sid}")
    return {"rows": len(rows), "series": len(by_series), "splits": {s: sum(1 for r in rows if r["split"] == s) for s in SPLITS}}


def partition_series(series_ids: Iterable[str], seed: int = 0,
                     fractions: Sequence[float] = (0.8, 0.1, 0.1)) -> dict[str, str]:
    """Deterministically assign each series to exactly one train/validation/test split."""
    ids = sorted({str(s) for s in series_ids})
    if len(fractions) != 3 or any(float(x) < 0 for x in fractions) or sum(fractions) <= 0:
        raise ValueError("fractions must be three nonnegative values")
    total = float(sum(fractions)); f = [float(x) / total for x in fractions]
    order = sorted(ids, key=lambda sid: hashlib.sha256(f"{seed}:{sid}".encode()).digest())
    n = len(order)
    n_train = int(n * f[0]); n_validation = int(n * f[1])
    if n >= 3:
        n_train = max(1, min(n - 2, n_train))
        n_validation = max(1, min(n - n_train - 1, n_validation))
    out = {}
    for sid in order[:n_train]: out[sid] = "train"
    for sid in order[n_train:n_train + n_validation]: out[sid] = "validation"
    for sid in order[n_train + n_validation:]: out[sid] = "test"
    return out


def _student_t(r: random.Random, nu: int = 5) -> float:
    return r.gauss(0.0, 1.0) / math.sqrt(sum(r.gauss(0.0, 1.0) ** 2 for _ in range(nu)) / nu)


def synthetic_series(regime: str, n: int = 512, seed: int = 0) -> list[float]:
    """Generate a deterministic, stdlib-only change stream for one regime."""
    if n < 1: raise ValueError("n must be positive")
    r = random.Random(f"laplace-distill:{seed}:{regime}")
    out: list[float] = []
    if regime in ("seasonal-ar-economic", "seasonal", "economic"):
        ar = 0.0
        for i in range(n):
            ar = 0.72 * ar + 0.45 * math.sin(2 * math.pi * i / 24.0) + 0.65 * _student_t(r, 6)
            out.append(ar)
    elif regime in ("sticky-repeating", "sticky"):
        state = 0.0
        for i in range(n):
            if i == 0 or r.random() < 0.075: state = round(r.gauss(0, 1.2), 1)
            out.append(state + 0.03 * r.gauss(0, 1))
    elif regime in ("garch-returns", "garch", "returns"):
        vol = 0.35
        for _ in range(n):
            eps = _student_t(r, 8); y = vol * eps; out.append(y)
            vol = math.sqrt(0.03 + 0.12 * y * y + 0.84 * vol * vol)
    elif regime in ("random-walk-price-change", "random-walk", "price-change"):
        level = 0.0
        previous = 0.0
        for _ in range(n):
            level += 0.18 * r.gauss(0, 1)
            out.append(level - previous)
            previous = level
    else:
        raise ValueError(f"unknown synthetic regime {regime!r}")
    return out


def synthetic_regimes(n: int = 512, seed: int = 0) -> dict[str, list[float]]:
    names = ("seasonal-ar-economic", "sticky-repeating", "garch-returns", "random-walk-price-change")
    return {name: synthetic_series(name, n=n, seed=seed) for name in names}

# Backward-friendly short alias used by benchmark scripts.
regimes = synthetic_regimes


def _preflight_fred_core(cache_dir: str | os.PathLike[str]) -> dict[str, list[tuple[str, float]]]:
    """Load and verify every frozen FRED source before returning any data."""
    cache = Path(cache_dir)
    missing = [f"{sid}.csv" for sid in FRED_CORE_SOURCES if not (cache / f"{sid}.csv").is_file()]
    if missing:
        raise FileNotFoundError(f"missing canonical FRED cache files: {', '.join(missing)}")
    loaded: dict[str, list[tuple[str, float]]] = {}
    failures = []
    for sid, (expected_sha, expected_rows, first_date, last_date) in FRED_CORE_SOURCES.items():
        path = cache / f"{sid}.csv"
        raw = path.read_bytes()
        actual_sha = hashlib.sha256(raw).hexdigest()
        levels = []
        with path.open(newline="") as fh:
            for row in csv.reader(fh):
                if len(row) != 2:
                    continue
                try:
                    levels.append((row[0], float(row[1])))
                except ValueError:
                    continue
        actual_dates = (levels[0][0], levels[-1][0]) if levels else (None, None)
        if (
            actual_sha != expected_sha
            or len(levels) != expected_rows
            or actual_dates != (first_date, last_date)
        ):
            failures.append(
                f"{sid} (sha256={actual_sha}, rows={len(levels)}, dates={actual_dates})"
            )
        loaded[sid] = levels
    if failures:
        raise ValueError("canonical FRED source mismatch: " + "; ".join(failures))
    return loaded


def _preflight_m4(path: str | os.PathLike[str]) -> None:
    """Require the frozen M4 hourly source instead of downloading on demand."""
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f"missing canonical M4 hourly cache file: {source.name}")
    actual_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    if actual_sha != M4_HOURLY_SHA256:
        raise ValueError(
            f"canonical M4 hourly source mismatch: sha256={actual_sha}"
        )


def archive_frozen_sources(
    cache_dir: str | os.PathLike[str],
    output_path: str | os.PathLike[str],
) -> str:
    """Create a deterministic archive of the exact M4 and FRED source bytes."""
    cache = Path(cache_dir)
    _preflight_fred_core(cache)
    _preflight_m4(cache / "m4_hourly.csv")
    output = Path(output_path)
    if output.exists():
        raise FileExistsError(f"refusing to overwrite source archive: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    source_manifest = {
        "schema": "laplace-distill-sources-v1",
        "m4_hourly": {
            "file": "m4_hourly.csv",
            "sha256": M4_HOURLY_SHA256,
            "url": (
                "https://raw.githubusercontent.com/Mcompetitions/M4-methods/"
                "master/Dataset/Train/Hourly-train.csv"
            ),
        },
        "fred_core": {
            sid: {
                "file": f"{sid}.csv",
                "sha256": values[0],
                "rows": values[1],
                "first_date": values[2],
                "last_date": values[3],
            }
            for sid, values in FRED_CORE_SOURCES.items()
        },
    }
    members = {
        "SOURCE_MANIFEST.json": (
            json.dumps(source_manifest, indent=2, sort_keys=True) + "\n"
        ).encode(),
        "m4_hourly.csv": (cache / "m4_hourly.csv").read_bytes(),
    }
    members.update(
        {
            f"{sid}.csv": (cache / f"{sid}.csv").read_bytes()
            for sid in FRED_CORE_SOURCES
        }
    )
    with output.open("xb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
            with tarfile.open(
                fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT
            ) as archive:
                for name in sorted(members):
                    data = members[name]
                    info = tarfile.TarInfo(f"issue133_sources/{name}")
                    info.size = len(data)
                    info.mtime = 0
                    info.mode = 0o644
                    info.uid = info.gid = 0
                    info.uname = info.gname = ""
                    archive.addfile(info, io.BytesIO(data))
    return hashlib.sha256(output.read_bytes()).hexdigest()


def iter_corpus(arm: str = "synthetic", limit: int = 24, n: int = 512, seed: int = 0):
    """Yield ``(series_id, regime, values)`` using only approved adapters."""
    if arm == "synthetic":
        names = tuple(synthetic_regimes(n=n, seed=seed))
        for i in range(max(0, limit)):
            regime = names[i % len(names)]
            j = i // len(names)
            yield f"synthetic-{regime}-{j}", regime, synthetic_series(
                regime, n=n, seed=seed + i + 101)
        return
    if arm == "m4-hourly":
        if limit <= 0:
            return
        import corpus

        _preflight_m4(corpus._M4_CACHE)
        count = 0
        for sid, _title, changes in corpus.iter_arm("m4-hourly", limit=limit):
            yield str(sid), "m4-hourly", list(changes)
            count += 1
            if count >= limit:
                break
        return
    if arm in ("fred", "fred-core"):
        try:
            from . import fred, fred_universe
        except ImportError:
            import fred
            import fred_universe
        loaded = _preflight_fred_core(fred._CACHE)
        for sid in list(FRED_CORE_SOURCES)[:max(0, limit)]:
            changes = fred._to_changes(loaded[sid])
            if not changes:
                raise ValueError(f"canonical FRED source produces no changes: {sid}")
            title = fred.SERIES.get(sid, "")
            asset = fred_universe.asset_class(title)
            regime = "fred-price-return" if asset in {"equity", "fx", "commodity"} else "fred-econ"
            yield sid, regime, changes
        return
    raise ValueError("arm must be synthetic, m4-hourly, fred, or fred-core")


def generate_series_records(values: Sequence[float], series: str, regime: str, split: str,
                            context_length: int = DEFAULT_CONTEXT, max_records: int | None = None,
                            forecaster_factory: Callable[[], Any] | None = None,
                            burn_in: int = 300) -> list[dict[str, Any]]:
    """Create online one-step records after warm-up, retaining final rows."""
    if split not in SPLITS: raise ValueError("invalid split")
    if context_length < 1: raise ValueError("context_length must be positive")
    if burn_in < 0: raise ValueError("burn_in must be nonnegative")
    if max_records is not None and max_records <= 0: return []
    ys = [float(y) for y in values]
    if not all(_finite(y) for y in ys): raise ValueError("nonfinite series")
    if forecaster_factory is None:
        from skaters import laplace
        forecaster_factory = lambda: laplace(1)
    f = forecaster_factory(); state = None; pending = None
    out = deque(maxlen=max_records)
    record_start = max(context_length, burn_in)
    if max_records is not None:
        record_start = max(record_start, len(ys) - max_records)
    for origin, y in enumerate(ys):
        if pending is not None and origin >= record_start:
            d = pending
            row = {"schema": SCHEMA, "series": str(series), "regime": str(regime), "split": split,
                   "origin": origin, "context": ys[origin - context_length:origin], "y": y,
                   "teacher": _teacher_summary(d)}
            validate_record(row, context_length)
            out.append(row)
        # Always consume every observation, including rows evicted by the cap.
        emitted, state = f(y, state)
        pending = emitted[0] if isinstance(emitted, (list, tuple)) else emitted
    return list(out)


def partition_by_regime(streams: Iterable[tuple[str, str, Sequence[float]]],
                        seed: int = 0) -> dict[str, str]:
    """Partition each regime independently so every sufficiently large regime
    has train, validation, and test representation."""
    groups: dict[str, list[str]] = {}
    for sid, regime, _values in streams:
        groups.setdefault(str(regime), []).append(str(sid))
    out: dict[str, str] = {}
    for regime in sorted(groups):
        digest = hashlib.sha256(f"{seed}:{regime}".encode()).digest()
        local_seed = int.from_bytes(digest[:8], "big")
        out.update(partition_series(groups[regime], seed=local_seed))
    return out

def build_records(arm: str = "synthetic", seed: int = 0, context_length: int = DEFAULT_CONTEXT,
                  limit: int = 24, n: int = 512, max_records: int | None = None,
                  source: str | None = None, split_override: str | None = None,
                  source_splits: Mapping[str, str] | None = None,
                  burn_in: int = 300) -> list[dict[str, Any]]:
    """Build rows, optionally pinning a whole source to one split.

    ``source_splits`` accepts source names (``fred-core``, ``m4-hourly``,
    ``synthetic``) and individual series IDs.  The ``split_override`` shorthand
    applies to every stream selected by this invocation.
    """
    source = source or arm
    adapter = "fred" if source == "fred-core" else arm
    streams = list(iter_corpus(adapter, limit=limit, n=n, seed=seed))
    assignments = partition_by_regime(streams, seed=seed)
    overrides = dict(source_splits or {})
    if split_override is not None:
        if split_override not in SPLITS: raise ValueError("invalid split_override")
        for sid, _regime, _values in streams: assignments[sid] = split_override
    for sid, _regime, _values in streams:
        source_keys = (sid, source, arm, "fred-core" if adapter == "fred" else "")
        override = next((overrides[k] for k in source_keys if k and k in overrides), None)
        if override is not None:
            if override not in SPLITS: raise ValueError(f"invalid split for {sid}")
            assignments[sid] = override
    rows = []
    for sid, regime, values in streams:
        rows.extend(generate_series_records(values, sid, regime, assignments[sid],
                                            context_length, max_records,
                                            burn_in=burn_in))
    audit_records(rows, context_length)
    return rows

def score_record(record: Mapping[str, Any]) -> tuple[float, float]:
    """Return the canonical LL (with the package floor) and CRPS for a row."""
    d = predictive_from_record(record)
    y = float(record["y"])
    return max(LL_FLOOR, float(d.logpdf(y))), float(d.crps(y))


def source_tree_manifest() -> dict[str, Any]:
    """Hash benchmark and package sources that determine teacher records."""
    root = Path(__file__).resolve().parents[1]
    paths = sorted((root / "src" / "skaters").glob("*.py"))
    paths.extend(
        root / "benchmarks" / name
        for name in (
            "corpus.py",
            "fred.py",
            "fred_universe.py",
            "fetch_freq.py",
            "laplace_distill.py",
            "predictions.py",
            "timesfm_distill.py",
        )
    )
    files = {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in paths
        if path.is_file()
    }
    payload = json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
    return {"sha256": hashlib.sha256(payload).hexdigest(), "files": files}


def write_producer_manifest(
    output_path: str | os.PathLike[str],
    records: Sequence[Mapping[str, Any]],
    settings: Mapping[str, Any],
    manifest_path: str | os.PathLike[str] | None = None,
) -> tuple[Path, dict[str, Any]]:
    """Persist the exact teacher-producer runtime and source contract."""
    output = Path(output_path)
    context_lengths = sorted({len(record["context"]) for record in records})
    manifest = {
        "schema": "laplace-distill-producer-v1",
        "output": {
            "file": output.name,
            "bytes": output.stat().st_size,
            "file_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
            "records_sha256": fingerprint_records(records),
            "rows": len(records),
            "series": len({str(record["series"]) for record in records}),
            "splits": {
                split: sum(record["split"] == split for record in records)
                for split in SPLITS
            },
            "context_lengths": context_lengths,
        },
        "producer_runtime": {
            "python": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "executable_name": Path(sys.executable).name,
            "os": platform.platform(),
            "machine": platform.machine(),
            "zlib_runtime": zlib.ZLIB_RUNTIME_VERSION,
            "zlib_compile": zlib.ZLIB_VERSION,
        },
        "source_contract": {
            "m4_hourly_sha256": M4_HOURLY_SHA256,
            "fred_core": {
                sid: {
                    "sha256": values[0],
                    "rows": values[1],
                    "first_date": values[2],
                    "last_date": values[3],
                }
                for sid, values in FRED_CORE_SOURCES.items()
            },
        },
        "source_tree": source_tree_manifest(),
        "settings": dict(settings),
        "byte_identity_scope": (
            "Guaranteed only for the recorded producer runtime and frozen source bytes; "
            "cross-platform byte identity is not claimed."
        ),
    }
    target = Path(manifest_path) if manifest_path else Path(f"{output}.manifest.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return target, manifest


# Small aliases keep integrations readable without duplicating implementations.
generate_records = generate_series_records
build_dataset = build_records
partition = partition_series
audit = audit_records
sha256 = fingerprint_records


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Build and audit deterministic Laplace teacher JSONL")
    arms = ("synthetic", "m4-hourly", "fred", "fred-core")
    p.add_argument("--out", default=None)
    p.add_argument("--manifest", default=None, help="producer manifest path; defaults beside --out")
    p.add_argument("--source-archive", default=None, help="archive frozen M4/FRED source bytes")
    p.add_argument("--audit", default=None, metavar="JSONL", help="audit an existing JSONL instead of building")
    p.add_argument("--merge", nargs="+", default=None, metavar="JSONL",
                   help="audit and merge input JSONL files into --out")
    p.add_argument("--arm", choices=arms, default="synthetic")
    p.add_argument("--source", choices=arms, default=None,
                   help="source label; fred-core means cached eight-series test transfer")
    p.add_argument("--split", dest="split_override", choices=SPLITS, default=None,
                   help="pin the selected source to one split")
    p.add_argument("--split-override", dest="source_override", action="append", default=[], metavar="SOURCE=SPLIT")
    p.add_argument("--seed", type=int, default=0); p.add_argument("--context", type=int, default=DEFAULT_CONTEXT)
    p.add_argument("--burn-in", type=int, default=300)
    p.add_argument("--limit", type=int, default=24); p.add_argument("--n", type=int, default=512)
    p.add_argument("--max-records", type=int, default=None)
    a = p.parse_args(argv)
    if a.audit and a.merge:
        p.error("--audit and --merge are mutually exclusive")
    source_archive = None
    if a.source_archive:
        if a.audit:
            p.error("--source-archive requires a build or merge command")
        source_archive = {
            "file": Path(a.source_archive).name,
            "sha256": archive_frozen_sources(
                Path(__file__).with_name("data"), a.source_archive
            ),
        }
    if a.merge:
        if not a.out:
            p.error("--out is required with --merge")
        digest = merge_jsonl(a.merge, a.out, a.context)
        rows = read_jsonl(a.out)
        manifest_path, _manifest = write_producer_manifest(
            a.out,
            rows,
            {
                "mode": "merge",
                "inputs": [Path(path).name for path in a.merge],
                "context": a.context,
                "source_archive": source_archive,
            },
            a.manifest,
        )
        print(
            json.dumps(
                {
                    "schema": SCHEMA,
                    "rows": len(rows),
                    "sha256": digest,
                    "producer_manifest": manifest_path.name,
                },
                sort_keys=True,
            )
        )
        return 0
    if a.audit:
        rows = read_jsonl(a.audit)
        report = audit_records(rows, a.context)
        report.update({"schema": SCHEMA, "sha256": fingerprint_records(rows)})
        print(json.dumps(report, sort_keys=True))
        return 0
    if not a.out:
        p.error("--out is required unless --audit is supplied")
    source_splits = {}
    for item in a.source_override:
        try: key, value = item.split("=", 1)
        except ValueError: p.error("--split-override requires SOURCE=SPLIT")
        if value not in SPLITS: p.error(f"invalid split in {item!r}")
        source_splits[key] = value
    rows = build_records(
        a.arm,
        a.seed,
        a.context,
        a.limit,
        a.n,
        a.max_records,
        source=a.source,
        split_override=a.split_override,
        source_splits=source_splits,
        burn_in=a.burn_in,
    )
    digest = write_jsonl(a.out, rows)
    manifest_path, _manifest = write_producer_manifest(
        a.out,
        rows,
        {
            "mode": "build",
            "arm": a.arm,
            "source": a.source,
            "split_override": a.split_override,
            "source_splits": source_splits,
            "seed": a.seed,
            "context": a.context,
            "burn_in": a.burn_in,
            "limit": a.limit,
            "n": a.n,
            "max_records": a.max_records,
            "source_archive": source_archive,
        },
        a.manifest,
    )
    print(
        json.dumps(
            {
                "schema": SCHEMA,
                "rows": len(rows),
                "sha256": digest,
                "producer_manifest": manifest_path.name,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
