# Scale-relative quantile precision: acceptance evidence

This study supports the narrow successor to [#176](https://github.com/microprediction/skaters/pull/176), using the [maintainer's acceptance criteria](https://github.com/microprediction/skaters/pull/176#issuecomment-6691384453).

Baseline: `8baee06362f82504fe47e25f7b91fe6d8b55eb84`. The implementation is an uncommitted snapshot on that baseline, identified by `source-identity.json`. These evidence files are a subsequent overlay and are not part of that implementation snapshot's hashes.

## Recorded results

The repository's canonical protocol used 200 series per corpus, 64 rolling one-step evaluations per series, context 128, and at most 1,000 history values. Both versions used identical saved input caches. The baseline source was archived before implementation and selected in a separate process. The baseline method label is `laplace_old`; the candidate label is `laplace`.

| Corpus | Series | Paired predictions | Median per-series ΔLL | Central 90% covered, both versions | At/below median, both versions |
| --- | ---: | ---: | ---: | ---: | ---: |
| FRED daily | 200 | 12,800 | 0 | 11,307 | 6,946 |
| FRED weekly | 200 | 12,800 | 0 | 11,405 | 6,063 |
| FRED monthly | 200 | 12,800 | 0 | 11,938 | 6,500 |
| M4 hourly | 200 | 12,800 | 0 | 11,534 | 6,490 |

These counts use the existing canonical writer, which records six decimal places. The maximum absolute per-series ΔLL is also zero. Daily data are split into 149 economic and 51 price series; weekly and monthly contain 200 non-price economic series each. All frequency/regime strata pass separately.

Some canonical quantiles and CRPS values differ by one unit in the sixth decimal because a smaller full-precision movement crosses a decimal rounding threshold. Canonical tapes are therefore not bit-identical either; the stated log-likelihood and coverage acceptance criteria still pass.

A supplementary FRED run preserves full Python binary64 precision with `repr(float)` and records unfloored log-likelihood separately. Across 600 series and 38,400 paired predictions, every unfloored log-likelihood is finite and exactly equal. There are zero individual lower-bound, upper-bound, central-90%, or median classification flips between versions.

| Corpus | Full-precision central 90% covered, both versions | Full-precision at/below median, both versions |
| --- | ---: | ---: |
| Daily | 11,279 / 12,800 | 6,675 / 12,800 |
| Weekly | 11,405 / 12,800 | 5,958 / 12,800 |
| Monthly | 11,938 / 12,800 | 6,473 / 12,800 |

Absolute counts differ between the two recording precisions because rounding observations and quantiles can change boundary comparisons. The comparison between baseline and candidate passes under both precisions. M4 was checked with canonical recording only.

Full-precision outputs are **not all bit-identical**. Maximum observed quantile movement is `4.989252941301289e-10`; maximum CRPS movement is `2.6592235735269077e-10`. Mean and standard deviation also move slightly. Every measured field movement is below `5e-10`; this is a result on these data, not a universal guarantee.

## Frozen synthetic signatures

`vendor/laplace_k1_signatures.py` is copied without modification from [#323](https://github.com/microprediction/skaters/pull/323), commit `f57fe72ef483ca0ae8f088f1c388cdb29b7b3704`. This does not assume that PR has merged. Its SHA-256 and upstream location are in `verification-summary.json`; the upstream MIT license is included.

All seven stream digests change. On the six ordinary streams, the largest absolute field movement is `4.936708819514024e-10`, below `tol/2 = 5e-10`. The separately reported near-constant stream moves by at most `4.98943997229162e-10`. CDF and log-density values remain unchanged on all seven streams. The input generator and complete synthetic before/after arrays are included.

## Files and evidence boundaries

- `results/*-per-series.json`: one result per series, including score means, exact coverage counts, individual decision-flip counts, and maximum field movements.
- `results/*-summary.json`: derived frequency/regime aggregates. `boundary_flips` order is central90, at/below median, lower bound, upper bound; coverage arrays are central90 and at/below median counts.
- `results/signatures-*.json` and `signature-measurements.json`: complete synthetic output arrays and derived measurements.
- `inputs.json`: selected series identifiers, corpus-cache hashes, retrieval times where recorded, and selection rules.
- `source-identity.json`: pinned baseline, complete implementation file hashes, baseline source hashes, and the recorded documentation-only delta after implementation review. The file set comprises 898 already-tracked files and the five new files in the implementation patch; it has no unrelated untracked-file dependency.
- `verification-summary.json`: local test counts, runtime versions, independent implementation-review scope, and limits.
- `reproduce.py`: portable recorder and paired-summary tool, reviewed separately from the implementation. `packaging-review.json` records that scope and the subsequent verification/documentation changes.

No credentials, `.env` files, local absolute paths, private consultation transcripts, downloaded FRED observations, or per-step economic prediction tapes are included. Original caches and tapes were retained locally. **Hashes alone do not reconstruct the original data.** Exact replay requires caches matching `inputs.json`; fresh FRED retrieval may reflect revisions or changed rankings and constitutes a new run. Aggregates can be recomputed from the included per-series results without the raw caches.

## Verify the included results

Only Python's standard library is needed for this command:

```sh
python benchmarks/quantile_scale_precision/reproduce.py verify-results
```

It recomputes corpus summaries, verifies the complete pinned series sets and 64-step counts, asserts canonical acceptance and full-precision score/boundary predicates, and verifies synthetic row digests and movement summaries. It does not rerun forecasting or independently authenticate the omitted raw input caches. The general `summarize` command permits a leading subset of pinned series for smoke checks and does not by itself certify the complete 200-series acceptance run.

## Replay forecasts using the original caches

Use the candidate checkout and a compatible environment with its declared dependencies. The recorded benchmark runtime was Python 3.14.6 with NumPy 2.5.4. Keep the baseline source in a separate directory:

Recording is deliberately locked to the listed candidate file contents, including workflows and changelogs. Later edits to any pinned file require a new validated identity record; a different Git commit with identical pinned contents is acceptable. The M4 input hash identifies the complete 414-row `benchmarks/preds/_corpus_m4-hourly.jsonl` cache, from which the first 200 series were scored.

```sh
mkdir -p /tmp/skaters-quantile-baseline
git archive 8baee06362f82504fe47e25f7b91fe6d8b55eb84 src | tar -x -C /tmp/skaters-quantile-baseline
```

The following example assumes the original hashed corpus cache is available at the repository's normal cache location. Use a fresh output directory. Both arms run in separate processes; the tool validates source and cache hashes and disables network access.

```sh
python benchmarks/quantile_scale_precision/reproduce.py record \
  --repo . --source /tmp/skaters-quantile-baseline/src \
  --cache benchmarks/preds/_corpus_daily.jsonl --corpus daily \
  --method laplace_old --precision full --output /tmp/quantile-check/daily-old.csv
python benchmarks/quantile_scale_precision/reproduce.py record \
  --repo . --source src \
  --cache benchmarks/preds/_corpus_daily.jsonl --corpus daily \
  --method laplace --precision full --output /tmp/quantile-check/daily-new.csv
python benchmarks/quantile_scale_precision/reproduce.py summarize \
  --baseline /tmp/quantile-check/daily-old.csv --candidate /tmp/quantile-check/daily-new.csv \
  --baseline-raw /tmp/quantile-check/daily-old.raw.csv \
  --candidate-raw /tmp/quantile-check/daily-new.raw.csv \
  --output /tmp/quantile-check/daily-summary.json
```

Repeat for weekly and monthly using their respective caches. Use `--precision canonical` for the original six-decimal protocol, including M4 hourly; omit the two raw-tape arguments when summarizing canonical outputs. A run has 200 series by default. `--max-series` exists for packaging smoke checks, not for claiming the 200-series acceptance result.

The recorder invokes the existing `benchmarks/run_arm.py` and its registry. It changes only source/cache routing, adds the `laplace_old` alias, and optionally replaces numeric serialization and records an unfloored score sidecar. It preserves the canonical `-20` log-score floor. `summarize_canonical.py` remains the authoritative canonical summarizer; run it with `CANON_BASELINE=laplace_old` and the chosen prediction directory. The saved original canonical results used that summarizer; the portable summarizer additionally reports per-step differences and boundary flips.

Synthetic signatures can be rerun against each source without FRED data:

```sh
PYTHONPATH=/tmp/skaters-quantile-baseline/src python benchmarks/quantile_scale_precision/vendor/laplace_k1_signatures.py --write /tmp/signatures-before.json
PYTHONPATH=src python benchmarks/quantile_scale_precision/vendor/laplace_k1_signatures.py --compare /tmp/signatures-before.json
```

The upstream signature tool reports changed digests; a nonzero comparison exit alone is not this change's acceptance criterion. Compare the measured ordinary-stream movements against `tol/2` and inspect near-constant separately.

## Review and remaining checks

The implementation completed independent Claude Code review. The final focused correction review used `claude-fable-5-1` and found no material defects in that delta. A documentation-only clarification followed; executable/test/configuration bytes remained unchanged. Execution evidence was collected separately. The reviewed model code is unchanged by this study.

The portable evidence script, package, and draft PR text received a separate analytical, read-only `claude-fable-5-1` review. It found no material defects and requested a conditional clean-clone file check; that check confirmed only the five intended new implementation files are untracked. Subsequent changes strengthen verification and clarify documentation; their local proof and review-carry limits are recorded in `packaging-review.json`. The reviewer did not execute the scripts or recompute hashes. Cross-platform GitHub CI, WebAssembly, and minimum-supported-Rust checks have not run on this unpublished candidate. Optional Torch behavior was not changed. No universal accuracy, output-invariance, merge-readiness, or release claim is made.
