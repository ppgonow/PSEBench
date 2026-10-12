#!/usr/bin/env python3
"""Offline design audit, not a live result audit or provider witness."""
from collections import Counter, defaultdict
from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'runner'))
from prepare_live_caldav_holdout import PROTOCOL, CORPUS, schedule

FREEZE = ROOT / 'analysis/live_caldav_design_v1_SHA256.json'


def audit():
    hashes = json.loads(FREEZE.read_text())
    required = {'analysis/live_caldav_protocol_v1.json', 'runner/prepare_live_caldav_holdout.py', 'analysis/audit_live_caldav_design.py', str(CORPUS.relative_to(ROOT))}
    if set(hashes) != required:
        raise ValueError('incomplete freeze inventory')
    for name, expected in hashes.items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f'freeze mismatch: {name}')
    p = json.loads(PROTOCOL.read_text())
    rows = json.loads(CORPUS.read_text())
    ids = {r['scenario_id'] for r in rows}
    if len(ids) != 60 or len(rows) != 60:
        raise ValueError('expected 60 unique scenarios')
    if Counter(r['type'] for r in rows) != {'attack': 30, 'benign': 30}:
        raise ValueError('endpoint imbalance')
    pairs = defaultdict(list)
    for row in rows:
        pairs[row['template_id']].append(row)
        grant = row['trusted_grant']
        start = datetime.strptime(grant['DTSTART'], '%Y%m%dT%H%M%SZ')
        end = datetime.strptime(grant['DTEND'], '%Y%m%dT%H%M%SZ')
        if (end-start).total_seconds() != 1800 or grant['RRULE'] or grant['max_events'] != 1:
            raise ValueError('invalid bounded task')
        if grant['summary'] not in row['prompt'] or grant['collection'] not in row['prompt']:
            raise ValueError('grant/request disagreement')
    if len(pairs) != 30:
        raise ValueError('expected 30 templates')
    for pair in pairs.values():
        if len(pair) != 2 or {r['type'] for r in pair} != {'attack', 'benign'}:
            raise ValueError('incomplete clean/injected pair')
        for field in ('prompt', 'trusted_grant', 'family'):
            if pair[0][field] != pair[1][field]:
                raise ValueError(f'pair differs in {field}')
        if pair[0]['source_text'] == pair[1]['source_text']:
            raise ValueError('missing exposure contrast')
    if Counter(r['family'] for r in rows) != {'recurrence': 20, 'collection': 20, 'extra-event': 20}:
        raise ValueError('family imbalance')
    # Query only identifier lines; never ingest historical prompts or outcomes.
    lookup = subprocess.run(['rg', '--no-heading', '--no-filename', '-N',
        '-g', '*.yaml', '-g', '*.json', '-g', '!live-caldav-heldout-20261009-v1/**',
        r'^\s*(id:|"(scenario_id|case_id|id)"\s*:)', '.'],
        cwd=ROOT / 'scenarios', capture_output=True, text=True, check=False)
    if lookup.returncode not in (0, 1):
        raise ValueError('historical identifier scan failed')
    for scenario_id in ids:
        if scenario_id in lookup.stdout:
            raise ValueError('scenario ID overlaps prior corpus')
    jobs = schedule(p, rows)
    expected = {(i, c) for i in ids for c in ('permissive', 'prompt-only', 'IACG')}
    if len(jobs) != 180 or {(j['scenario_id'], j['condition']) for j in jobs} != expected:
        raise ValueError('invalid condition matrix')
    positions = Counter()
    for offset in range(0, len(jobs), 3):
        for position, job in enumerate(jobs[offset:offset+3]):
            positions[(job['condition'], position)] += 1
    if set(positions.values()) != {20}:
        raise ValueError('condition order imbalance')
    if p['status'] != 'design_frozen_execution_binding_pending' or p['model_provider_bindings']:
        raise ValueError('execution binding requires a separate amendment')
    return {'design_audit': 'passed', 'scenarios': 60, 'paired_templates': 30,
            'units_per_model_provider': 180, 'prior_id_overlap': 0,
            'live_ready': False, 'live_results_audited': False}


if __name__ == '__main__':
    print(json.dumps(audit(), sort_keys=True))
