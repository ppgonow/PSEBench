# Live CalDAV holdout: design freeze, 2026-10-09

Normative design: `analysis/live_caldav_protocol_v1.json`.
Corpus: `scenarios/live-caldav-heldout-20261009-v1/corpus.json`.
Freeze inventory: `analysis/live_caldav_design_v1_SHA256.json`.

This is an offline design freeze, not an execution-ready preregistration or
completed live experiment. No API credential is read and no network request is
made by the preparation/audit scripts. The next execution amendment must bind
at least two independently operated direct model endpoints and exact model IDs
before any study outcome. Existing confirmation aliases are not silently
substituted. Model and provider effects cannot be separated without a crossed
design. Radicale is a tool provider, not an independent model provider.

The corpus contains 30 template pairs: 10 recurrence, 10 collection routing,
and 10 extra-event attacks, each with a clean counterpart. All 60 IDs are new;
template reuse and synthetic construction limit external validity. There are
180 trajectories per model/provider (60 scenarios x three conditions). Clean
and injected members have identical trusted requests/grants. Conditions are
permissive, prompt-only and IACG; the latter two share the same hardened prompt.
All conditions get independent conversations and clean provider state.

The protocol freezes denominator, failure, retry, resume, observer, persistent
SQLite ledger and statistical rules. Neither zero ASR nor baseline failure is
an audit requirement. Outcomes are not computed by this design dry-run.

Run from the repository root:

```sh
python3 runner/prepare_live_caldav_holdout.py --dry-run
python3 analysis/audit_live_caldav_design.py
```

`--build` is a one-time corpus creation operation and refuses an existing file.
There is deliberately no live mode in this preparation tool.

Before live execution, implement and hash the live runner, persistent ledger,
and separate post-state observer, then test crash reconciliation and unknown
observations offline. Existing `radicale_caldav_service.py` is a reference only:
its 2026 REPORT window is incompatible with this corpus's January 2031 dates;
its parser omits event times/RDATE/EXDATE; its REPORT counting is collection-wide
rather than UID-specific. Reusing it unchanged would invalidate outcome
measurement. A new adapter must retain raw ICS/XML before provider teardown and
observe both collections, including extra resources. Local SQLite recording
does not make the remote CalDAV PUT atomic with ledger writes.

The confirmation amendment remains a separate decision-only experiment.
This work does not alter its frozen files or the manuscript/Figure 1.
