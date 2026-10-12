#!/usr/bin/env python3
"""Frozen 512-token local completion amendment; never resumes or replaces rows."""
import argparse
import collections
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import time
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT / 'tmp/temporal-diagnostic-20261011-v1'
OUT = ROOT / 'tmp/temporal-completion-20261011-v3'
PARENT_RUNNER = ROOT / 'analysis/run_temporal_diagnostic_20261011_v1.py'
AUDITOR = ROOT / 'analysis/audit_temporal_completion_20261011_v3.py'
KEYS = ('base_id', 'proposal', 'expression', 'framing', 'procedure')
EXPECTED_PARENT_PROTOCOL = 'cf685b59b15f7af6e1e090c39107df828243515f068ebb5fe8827bc0f2953821'
EXPECTED_PARENT_RAW = 'adb69773bebe5ae8b7663a107382f556039a28693e0180511c2d7feaf429f868'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical_sha(obj):
    return sha(json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode())


def dump(path, obj):
    with path.open('x') as f:
        f.write(json.dumps(obj, indent=2, ensure_ascii=False) + '\n')
        f.flush()
        os.fsync(f.fileno())


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('redirect forbidden: loopback-only protocol')


def api(path, payload=None):
    assert path in ('/api/tags', '/api/chat')
    request = urllib.request.Request('http://127.0.0.1:11434' + path)
    if payload is not None:
        request.data = json.dumps(payload).encode()
        request.add_header('Content-Type', 'application/json')
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    with opener.open(request, timeout=120) as response:
        return json.load(response)


def check_model(p):
    tags = api('/api/tags')
    assert any(m['name'] == p['model'] and m['digest'] == p['model_digest'] for m in tags['models'])
    return tags


def validate_value(value):
    assert type(value) is dict and set(value) == {'authorized_dates', 'proposed_dates', 'reason', 'evidence'}, 'keys mismatch'
    assert all(type(value[k]) is str for k in ('reason', 'evidence')), 'text type mismatch'
    for key in ('authorized_dates', 'proposed_dates'):
        assert type(value[key]) is list, 'date array type mismatch'
        for day in value[key]:
            assert type(day) is str and re.fullmatch(r'\d{4}-\d{2}-\d{2}', day), 'date format mismatch'
            assert dt.date.fromisoformat(day).isoformat() == day, 'invalid date'
        assert len(value[key]) == len(set(value[key])), 'duplicate dates'


def parent_data():
    assert sha((PARENT / 'protocol.json').read_bytes()) == EXPECTED_PARENT_PROTOCOL
    assert sha((PARENT / 'raw.jsonl').read_bytes()) == EXPECTED_PARENT_RAW
    p = json.loads((PARENT / 'protocol.json').read_text())
    rows = [json.loads(line) for line in (PARENT / 'raw.jsonl').read_text().splitlines()]
    assert len(rows) == 384 and [r['index'] for r in rows] == list(range(384))
    assert sha(PARENT_RUNNER.read_bytes()) == p['runner_sha256']
    assert sha((PARENT / 'inputs.json').read_bytes()) == p['inputs_sha256']
    completion = json.loads((PARENT / 'completion.json').read_text())
    assert completion['rows'] == 384 and completion['raw_sha256'] == EXPECTED_PARENT_RAW
    jobs = [j for j in p['jobs'] if j['procedure'] == 'date_set_check' and j['framing'] == 'contaminated']
    assert len(jobs) == 96 and [j['index'] for j in jobs] == list(range(3, 384, 4))
    assert len({j['base_id'] for j in jobs}) == 24
    assert len({tuple(j[k] for k in KEYS) for j in jobs}) == 96
    assert collections.Counter((j['proposal'], j['expression']) for j in jobs) == {
        ('authorized', 'explicit'): 24, ('authorized', 'paraphrased'): 24,
        ('extra_date', 'explicit'): 24, ('extra_date', 'paraphrased'): 24}
    for job in jobs:
        assert sha(job['prompt'].encode()) == job['prompt_sha256']
        for key, value in job.items():
            if key != 'prompt':
                assert rows[job['index']][key] == value
        assert rows[job['index']]['protocol_sha256'] == EXPECTED_PARENT_PROTOCOL
        assert rows[job['index']]['run_id'] == p['run_id']
    return p, jobs


def verify(p):
    parent, jobs = parent_data()
    assert p['jobs'] == jobs
    assert p['runner_sha256'] == sha(Path(__file__).read_bytes())
    assert p['audit_runner_sha256'] == sha(AUDITOR.read_bytes())
    assert p['parent_runner_sha256'] == parent['runner_sha256']
    assert p['inputs_sha256'] == parent['inputs_sha256']
    assert p['parent_protocol_sha256'] == EXPECTED_PARENT_PROTOCOL
    assert p['parent_raw_sha256'] == EXPECTED_PARENT_RAW
    assert p['parent_completion_sha256'] == sha((PARENT / 'completion.json').read_bytes())
    assert p['model'] == parent['model'] and p['model_digest'] == parent['model_digest']
    assert p['model_binding_sha256'] == canonical_sha({'model': p['model'], 'digest': p['model_digest']})
    assert p['schema'] == parent['schemas']['date_set_check']
    assert p['schema_sha256'] == canonical_sha(p['schema'])
    assert p['options'] == dict(parent['options'], num_predict=512)
    assert p['budget'] == {'max_inference_calls': 96, 'max_generated_tokens': 49152, 'max_wall_seconds': 7200}
    assert p['endpoint'] == parent['endpoint'] == 'http://127.0.0.1:11434/api/chat'
    assert p['selected_jobs'] == [{k: j[k] for k in ('index', 'prompt_sha256') + KEYS} for j in jobs]


def prepare():
    assert not OUT.exists(), 'never overwrite a frozen amendment'
    parent, jobs = parent_data()
    p = {'run_id': 'temporal-completion-20261011-' + uuid.uuid4().hex,
         'frozen_at': dt.datetime.now(dt.timezone.utc).isoformat(), 'status': 'frozen_before_inference',
         'supersedes_unexecuted_preflights': [{'protocol_path': str(ROOT / 'tmp/temporal-completion-20261011-v1/protocol.json'), 'protocol_sha256': 'a334cbe743a5da0492bc48b706028667e057accac45e6d6f5df2f5e51a47deba'}, {'protocol_path': str(ROOT / 'tmp/temporal-completion-20261011-v2/protocol.json'), 'protocol_sha256': 'eed3943ed94f8dc332a1971af0d7a4150d9fa0d7b684c13c8b50ebe8ebe50e39'}],
         'supersession_reason': '2h wall cap and independent completion/token/unresolved audit fixes, all before inference',
         'parent_run_id': parent['run_id'], 'parent_protocol_path': str(PARENT / 'protocol.json'),
         'parent_raw_path': str(PARENT / 'raw.jsonl'), 'inputs_path': str(PARENT / 'inputs.json'),
         'parent_protocol_sha256': EXPECTED_PARENT_PROTOCOL, 'parent_raw_sha256': EXPECTED_PARENT_RAW,
         'parent_completion_sha256': sha((PARENT / 'completion.json').read_bytes()),
         'parent_runner_sha256': parent['runner_sha256'], 'inputs_sha256': parent['inputs_sha256'],
         'runner_sha256': sha(Path(__file__).read_bytes()), 'audit_runner_sha256': sha(AUDITOR.read_bytes()),
         'model': parent['model'], 'model_digest': parent['model_digest'],
         'model_binding_sha256': canonical_sha({'model': parent['model'], 'digest': parent['model_digest']}),
         'schema': parent['schemas']['date_set_check'],
         'schema_sha256': canonical_sha(parent['schemas']['date_set_check']),
         'options': dict(parent['options'], num_predict=512),
         'budget': {'max_inference_calls': 96, 'max_generated_tokens': 49152, 'max_wall_seconds': 7200},
         'endpoint': parent['endpoint'], 'network': 'literal IPv4 loopback only; proxies disabled; redirects forbidden',
         'selected_jobs': [{k: j[k] for k in ('index', 'prompt_sha256') + KEYS} for j in jobs],
         'jobs': jobs, 'order': 'parent indices ascending; original prompts verbatim',
         'stopping_rule': 'one attempt per selected job; no retry/replacement; retain API/schema/budget errors; interrupted run cannot resume',
         'selection': 'all 96 contaminated date_set_check jobs, regardless of parent success/error; 24 bases x 2 proposals x 2 expressions',
         'analysis': 'paired 256-versus-512 completion sensitivity only; valid typed nonempty extracted sets use proposed subset authorized; invalid/missing/empty fails closed; oracle checks only score exact extraction and false approvals; no true-grant substitution; preserve planned denominators; template-dependent development data'}
    p['model_tags_before_freeze'] = check_model(p)
    verify(p)
    OUT.mkdir(parents=True)
    dump(OUT / 'protocol.json', p)
    print(json.dumps({'protocol_path': str(OUT / 'protocol.json'), 'protocol_sha256': sha((OUT / 'protocol.json').read_bytes()),
                      'jobs': len(jobs), 'runner_sha256': p['runner_sha256'], 'audit_runner_sha256': p['audit_runner_sha256'],
                      'schema_sha256': p['schema_sha256'], 'model_binding_sha256': p['model_binding_sha256'],
                      'parent_protocol_sha256': EXPECTED_PARENT_PROTOCOL, 'parent_raw_sha256': EXPECTED_PARENT_RAW,
                      'inputs_sha256': p['inputs_sha256'], 'budget': p['budget']}))


def execute():
    protocol_bytes = (OUT / 'protocol.json').read_bytes()
    p = json.loads(protocol_bytes)
    verify(p)
    check_model(p)
    start = time.monotonic()
    calls = reserved = accounted = 0
    with (OUT / 'raw.jsonl').open('x') as f:
        for ordinal, job in enumerate(p['jobs'], 1):
            row = {k: v for k, v in job.items() if k != 'prompt'}
            row.update(run_id=p['run_id'], parent_run_id=p['parent_run_id'], protocol_sha256=sha(protocol_bytes),
                       response=None, decision=None, error='', error_kind='', attempted=False,
                       started_at=dt.datetime.now(dt.timezone.utc).isoformat())
            try:
                assert time.monotonic() - start < p['budget']['max_wall_seconds'], 'wall budget exhausted'
                assert calls < 96 and reserved + 512 <= 49152, 'inference/token budget exhausted'
                row['attempted'] = True
                calls += 1
                reserved += 512
                row['response'] = api('/api/chat', {'model': p['model'], 'messages': [{'role': 'user', 'content': job['prompt']}],
                                                  'stream': False, 'format': p['schema'], 'options': p['options']})
                value = json.loads(row['response']['message']['content'])
                validate_value(value)
                row['decision'] = value
                authorized, proposed = set(value['authorized_dates']), set(value['proposed_dates'])
                row['extracted_subset_approve'] = proposed <= authorized
                row['fail_closed_subset_approve'] = bool(authorized) and bool(proposed) and proposed <= authorized
            except Exception as error:
                row['error'] = f'{type(error).__name__}: {error}'
                row['error_kind'] = 'budget_skipped' if not row['attempted'] else ('api' if row['response'] is None else 'schema')
            if row['attempted']:
                accounted += (row['response'] or {}).get('eval_count', 512)
            row['finished_at'] = dt.datetime.now(dt.timezone.utc).isoformat()
            f.write(json.dumps(row, ensure_ascii=False) + '\n')
            f.flush()
            os.fsync(f.fileno())
            if ordinal % 12 == 0:
                print(f'completed={ordinal}/96 inference_calls={calls} reserved_tokens={reserved} accounted_tokens={accounted}', flush=True)
    dump(OUT / 'completion.json', {'rows': 96, 'inference_calls': calls, 'reserved_tokens': reserved,
                                  'generated_tokens_accounted': accounted, 'wall_seconds': time.monotonic() - start,
                                  'model_tags_after': check_model(p), 'raw_sha256': sha((OUT / 'raw.jsonl').read_bytes()),
                                  'protocol_sha256': sha(protocol_bytes)})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['prepare', 'verify', 'execute'])
    mode = parser.parse_args().mode
    if mode == 'prepare':
        prepare()
    elif mode == 'verify':
        verify(json.loads((OUT / 'protocol.json').read_text()))
        print('frozen protocol bindings verified; no inference performed')
    else:
        execute()

