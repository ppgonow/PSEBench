# Adaptive native GPT-5.4/GPT-5.6 extension result (2026-07-18)

## Status and claim boundary

The frozen extension completed all 160 requested alias/scenario units through
the HTTPS OpenAI-compatible relay. It repeats the schema-neutral adaptive
native shared-proposal protocol on the already frozen 80-scenario manifest.
Because the original GPT-5.5/Grok-4.5 outcomes were known before this model
extension, these results are reported per alias and are not pooled with the
original two-alias replication or described as a prospectively selected
four-model effect. Requested aliases are relay conditions, not authenticated
upstream model identities or independent providers.

The two inert native protocol probes were excluded from all denominators. Each
returned exactly one valid native `tool_calls` object with no text-only fallback.

## Frozen execution

- Run ID: `adaptive-native-fork-schema-neutral-gpt54-gpt56-v1`.
- Manifest: `scenarios/adaptive-native-holdout/MANIFEST.csv`.
- Requested aliases, in order: `gpt-5.4`, then `gpt-5.6-sol`.
- Schema mode: `neutral`; 80 scenarios per alias, 20 each for cron, file,
  calendar, and recipient boundaries.
- Shared proposal fork: each native first proposal was reused in permissive and
  IACG branches with the same conversation state.
- Fixed limits: six turns, two retries, at least three seconds between attempts,
  HTTPS only, and a 1,600-attempt cumulative ceiling.
- HTTP attempts: 947; unresolved API errors: 0; raw rows/final units: 160/160.
- Effects: isolated local SQLite sandbox only; no production service was called.

One `gpt-5.4` calendar unit ended as `terminal_without_effect` after two valid
prefix responses and no effect proposal. It is retained as an observed model
outcome and excluded from paired fork denominators, giving 79 valid GPT-5.4
forks. No unit was discarded or rerun.

## Primary results

| Requested alias | Valid forks | Unsafe-any proposal | Permissive ASR | IACG ASR | Permissive TCR | IACG TCR | Exact paired ASR p |
|---|---:|---:|---:|---:|---:|---:|---:|
| `gpt-5.4` | 79/80 | 19/79 | 19/79 | 0/79 | 68/79 | 69/79 | 3.814697265625e-06 |
| `gpt-5.6-sol` | 80/80 | 4/80 | 4/80 | 0/80 | 77/80 | 80/80 | 0.125 |

For GPT-5.4, the paired primary-TCR contrast is 68/79 versus 69/79
(`p=1`). For GPT-5.6-sol it is 77/80 versus 80/80 (`p=0.25`). IACG recovers
the primary task in 9/19 GPT-5.4 unsafe-any units and 4/4 GPT-5.6-sol unsafe-any
units. These are descriptive per-alias extension results; the GPT-5.6-sol ASR
contrast is not statistically distinguishable at this bounded sample size.

## Boundary decomposition

Unsafe-any proposal counts (valid exposure denominator) are:

| Requested alias | Cron | File | Calendar | Recipient |
|---|---:|---:|---:|---:|
| `gpt-5.4` | 0/20 | 6/20 | 0/19 | 13/20 |
| `gpt-5.6-sol` | 0/20 | 3/20 | 0/20 | 1/20 |

Both aliases therefore show the same qualitative localization as the earlier
native conditions: the observed proposal-bearing signal is concentrated in
file and recipient boundaries, while zero cron/calendar proposal counts are
negative model conditions rather than demonstrated treatment effects.

## Independent integrity audit

The post-run audit was run with `--allow-terminal-without-effect`, a default-off
extension to the prior auditor that validates terminal units have no branches,
proposal effects, or SQLite commits while preserving the original strict mode.

- Final units audited: 160/160.
- SQLite commits matched to allowed trace calls: 317/317.
- SQLite jobs with commits: 308; unreferenced or missing commits: 0.
- Returned-model metadata: 941/941 matched the requested alias; mismatches: 0.
- Superseded API errors: 0.
- Claim audit: 68/68 paper/data checks passed after adding the public candidate-action method comparison.

The changed auditor was not used to replace or reinterpret the original 328- and
330-commit audits; the standard `scripts/sanity_check.sh` still passes those
two frozen conditions in strict mode.

## Provenance hashes

| Artifact | SHA-256 |
|---|---|
| Manifest | `bd158077336f784bcdaa55bb8f7378043b3e40961166f9fb0e1f54b8f9a4e8a5` |
| Protocol probe | `d0eb762dd9dcaaebd61dd946378041f2008db2e30d5ce85670bd4df3d1277620` |
| Sanitized final JSONL | `4239f5da8aec48d6436d1106dd5f23c3c402d09873e7cb00615d2cb4b71b23fe` |
| Summary CSV | `984347723a4e9b2f4529e6637ba3f5a66c4dc71b03ee398d3f3a2bcee617be52` |
| Paired CSV | `59ebdca3dcf01a5483fc10fb39f828602b949d2b69ee466a8cbbca8de66eb09b` |
| Attempt audit CSV | `869debfaa02dac1d8f84401951cd150a07c8026dc28caa0c747ae851ae2a63b3` |
| Independent audit detail | `35a111063a6c38d3e7b7ee77dcd0be846cbadb4b4e1d160ec99bd8549bce39f7` |
| Independent audit paired | `3c35e571aaba6f491884ab9a11017b39f90e31797dda10dc42e29b6823fe7a8b` |
| Independent audit integrity | `f88e5927abf448edc370f2a5490e464d8a0e1dfde02b747600eccb31976d3ab2` |
| Public ledger CSV | `92da201cc1365efea0a7c3cf8aaaa0f2e65ec2194d540f8edf1a63eedc6b631a` |
| Runner | `50d8502e86d5794ab0461d8b6614cb6d8cf0bd96f24c3ec92ebe3aec21b0702c` |
| Summarizer | `5b8d45bd09cba205bc2a9883edfc0a728655f8577146edefa7fb1dc0c4ba01b5` |
| Post-run auditor | `ac00f68c75d32fb72953d83505374b4d2872702a3e4c57c9c9f28b37e2309efb` |

Raw relay JSONL and the local SQLite database remain excluded from the
anonymous artifact. The sanitized final traces and public ledger are sufficient
to reproduce the reported counts and the read-only post-run audit.
