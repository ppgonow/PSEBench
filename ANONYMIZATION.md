# Anonymous Submission Notes

This public artifact snapshot is intended to support double-blind review. The
repository contents avoid paper drafts, author names, compiled PDFs,
machine-local paths, credentials, live-service tokens, and local runner
configuration.

For a double-blind submission, do not provide a URL that reveals author identity
through the account name, organization name, commit metadata, issue tracker, or
repository settings. If the conference asks for an artifact URL during review,
mirror this repository snapshot through an anonymous artifact-sharing service or
otherwise provide an anonymized archive. The post-acceptance public release can
then point to the maintained project repository.

Before sharing an artifact URL with reviewers, rerun:

```bash
scripts/sanity_check.sh
git grep -n -I -E "(sk-[A-Za-z0-9]{8,}|/Users/|OPENAI_API_KEY|ANTHROPIC_AUTH_TOKEN)" -- .
```

To create a clean zip from the committed artifact snapshot:

```bash
scripts/make_anonymous_archive.sh
```

To audit a pre-commit review snapshot containing tracked files and non-ignored
new experiment files, while still excluding `src/`, `build/`, `output/`,
`tmp/`, local configuration, and other gitignored paths, run:

```bash
scripts/make_anonymous_archive.sh --worktree
```

After building the review PDF and archive, run the INFOCOM-specific gate:

```bash
python3 analysis/infocom_submission_audit.py \
  --pdf output/pdf/PSEBench_INFOCOM2027_submission_draft.pdf \
  --source src/main.tex \
  --artifact dist/PSEBench-anonymous-artifact.zip
```

This checks the official page limits, Letter page size, searchable text,
embedded fonts, anonymous title block and metadata, exact AI-disclosure title,
IEEEtran preamble, and archive scope/sensitive-data boundaries. Human checks
such as EDAS author metadata, conflicts, and account-neutral hosting remain
outside the script.

The adaptive native v1 and schema-neutral runs' raw relay JSONL and SQLite
databases are local audit inputs and must not enter the anonymous archive. The
public artifact uses sanitized final JSONL plus timestamp-free ledger CSVs for
both conditions; the sanity script reconstructs their released outcome tables
from those files in a clean extraction. Requested model aliases and matching
relay metadata are not claims of authenticated backend identity or independent
providers.

The multi-process commit experiment follows the same boundary: its raw JSONL
and SQLite database remain local, while the timestamp-free detail, summary,
paired, and integrity CSVs are public. The public audit reconstructs all counts
and pairings without relying on process-local clocks or the local database.

The remote-instance replication additionally keeps SSH configuration, raw host
identifiers, logs, HMAC material, SQLite data, and raw JSONL local. Its released
topology table contains only SHA-256 identities and non-identifying capability
fields. The anonymous artifact supports a daemon-free audit and does not enable
or require access to the original remote instances.

The PostgreSQL portability run similarly excludes its DSN, random password,
loopback port, container ID, database files, HMAC key, and logs. Released
metadata contains only the public image digest, backend/driver versions,
isolation level, and matrix row count; the independent audit requires no live
database or Docker service.

The asynchronous queue run excludes the temporary broker/effect SQLite files,
WAL files, HMAC key, loopback ports, process identifiers, and runtime logs. Its
released CSVs contain synthetic trial/scenario identifiers, logical gates,
decisions, counts, and non-identifying latency only; the public audit requires
no broker or effect process.

The Docker failover run additionally excludes its containers, bridge networks,
broker/effect databases, consumer state, runtime identities, HMAC key, ports,
and logs. Its public metadata contains only the pinned image digest, generic
bridge/loopback capabilities, four fault epochs, and matrix size. The released
detail records synthetic identifiers and logical outcome/gate fields; the audit
does not require Docker. Each 150-row cell shares one fault epoch, so the public
rows must not be represented as independent partition or crash events.

The generated archive is written under `dist/`, which is gitignored.

The official AgentDojo source checkouts are also excluded. The public artifact
contains only the frozen 16-case same-state manifest, source-relative task
locations, released derived CSVs, and the audit script. Its one non-example.com
address is the exact public synthetic fixture
`mark.black-2134@gmail.com`; the archive scanner permits only that full address,
not the `gmail.com` domain generally.
