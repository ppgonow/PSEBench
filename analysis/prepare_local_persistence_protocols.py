"""Materialize byte-identical frozen lineage inputs for offline reconstruction."""
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BINDINGS = (
    ('source_v1.json', 'tmp/local-7b-persistence-20261011-v1/protocol.json',
     '099690c54c5050039543b3ba8eb213a1b04057cefba53dd4f58cbdbcbb7c42f3'),
    ('source_v2.json', 'tmp/local-persistence-expansion-20261011-v2/protocol.json',
     '0e8f9e2ce34be6596f91b31593f2fc7ea872d1ce01cba92bbab5fd93bfc1d86c'),
)


def prepare(root=ROOT):
    root = Path(root)
    planned = []
    for name, relative, expected in BINDINGS:
        source = root / 'scenarios/local-persistence-protocols' / name
        data = source.read_bytes()
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError(f'frozen source protocol digest mismatch: {source}')
        target = root / relative
        if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() != expected:
            raise ValueError(f'existing protocol differs from frozen input: {target}')
        planned.append((target, data))
    for target, data in planned:
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as handle:
                handle.write(data)
    return [target for target, _ in planned]


if __name__ == '__main__':
    print(f'Prepared {len(prepare())} frozen source protocols.')
