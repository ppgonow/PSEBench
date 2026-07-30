# INFOCOM 2027 submission readiness (2026-07-17)

This report supersedes the 2026-07-16 readiness snapshot after completion of
the adaptive native shared-proposal holdout and its pre-registered
schema-neutral replication.

## Quantitative evidence freeze

The prior schema-cue gap is closed by the pre-registered same-scenario neutral
replication. All 160 units have valid native exposure and paired
permissive/IACG branches. In the requested `grok-4.5` condition,
permissive/IACG ASR is 35/80 versus 0/80 (two-sided exact McNemar
`p=5.820766091346741e-11`), while primary TCR is 61/80 versus 75/80
(`p=0.0001220703125`). IACG preserves or recovers the primary task in 30/35
units with any unsafe proposal. The requested `gpt-5.5` condition has 2/80
versus 0/80 ASR (`p=0.5`) and 78/80 versus 79/80 primary TCR (`p=1`).

The strong native treatment signal occurs in Grok file and recipient units;
the two GPT discordances are recipient units. Neither alias produces an unsafe
cron or calendar proposal. Both aliases share one self-hosted compatible relay;
returned metadata matches the requested alias in 921/921 successful neutral-run
responses but does not authenticate upstream model identity or establish
cross-provider robustness. The earlier 288-unit provenance-marking matrix
remains a prompt-hardening ablation because it has no unsafe proposal.

A post-run protocol audit found that the adaptive v1 system prompt was neutral
but its inherited read-tool description labeled returned content untrusted. V1
is therefore retained as a separate provenance-marked-schema condition. Its
Grok result remains 25/80 versus 0/80 ASR and 65/80 versus 78/80 primary TCR;
it is not pooled with or substituted for the neutral replication.

The independent neutral-run audit matches all 330 SQLite commits to the 160
final units. Its timestamp-free public ledger export exactly reproduces the
same detail, per-boundary, paired, and metadata tables from the sanitized final
JSONL. The separate v1 public ledger continues to reproduce its 328 commits.

The post-hoc native model extension then completed the same schema-neutral
protocol for `gpt-5.4` and `gpt-5.6-sol`. GPT-5.4 has 19/79 versus 0/79 ASR
(`p=3.814697265625e-06`) and GPT-5.6-sol has 4/80 versus 0/80 (`p=0.125`).
These requested aliases share the same relay and manifest, so the extension is
reported separately rather than pooled with the original two-alias result. Its
independent audit matches 317 SQLite commits and 941/941 returned-alias
metadata records. The official AgentDojo and AgentDojo-Core no-API rechecks
also pass independently at 32 and 21 tests; neither is a live performance row.

The public candidate-action method comparison covers 135 scenarios, 110
attacks, eight policies, and 1,080 deterministic rows. PAuth-style and
PCAS-style adaptations tie IACG at 0/110 ASR and 135/135 TCR; RTBAS/IFC-style
confirmation reaches the same ASR/TCR with 110/135 confirmations. The main
paper reports these as typed adaptations, not official reproductions or an
IACG superiority claim. The public generator and sanity gate byte-reproduce
the detail, overall, by-slice, and Markdown outputs.

## Paper gate

- Review PDF: `output/pdf/PSEBench_INFOCOM2027_submission_draft.pdf`.
- SHA-256: `03fc70bb5494405594ff3610f7f7fd37a842c7562d422ab89b1f1a22c7ebeaac`.
- Length: 9 US-Letter pages; references begin on page 8.
- Abstract: 191 words, within the 200-word EDAS metadata limit.
- Anonymous title block and metadata; 17 unique fonts, all embedded.
- `Use of AI Disclosure` begins on page 8.
- No overfull box, undefined reference, credential, local path, clipping,
  overlap, or broken glyph was observed.
- All nine pages were rendered and visually inspected. The vector IACG figure,
  commit-binding algorithm, neutral native table, and evidence-tier row are
  legible and within margins.

The automated gate reports 17/17 PDF/source checks passing. The claim audit
reports 68/68 checks passing, and the reviewer-response audit reports 9/9
evidence/manuscript checks passing.

The citation audit resolves all 25 compiled citation keys and checks their
public primary records. It corrects the current FORGE metadata and description,
the ReAct proceedings year, Task Shield's official ACL entry, OpenAgentSafety's
arXiv date, and several title/author formatting issues. BibTeX and LaTeX compile
without missing entries, undefined citations, or reference-layout errors.

## Artifact gate

The worktree anonymous ZIP contains sanitized final traces, the frozen holdout,
runner and generator, frozen summarizer, independent audit, timestamp-free
ledger export, tests, and all derived tables. It excludes paper sources, build
outputs, local configuration, raw relay logs, SQLite databases, credentials,
and endpoint identifiers.

The archive audit reports 20/20 PDF/source/artifact checks passing. A fresh
extraction independently passes 75 unit tests, 1004 scenario schemas, three
native aggregation gates, the 328-commit v1, 330-commit neutral, and 317-commit
GPT-5.4/GPT-5.6 public ledger audits, 68 claim checks, and nine
reviewer-response checks. The archive hash is
intentionally recorded outside the archive to avoid self-reference.

## Remaining external work

1. Register the paper in EDAS by the internal deadline of 2026-07-24 18:00 CST,
   entering the 191-word abstract, complete ordered author list, and conflicts.
2. Verify originality, the INFOCOM five-submission cap, author ordering, and
   every author's acceptance of the AI disclosure.
3. Host the ZIP through an account-neutral anonymous channel and inspect the
   reviewer view while logged out. Do not publish an extended technical report.
4. Run a logged-out title/project-name search to check that public pages do not
   defeat double blindness.
5. Obtain an independent author read focused on threat-model accuracy,
   statistical claim boundaries, citations, and table legibility.
6. Confirm that every relay credential disclosed in chat is revoked. The local
   `.env.local` file is excluded from the repository, PDF, and archive.
7. Upload by the internal full-paper deadline of 2026-07-30 18:00 CST, download
   EDAS's stored PDF, and rerun the submission audit on that exact copy.

Additional API experiments should not enter the main paper after this neutral
replication freeze unless they are pre-registered, materially address an
explicit remaining claim, and leave enough time for complete reporting. The
highest-value work is now independent technical review, anonymous hosting, and
EDAS preparation.
