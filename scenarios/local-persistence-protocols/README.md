# Frozen local persistence source protocols

These two files are byte-identical copies of the frozen source protocols used
by the unified structured-authorization experiment. They retain the original
scenario IDs, prompts, jobs, model metadata, and runner/observer bindings.
They contain experimental inputs, not model response logs.

| Released file | Original relative path | SHA-256 |
| --- | --- | --- |
| `source_v1.json` | `tmp/local-7b-persistence-20261011-v1/protocol.json` | `099690c54c5050039543b3ba8eb213a1b04057cefba53dd4f58cbdbcbb7c42f3` |
| `source_v2.json` | `tmp/local-persistence-expansion-20261011-v2/protocol.json` | `0e8f9e2ce34be6596f91b31593f2fc7ea872d1ce01cba92bbab5fd93bfc1d86c` |

Prepare the original relative paths in a clean checkout with:

```bash
python3 analysis/prepare_local_persistence_protocols.py
```

The preparer verifies both hashes before creating missing files. Existing
matching inputs are preserved; conflicting files cause an error. The unified
unit tests invoke it automatically. This packaging step makes lineage checks
available offline without changing any historical protocol or result.
