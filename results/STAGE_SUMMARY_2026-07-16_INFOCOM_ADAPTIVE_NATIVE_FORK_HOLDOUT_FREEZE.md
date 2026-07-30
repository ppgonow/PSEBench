# Adaptive Native Fork Holdout Freeze (2026-07-16)

This holdout was generated after the development amendment and before any
holdout API request.

## Frozen matrix

- 80 unique scenarios: 20 each for cron, file, calendar, and recipient;
- requested aliases: `gpt-5.5` and `grok-4.5`;
- 160 shared model/scenario units, each forked into permissive and IACG
  branches when exposure is valid;
- neutral native-tool prompt, shared first proposal, and native continuation;
- 6-turn maximum, 2 transient retries, 3-second minimum inter-request delay;
- cumulative HTTP-attempt ceiling: 1,600;
- local SQLite sandbox only; no production service or account;
- outcomes fixed by `analysis/summarize_adaptive_native_fork.py`.

## Frozen hashes

- holdout manifest: `bd158077336f784bcdaa55bb8f7378043b3e40961166f9fb0e1f54b8f9a4e8a5`;
- generator: `8cf38063cb7eac68b0a2e73f4cdbded05479a5d021cf1303a56b33071e112802`;
- fork runner: `cfed04bd4bdfd9b3b655d55425046a346ca719a8affcc097550b561ef2e93f15`;
- summarizer: `a8b57c32e5b252eb5c7f2132265025e2396ebef1a3f425743a0165ec3fe2dfc5`;
- development amendment: `0ecdde3de6bb028fbfd91707699fb34396c32b1eab95d31d3f43f919474e0bc4`.

No holdout row may be removed, replaced, or regenerated after the first API
request. Infrastructure failures remain in raw JSONL and are recovered only by
resuming the same fixed key under the same attempt ceiling.
