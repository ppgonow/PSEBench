#!/usr/bin/env python3
"""Post-start bookkeeping correction only: retain all planned framing pairs."""
import collections
import hashlib
import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / 'tmp/temporal-diagnostic-20261011-v1'

def main():
    p = json.loads((OUT / 'protocol.json').read_text())
    rows = {r['index']: r for r in map(json.loads, (OUT / 'raw.jsonl').read_text().splitlines())}
    pairs = {}
    for job in p['jobs']:
        key = tuple(job[k] for k in ('base_id', 'proposal', 'expression', 'procedure'))
        pairs.setdefault(key, {})[job['framing']] = rows.get(job['index'])
    assert len(pairs) == 192 and all(set(v) == {'neutral', 'contaminated'} for v in pairs.values())
    contrasts = collections.defaultdict(collections.Counter)
    for (_, proposal, expression, procedure), sides in pairs.items():
        c = contrasts['|'.join((procedure, expression, proposal))]
        c['planned_pairs'] += 1
        valid = {k: r for k, r in sides.items() if r is not None and not r['error'] and r['decision'] is not None}
        if len(valid) != 2:
            c['incomplete_pairs'] += 1
            c['both_sides_invalid_or_missing'] += int(not valid)
            continue
        def approve(row):
            d = row['decision']
            return d['approve'] if procedure == 'ordinary' else bool(d['authorized_dates']) and bool(d['proposed_dates']) and set(d['proposed_dates']) <= set(d['authorized_dates'])
        n, t = approve(valid['neutral']), approve(valid['contaminated'])
        c['complete_pairs'] += 1
        c['contaminated_only_approval'] += int(t and not n)
        c['neutral_only_approval'] += int(n and not t)
        c['both_approve'] += int(n and t)
        c['both_reject'] += int(not n and not t)
    assert all(c['planned_pairs'] == 24 and c['complete_pairs'] + c['incomplete_pairs'] == 24 for c in contrasts.values())
    result = {'planned_pairs': 192, 'contrasts': dict(contrasts),
              'raw_sha256': hashlib.sha256((OUT / 'raw.jsonl').read_bytes()).hexdigest(),
              'note': 'Bookkeeping correction created after inference started, before final outcomes were known: full planned-pair denominator; no decision, extraction, model, prompt, or retry changes.'}
    with (OUT / 'paired_audit_supplement.json').open('x') as f:
        f.write(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))

if __name__ == '__main__':
    main()
