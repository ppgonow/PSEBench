#!/usr/bin/env python3
"""Independent paired audit of the local temporal 256/512 completion amendment."""
import collections
import datetime as dt
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT / 'tmp/temporal-diagnostic-20261011-v1'
OUT = ROOT / 'tmp/temporal-completion-20261011-v2'
KEYS = ('base_id', 'proposal', 'expression', 'framing', 'procedure')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def outcome(row, base, proposal):
    actual_authorized = set(base['canonical_grant'])
    actual_proposed = set(base['requests'][proposal]['dates'])
    result = {'present': row is not None, 'attempted': bool(row and row['attempted']),
              'schema_valid': False, 'fail_closed_subset_approve': False,
              'authorized_dates': None, 'proposed_dates': None,
              'authorized_extraction_exact': False, 'proposed_extraction_exact': False,
              'both_extractions_exact': False, 'false_approval': False,
              'false_rejection': proposal == 'authorized'}
    if row is None:
        result.update(error_kind='missing', error='missing planned row', done=None, done_reason=None, eval_count=None)
        return result
    response = row['response'] or {}
    result.update(error_kind=row['error_kind'], error=row['error'], done=response.get('done'),
                  done_reason=response.get('done_reason'), eval_count=response.get('eval_count'))
    try:
        value = json.loads(response['message']['content'])
        assert type(value) is dict and set(value) == {'authorized_dates', 'proposed_dates', 'reason', 'evidence'}
        assert all(type(value[k]) is str for k in ('reason', 'evidence'))
        for field in ('authorized_dates', 'proposed_dates'):
            assert type(value[field]) is list
            for date in value[field]:
                assert type(date) is str and re.fullmatch(r'\d{4}-\d{2}-\d{2}', date)
                assert dt.date.fromisoformat(date).isoformat() == date
            assert len(value[field]) == len(set(value[field]))
    except (AssertionError, ValueError, TypeError, KeyError):
        assert row['decision'] is None and row['error'], 'invalid response mislabeled valid'
        return result
    assert not row['error'] and value == row['decision'], 'valid response mislabeled error'
    authorized, proposed = set(value['authorized_dates']), set(value['proposed_dates'])
    raw_subset = proposed <= authorized
    approved = bool(authorized) and bool(proposed) and raw_subset
    assert raw_subset == row['extracted_subset_approve']
    if 'fail_closed_subset_approve' in row:
        assert approved == row['fail_closed_subset_approve']
    result.update(schema_valid=True, authorized_dates=sorted(authorized), proposed_dates=sorted(proposed),
                  authorized_extraction_exact=authorized == actual_authorized,
                  proposed_extraction_exact=proposed == actual_proposed,
                  both_extractions_exact=authorized == actual_authorized and proposed == actual_proposed,
                  raw_subset_approve=raw_subset, fail_closed_subset_approve=approved,
                  empty_authorized=not authorized, empty_proposed=not proposed,
                  proposed_dates_omitted=bool(actual_proposed - proposed),
                  unauthorized_extra_omitted=bool((actual_proposed - actual_authorized) - proposed),
                  false_approval=approved and proposal == 'extra_date',
                  false_rejection=not approved and proposal == 'authorized')
    return result


def main():
    p = json.loads((OUT / 'protocol.json').read_text())
    pp = json.loads((PARENT / 'protocol.json').read_text())
    assert sha(PARENT / 'protocol.json') == p['parent_protocol_sha256']
    assert sha(PARENT / 'raw.jsonl') == p['parent_raw_sha256']
    assert sha(PARENT / 'inputs.json') == p['inputs_sha256']
    assert sha(ROOT / 'analysis/run_temporal_completion_20261011_v2.py') == p['runner_sha256']
    assert sha(Path(__file__)) == p['audit_runner_sha256']
    assert sha(ROOT / 'analysis/run_temporal_diagnostic_20261011_v1.py') == p['parent_runner_sha256'] == pp['runner_sha256']
    assert sha(PARENT / 'completion.json') == p['parent_completion_sha256']
    assert p['model'] == pp['model'] and p['model_digest'] == pp['model_digest']
    assert p['schema'] == pp['schemas']['date_set_check']
    assert p['options'] == dict(pp['options'], num_predict=512)
    assert p['budget'] == {'max_inference_calls': 96, 'max_generated_tokens': 49152, 'max_wall_seconds': 7200}
    for obj, expected in [(p['schema'], p['schema_sha256']),
                          ({'model': p['model'], 'digest': p['model_digest']}, p['model_binding_sha256'])]:
        assert hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest() == expected
    assert p['jobs'] == [j for j in pp['jobs'] if j['procedure'] == 'date_set_check' and j['framing'] == 'contaminated']
    old = {r['index']: r for r in map(json.loads, (PARENT / 'raw.jsonl').read_text().splitlines())}
    new_rows = list(map(json.loads, (OUT / 'raw.jsonl').read_text().splitlines()))
    assert len({r['index'] for r in new_rows}) == len(new_rows)
    assert [r['index'] for r in new_rows] == sorted(r['index'] for r in new_rows)
    assert set(r['index'] for r in new_rows) <= set(j['index'] for j in p['jobs'])
    new = {r['index']: r for r in new_rows}
    completion_path = OUT / 'completion.json'
    if completion_path.exists():
        completion = json.loads(completion_path.read_text())
        assert completion['rows'] == len(new_rows) == 96
        assert completion['raw_sha256'] == sha(OUT / 'raw.jsonl')
        assert completion['protocol_sha256'] == sha(OUT / 'protocol.json')
        assert completion['inference_calls'] == sum(r['attempted'] for r in new_rows) <= 96
        assert completion['reserved_tokens'] == completion['inference_calls'] * 512 <= 49152
        assert completion['generated_tokens_accounted'] <= 49152
        assert any(m['name'] == p['model'] and m['digest'] == p['model_digest'] for m in completion['model_tags_after']['models'])
    inputs = {x['base_id']: x for x in json.loads((PARENT / 'inputs.json').read_text())}
    summary = {'256': collections.Counter(), '512': collections.Counter()}
    cells = collections.defaultdict(lambda: {'256': collections.Counter(), '512': collections.Counter()})
    transitions = collections.Counter()
    paired = []
    for job in p['jobs']:
        row = {'index': job['index'], 'key': {k: job[k] for k in KEYS}, 'prompt_sha256': job['prompt_sha256']}
        assert hashlib.sha256(job['prompt'].encode()).hexdigest() == job['prompt_sha256']
        for label, records, protocol_hash, run_id in [('256', old, p['parent_protocol_sha256'], pp['run_id']),
                                                    ('512', new, sha(OUT / 'protocol.json'), p['run_id'])]:
            record = records.get(job['index'])
            if record is not None:
                assert record['protocol_sha256'] == protocol_hash and record['run_id'] == run_id
                for field, value in job.items():
                    if field != 'prompt':
                        assert record[field] == value
            result = outcome(record, inputs[job['base_id']], job['proposal'])
            row[label] = result
            cell_key = job['proposal'] + '|' + job['expression']
            for counter in (summary[label], cells[cell_key][label]):
                counter['planned'] += 1
                for field in ('present', 'attempted', 'schema_valid', 'authorized_extraction_exact', 'proposed_extraction_exact',
                              'both_extractions_exact', 'fail_closed_subset_approve', 'false_approval', 'false_rejection',
                              'empty_authorized', 'empty_proposed', 'proposed_dates_omitted', 'unauthorized_extra_omitted'):
                    counter[field] += int(result.get(field, False))
                counter['error_' + (result['error_kind'] or 'none')] += 1
                counter['done_reason_' + str(result['done_reason'])] += 1
                counter['incomplete_response'] += int(result['attempted'] and result['done'] is not True)
        old_result, new_result = row['256'], row['512']
        transitions[f"schema_valid_{old_result['schema_valid']}_to_{new_result['schema_valid']}"] += 1
        transitions[f"approval_{old_result['fail_closed_subset_approve']}_to_{new_result['fail_closed_subset_approve']}"] += 1
        transitions['new_false_approvals'] += int(new_result['false_approval'] and not old_result['false_approval'])
        transitions['removed_false_approvals'] += int(old_result['false_approval'] and not new_result['false_approval'])
        row['both_schema_valid'] = old_result['schema_valid'] and new_result['schema_valid']
        row['authorized_sets_equal'] = row['both_schema_valid'] and old_result['authorized_dates'] == new_result['authorized_dates']
        row['proposed_sets_equal'] = row['both_schema_valid'] and old_result['proposed_dates'] == new_result['proposed_dates']
        for field in ('both_schema_valid', 'authorized_sets_equal', 'proposed_sets_equal'):
            transitions[field] += int(row[field])
        paired.append(row)
    result = {'run_id': p['run_id'], 'protocol_sha256': sha(OUT / 'protocol.json'),
              'raw_sha256': sha(OUT / 'raw.jsonl'), 'parent_protocol_sha256': p['parent_protocol_sha256'],
              'parent_raw_sha256': p['parent_raw_sha256'], 'planned': 96, 'rows': len(new_rows),
              'completion_present': completion_path.exists(),
              'missing_indices': [j['index'] for j in p['jobs'] if j['index'] not in new],
              'summary': summary, 'cells': dict(cells), 'transitions': transitions, 'paired': paired,
              'interpretation': p['analysis']}
    with (OUT / 'audit.json').open('x') as f:
        f.write(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({k: result[k] for k in ('planned', 'rows', 'missing_indices', 'summary', 'transitions')}))


if __name__ == '__main__':
    main()

