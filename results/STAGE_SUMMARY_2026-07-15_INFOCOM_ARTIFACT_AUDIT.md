# INFOCOM Anonymous Artifact Audit (2026-07-15)

## Snapshot construction

The review snapshot was created with:

```bash
scripts/make_anonymous_archive.sh --worktree
```

This mode includes tracked files and non-ignored new experiment files. It
excludes paper sources and PDFs, build outputs, temporary renders, raw local
run directories, local runner configuration, credentials, and git history.
The default archive mode remains stricter and accepts only a clean committed
snapshot.

## Audit results

- No forbidden archive prefixes or local configuration files were present.
- Known author, affiliation, account, and machine-path tokens produced no
  matches in the archive payload.
- The credential scan found no OpenAI-style secret, hard-coded custom endpoint,
  or provider key. The archive builder and audit also reject logs, screenlogs,
  SQLite/database files, local credentials, and symlinks.
- The fresh cron and non-cron manifests and frozen rule hashes were present.
- The confirmation runner, summarizer, tests, and INFOCOM stage reports were
  present.
- The multi-tool generator, pre-registered-effect replay, derived summaries,
  tests, manifest, and frozen rule hash were present.
- The commit-binding generator, 150-scenario manifest, paired replay,
  lifecycle benchmark, derived summaries, tests, and frozen binding hash were
  present.
- The headline-claim audit script, source mapping, and stage report were
  present; data-layer reconstruction passed in the source-free archive.
- The minimal same-ID paired outcome table was present and regenerated all six
  independent-unit rows without exposing raw local run directories.
- The nine-item ACSAC review-response evidence map, automated audit, and
  explicit partial-status boundaries were present.
- The pre-request confirmation power/precision tables, paired framing
  summarizer, Holm correction, and descriptive-pilot interpretation were
  present.
- The completed same-endpoint native-tool matrix included 288 sanitized traces,
  288/288 primary-effect completions, 282/288 sender confirmations, request
  accounting, summary/paired tables, and explicit no-policy-effect and
  requested-alias interpretation.
- The final PDF/source/ZIP audit passed 20/20 checks over 1,255 archive entries.
- A clean source-free extraction discovered 64 unit tests: 63 executed and
  passed, while the localhost HTTP test was explicitly skipped because the
  managed sandbox forbids socket binding. It validated all 908 scenario files
  with zero missing required or recommended fields, reconstructed all 61
  INFOCOM numerical claims, and passed all nine review-response mappings.

## Boundary

This audit validates the local anonymous ZIP contents; it does not create or
host an anonymous reviewer URL. Regenerate and re-audit the archive after any
release change, then upload it through an account-neutral artifact-sharing
channel.
