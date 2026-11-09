"""Replay the repository protocol offline and summarize paired prediction tapes.

No model implementation is copied here. Every forecast comes from the selected
source tree through the candidate repository's existing benchmark runner.
"""
from __future__ import annotations
import argparse
import collections
import csv
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import statistics
import sys
import urllib.request

HERE = Path(__file__).resolve().parent
FIELDS = ('y', 'mean', 'std', 'q05', 'q50', 'q95', 'logpdf', 'crps')

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read_json(path):
    return json.loads(Path(path).read_text())

def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')

def verify(repo, source, method):
    identity = read_json(HERE / 'source-identity.json')
    for name, digest in identity['candidate_files_sha256'].items():
        if sha(repo / name) != digest:
            raise ValueError('Candidate file mismatch: ' + name)
    hashes = identity['baseline_src_sha256'] if method == 'laplace_old' else {
        name: digest for name, digest in identity['candidate_files_sha256'].items()
        if name.startswith('src/')}
    for name, digest in hashes.items():
        if sha(source / Path(name).relative_to('src')) != digest:
            raise ValueError('Selected model source mismatch: ' + name)
    return hashes

def record(args):
    repo, source, cache, output = (Path(x).resolve() for x in
                                 (args.repo, args.source, args.cache, args.output))
    hashes = verify(repo, source, args.method)
    inputs = read_json(HERE / 'inputs.json')[args.corpus]
    if sha(cache) != inputs['cache_sha256']:
        raise ValueError('Corpus hash differs from the reported input snapshot')
    if output.exists() or output.with_suffix('.raw.csv').exists():
        raise ValueError('Use a fresh output path; prediction tapes are never resumed')
    output.parent.mkdir(parents=True, exist_ok=True)
    for name in list(os.environ):
        if name.startswith(('ARM_', 'FM_', 'CANON_')):
            del os.environ[name]
    os.environ.update(ARM_METHODS=args.method, ARM_CORPUS=args.corpus,
                      ARM_MAX=str(args.max_series), ARM_H='1', FM_CTX='128',
                      FM_TEST='64', PRED_OUT=str(output))
    def offline(*_args, **_kwargs):
        raise RuntimeError('Network access is disabled; supply the pinned cache')
    urllib.request.urlopen = offline
    sys.path[:0] = [str(source), str(repo / 'benchmarks')]
    import skaters.dist
    import arm_adapters
    import predictions
    if Path(skaters.dist.__file__).resolve() != source / 'skaters/dist.py':
        raise ValueError('Wrong Skaters source was imported')
    factory = arm_adapters.make_registry
    def registry(h=1):
        result = factory(h)
        result['laplace_old'] = result['laplace']
        return result
    arm_adapters.make_registry = registry
    if args.precision == 'full':
        predictions._f = lambda value: '' if value is None else repr(float(value))
        original = predictions.PredictionWriter
        raw_file = output.with_suffix('.raw.csv').open('x')
        raw = csv.writer(raw_file)
        raw.writerow(['study', 'series', 'method', 'step', 'raw_logpdf'])
        class Writer(original):
            def step(self, study, series, method, step, y, dist=None, **kwargs):
                if dist is None or kwargs:
                    raise ValueError('Unexpected benchmark writer call')
                lp = dist.logpdf(y)
                raw.writerow([study, series, method, step, repr(float(lp))])
                super().step(study, series, method, step, y, dist=dist,
                             logpdf=max(lp, -20.0) if math.isfinite(lp) else -20.0)
            def close(self):
                super().close()
                raw_file.close()
        predictions.PredictionWriter = Writer
    spec = importlib.util.spec_from_file_location('quantile_acceptance_run', repo / 'benchmarks/run_arm.py')
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    def iter_series(arm):
        if arm != args.corpus:
            raise ValueError('Unexpected corpus')
        with cache.open() as file:
            for line in file:
                row = json.loads(line)
                yield row['sid'], row['title'], row['ch']
    runner.iter_series = iter_series
    runner.main()
    loaded = {}
    for name, module in list(sys.modules.items()):
        filename = getattr(module, '__file__', None)
        if (name == 'skaters' or name.startswith('skaters.')) and filename:
            relative = 'src/' + str(Path(filename).resolve().relative_to(source))
            if sha(Path(filename)) != hashes[relative]:
                raise ValueError('Loaded model module mismatch: ' + name)
            loaded[relative] = hashes[relative]
    write_json(output.with_suffix('.identity.json'), {
        'method': args.method, 'corpus': args.corpus, 'precision': args.precision,
        'max_series': args.max_series, 'cache_sha256': sha(cache),
        'loaded_source_sha256': loaded, 'prediction_sha256': sha(output)})

def read_rows(path):
    with Path(path).open() as file:
        rows = list(csv.DictReader(file))
    result = {(r['study'], r['series'], int(r['step'])): r for r in rows}
    if len(result) != len(rows) or not result:
        raise ValueError('Empty prediction tape or duplicate row keys')
    return result

def validate_series_set(rows, complete=False):
    """Require the pinned series (a leading prefix is allowed for smoke runs)."""
    inputs = read_json(HERE / 'inputs.json')
    grouped = collections.defaultdict(list)
    for row in rows:
        grouped[row['study'].split(':', 1)[0]].append(row['series'])
    for corpus, series in grouped.items():
        if corpus not in inputs:
            raise ValueError('Unknown corpus in results: ' + corpus)
        count = len(series)
        expected = inputs[corpus]['series_ids']
        if not 1 <= count <= 200 or len(set(series)) != count:
            raise ValueError('Duplicate or invalid series count')
        if set(series) != set(expected[:count]) or complete and count != 200:
            raise ValueError('Series set differs from pinned inputs')

def summarize_pair(old_path, new_path, old_raw=None, new_raw=None):
    old, new = read_rows(old_path), read_rows(new_path)
    if old.keys() != new.keys():
        raise ValueError('Prediction keys do not match')
    raw = (read_rows(old_raw), read_rows(new_raw)) if old_raw and new_raw else None
    if raw and (raw[0].keys() != old.keys() or raw[1].keys() != old.keys()):
        raise ValueError('Raw log-likelihood keys do not match')
    groups = collections.defaultdict(list)
    for key in old:
        groups[key[:2]].append(key)
    result = []
    for (study, series), keys in sorted(groups.items()):
        if sorted(k[2] for k in keys) != list(range(64)):
            raise ValueError('Expected exactly 64 scored steps per series')
        rec = {'study': study, 'series': series, 'steps': len(keys),
               'mean_logpdf_baseline': statistics.mean(float(old[k]['logpdf']) for k in keys),
               'mean_logpdf_candidate': statistics.mean(float(new[k]['logpdf']) for k in keys),
               'logpdf_step_changes': 0, 'boundary_flips': [0, 0, 0, 0],
               'coverage_baseline': [0, 0], 'coverage_candidate': [0, 0],
               'max_absolute_movements': {field: 0.0 for field in FIELDS}}
        if raw:
            rec.update(raw_logpdf_changes=0, raw_nonfinite_count=0)
        for key in keys:
            a, b = old[key], new[key]
            if a['method'] != 'laplace_old' or b['method'] != 'laplace':
                raise ValueError('Expected baseline laplace_old and candidate laplace')
            if float(a['y']) != float(b['y']):
                raise ValueError('Observed values do not match')
            if not all(math.isfinite(float(row[f])) for row in (a,b) for f in FIELDS):
                raise ValueError('Nonfinite canonical prediction value')
            decisions = []
            for row, field in [(a, 'coverage_baseline'), (b, 'coverage_candidate')]:
                y, lo, med, hi = (float(row[f]) for f in ('y','q05','q50','q95'))
                decision = (lo <= y <= hi, y <= med, lo <= y, y <= hi)
                decisions.append(decision)
                rec[field][0] += decision[0]
                rec[field][1] += decision[1]
            for i in range(4):
                rec['boundary_flips'][i] += decisions[0][i] != decisions[1][i]
            rec['logpdf_step_changes'] += float(a['logpdf']) != float(b['logpdf'])
            for field in FIELDS:
                rec['max_absolute_movements'][field] = max(rec['max_absolute_movements'][field], abs(float(a[field])-float(b[field])))
            if raw:
                x,y = (float(rows[key]['raw_logpdf']) for rows in raw)
                rec['raw_logpdf_changes'] += x != y
                rec['raw_nonfinite_count'] += not (math.isfinite(x) and math.isfinite(y))
        result.append(rec)
    validate_series_set(result)
    return result

def aggregate(rows):
    result = {}
    for study in sorted({row['study'] for row in rows}):
        group = [row for row in rows if row['study']==study]
        ds = [r['mean_logpdf_candidate']-r['mean_logpdf_baseline'] for r in group]
        result[study] = {'series':len(group), 'steps':sum(r['steps'] for r in group),
                         'median_dLL':statistics.median(ds), 'max_absolute_series_dLL':max(map(abs,ds)),
                         'coverage_baseline':[sum(r['coverage_baseline'][i] for r in group) for i in range(2)],
                         'coverage_candidate':[sum(r['coverage_candidate'][i] for r in group) for i in range(2)],
                         'logpdf_step_changes':sum(r['logpdf_step_changes'] for r in group),
                         'boundary_flips':[sum(r['boundary_flips'][i] for r in group) for i in range(4)],
                         'max_absolute_movements':{f:max(r['max_absolute_movements'][f] for r in group) for f in FIELDS}}
        if 'raw_logpdf_changes' in group[0]:
            result[study].update(raw_logpdf_changes=sum(r['raw_logpdf_changes'] for r in group),
                                 raw_nonfinite_count=sum(r['raw_nonfinite_count'] for r in group))
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    record_parser=sub.add_parser('record')
    for name in ('repo','source','cache','output'):
        record_parser.add_argument('--'+name,required=True)
    record_parser.add_argument('--method',choices=('laplace_old','laplace'),required=True)
    record_parser.add_argument('--corpus',choices=('daily','weekly','monthly','m4-hourly'),required=True)
    record_parser.add_argument('--precision',choices=('canonical','full'),default='canonical')
    record_parser.add_argument('--max-series',type=int,default=200)
    summarize_parser=sub.add_parser('summarize')
    for name in ('baseline','candidate','output'):
        summarize_parser.add_argument('--'+name,required=True)
    summarize_parser.add_argument('--baseline-raw')
    summarize_parser.add_argument('--candidate-raw')
    sub.add_parser('verify-results')
    args=parser.parse_args()
    if args.command=='record':
        if not 1 <= args.max_series <= 200:
            parser.error('--max-series must be between 1 and 200')
        record(args)
    elif args.command=='summarize':
        if bool(args.baseline_raw)!=bool(args.candidate_raw):
            parser.error('Supply both raw tapes or neither')
        rows=summarize_pair(args.baseline,args.candidate,args.baseline_raw,args.candidate_raw)
        write_json(args.output,{'per_series':rows,'aggregate':aggregate(rows)})
    else:
        for precision in ('canonical','full-precision'):
            rows=read_json(HERE/f'results/{precision}-per-series.json')
            expected=read_json(HERE/f'results/{precision}-summary.json')
            validate_series_set(rows, complete=True)
            corpora={r['study'].split(':',1)[0] for r in rows}
            required={'daily','weekly','monthly'} | ({'m4-hourly'} if precision=='canonical' else set())
            if corpora!=required or any(r['steps']!=64 for r in rows):
                raise ValueError('Incomplete acceptance corpus or step coverage')
            if aggregate(rows)!=expected:
                raise ValueError('Stored summaries differ from per-series evidence')
            for summary in expected.values():
                if summary['median_dLL']!=0 or summary['coverage_baseline']!=summary['coverage_candidate']:
                    raise ValueError('Canonical acceptance predicate failed')
                if precision=='full-precision' and (
                    summary['logpdf_step_changes']!=0 or any(summary['boundary_flips'])
                    or summary['raw_logpdf_changes']!=0 or summary['raw_nonfinite_count']!=0):
                    raise ValueError('Full-precision score/boundary predicate failed')
            print(precision+': aggregates reproduced; corpus completeness and acceptance predicates pass')
        before=read_json(HERE/'results/signatures-before.json')
        after=read_json(HERE/'results/signatures-after.json')
        expected=read_json(HERE/'results/signature-measurements.json')
        fields=('mean','std','q0.001','q0.01','q0.1','q0.5','q0.9','q0.99','q0.999','logpdf','cdf')
        if set(before)!=set(after) or set(before)!=set(expected):
            raise ValueError('Signature stream sets differ')
        for stream in before:
            changed=before[stream]['sha256']!=after[stream]['sha256']
            if not changed or expected[stream]['digest_identical']:
                raise ValueError('Expected changed signature digest: '+stream)
            for sample in (before[stream],after[stream]):
                digest=hashlib.sha256(json.dumps([[repr(v) for v in row] for row in sample['rows']]).encode()).hexdigest()
                if digest!=sample['sha256']:
                    raise ValueError('Signature digest mismatch: '+stream)
            a,b=before[stream]['rows'],after[stream]['rows']
            if len(a)!=len(b) or len(a)!=expected[stream]['rows']:
                raise ValueError('Signature row count mismatch')
            movements={}
            for j,field in enumerate(fields):
                gaps=[]
                for x,y in zip(a,b):
                    if math.isfinite(x[j]) and math.isfinite(y[j]): gaps.append(abs(x[j]-y[j]))
                    elif x[j]==y[j] or math.isnan(x[j]) and math.isnan(y[j]): gaps.append(0.0)
                    else: gaps.append(math.inf)
                movements[field]=max(gaps)
            if movements!=expected[stream]['max_absolute_moves']:
                raise ValueError('Signature movement summary mismatch')
            if stream!='near_constant' and max(movements.values())>5e-10:
                raise ValueError('Ordinary signature movement exceeds tol/2')
        print('signatures: all seven digests and movement summaries verified')

if __name__=='__main__':
    main()
