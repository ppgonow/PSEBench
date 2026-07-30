# INFOCOM native service-commit bridge implementation freeze (2026-07-21)

## Frozen implementation

The three-process native-proposal service-commit bridge is frozen before its
single formal 768-row execution. The runner starts distinct authorization,
gateway, and effect processes on `127.0.0.1`; checks relay health before the
first row; applies authorization-version revocation through the authorization
service; observes the 1,000 ms mutation-active interval; waits 10 ms; and then
submits the unchanged native effect through the gateway. Receipt verification
and effect insertion occur in one effect-service SQLite transaction.

Formal output paths do not exist at freeze time. The runner refuses to replace
any existing formal output. It writes each attempt append-only, retains a
failure record before aborting, and creates the final JSONL/CSV artifacts only
after the complete matrix passes in-process validation and temporary-state
cleanup.

## Code hashes

| File | SHA-256 |
|---|---|
| `runner/run_native_service_commit_bridge.py` | `4a294b242ed05d88b6f40920b468e2ad6f9c28d97d46069f465974d0e14c9f07` |
| `analysis/audit_native_service_commit_bridge.py` | `1d2d59577c3735827c4c4606c8a51f9664369312a1497de17787494f55bd5b14` |
| `tests/test_native_service_commit_bridge.py` | `4ce593bbd5612a7f42492e575678bb5efad13132c64befd72919bb885a44ff90` |
| `tests/test_audit_native_service_commit_bridge.py` | `e1c55e20de8108685b01fedd30de323a63888d38ff44807b6c02fccb9eb5fb50` |
| `runner/service_integrated_commit.py` | `20c160f6e255013d9019d410e75be9e3f245394f0e6cd93ca7f26a288dc713ba` |
| `runner/commit_binding.py` | `3c6857987183633a83d5cd2b76a633b529a2651eec1c86fe37b31dd4ee1f2600` |
| `runner/effect_boundary.py` | `2a74aa33d4afac769e0c85f3298058779ad4aabd68db9638f7bc0e4924078948` |

## Pre-run verification

- Frozen input validation: 192 unique authorized clean proposals, 48 per
  requested alias; all input, manifest, and scenario hashes match.
- Four-cell three-process smoke test: cached stable/revoked commit;
  receipt-bound stable commits and revoked blocks before the ledger.
- Hash-chain and distinct-role gates pass in the service smoke test.
- Independent audit accepts a complete 768-row synthetic fixture and detects
  a deliberately failed effect-hash gate.
- Repository unit tests: 131/131 pass.

No model API, SSH target, public service, real account, or production effect is
used by this experiment. Any implementation or timing change after this freeze
requires a dated amendment and a fresh formal output prefix.
