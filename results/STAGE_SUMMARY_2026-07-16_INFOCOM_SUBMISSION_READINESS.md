# INFOCOM 2027 Submission Readiness (2026-07-16)

## Official sources and deadlines

This gate is based on the public INFOCOM 2027 pages retrieved on 2026-07-16:

- Call for papers: <https://infocom2027.ieee-infocom.org/call-papers>
- Submission guidelines: <https://infocom2027.ieee-infocom.org/submission-guidelines>
- EDAS submission: <https://edas.info/N34810>

Confirmed deadlines are 2026-07-24 23:59 AOE for paper registration/abstract
metadata and 2026-07-31 23:59 AOE for the full PDF. In China Standard Time
(UTC+8), these are 2026-07-25 19:59 and 2026-08-01 19:59, respectively. The
project should retain earlier internal deadlines rather than use the converted
hard deadlines as working targets.

## Confirmed review-submission requirements

- English PDF, at most 10 printed pages total.
- Main text, figures, tables, appendices, and all non-reference material at
  most 9 pages.
- Unmodified IEEEtran 1.8-family conference template, 10-point, US Letter,
  two-column layout, and default spacing/margins/fonts.
- Rigorous double-blind review: no author names, affiliations,
  acknowledgments, identifying funding/project text, or identity-bearing PDF
  metadata; self-citations remain in the third person.
- Searchable PDF with legible figures in black-and-white printing.
- EDAS metadata before registration closes: title, complete ordered author
  list, and abstract of at most 200 words.
- A section titled exactly `Use of AI Disclosure` within the first 9 pages
  when AI affected experiment design, data, analysis, software, figures,
  datasets, or other research artifacts. The disclosure must identify the
  system, purpose, contribution extent, and author validation.
- Original work not published or simultaneously submitted elsewhere. Each
  person may appear on at most five INFOCOM 2027 submissions.
- Anonymous data/code release is encouraged. An anonymous extended technical
  report is not permitted as additional paper content.

## Automated and visual gate

`analysis/infocom_submission_audit.py` checks the local PDF/source and optional
anonymous ZIP against the machine-verifiable requirements above.

Current review PDF:

- Path: `output/pdf/PSEBench_INFOCOM2027_submission_draft.pdf`
- SHA-256: `ec7d335bb0425340f5f8083ba042e352ed39b460f1453367b3c92e095c0bfb16`
- 9 pages, all 612 x 792 point US Letter.
- Extractable text on every page; no encryption, author metadata, local path,
  credential pattern, title-block identity marker, or acknowledgment section.
- 12 unique fonts, all embedded.
- IEEEtran V1.8b with `10pt, conference, letterpaper`; no detected margin,
  font-size, or line-spacing override.
- Source abstract is 198 words and can be used as the EDAS abstract.
- `Use of AI Disclosure` begins on page 8 and identifies OpenAI Codex, the
  development/editorial uses, requested GPT/Grok/Claude-labeled API conditions,
  lack of independent backend-identity authentication, and author validation.
- Compilation has no overfull box, undefined-reference, or LaTeX/package
  warning; the native evidence-tier row remains inside Table I.

All nine pages were rendered at 180 dpi and inspected. The anonymous title
page, figures, matrix, tables, native-result caveats, two-column flow, AI
disclosure, and references show no clipping, overlap, broken glyph, or margin
overflow. The final reference page is balanced across two columns using
IEEEtran's reference trigger. Figure 3 uses the smallest labels in the paper,
but they remain legible and unclipped.

The anonymous worktree ZIP is regenerated after this report is added. Its hash
is intentionally not embedded inside the archive because doing so would make
the archive hash self-referential. The audit command prints both final hashes.

## Human and external gates

Automation cannot complete these items:

1. By the internal deadline of 2026-07-24 18:00 CST, create/register the EDAS
   paper, paste the 198-word abstract, enter the complete ordered author list,
   and update all non-automatic conflicts of interest.
2. Verify originality, the five-submission cap for every author, and the exact
   author ordering. INFOCOM/ComSoc does not permit author-list changes after
   submission for review.
3. Search the paper title and project name from a logged-out browser and ensure
   no identity-bearing project page defeats double blindness.
4. Host the artifact only through an account-neutral anonymous channel, then
   inspect the public reviewer view while logged out. Do not link an extended
   technical report.
5. Confirm that the AI disclosure accurately describes every system used and
   that all named authors accept responsibility for the submission.
6. Upload the frozen PDF to EDAS by the internal deadline of 2026-07-30 18:00
   CST, download EDAS's stored copy, and rerun the PDF audit on that copy.

## Remaining experiment decision

The optional 120-call confirmation-framing matrix remains a descriptive pilot,
not a powered null-effect test. It may run only under its pre-request analysis
plan, with a newly rotated environment-provided key, sequential rate limiting,
and no tool execution. Do not reuse the credential disclosed in chat, select
models after seeing outcomes, expand the sample post hoc, or let this optional
pilot delay paper registration and PDF freeze.

Working schedule:

- 2026-07-16 to 2026-07-20: run and analyze only the pre-registered optional
  pilot if a rotated key is available; otherwise close the experiment branch.
- 2026-07-21: freeze quantitative evidence and regenerate all claim tables.
- 2026-07-22 to 2026-07-23: final technical and citation review.
- 2026-07-24 18:00 CST: internal EDAS registration deadline.
- 2026-07-25 to 2026-07-28: independent author read and anonymity check.
- 2026-07-29: freeze paper source, PDF, and anonymous artifact.
- 2026-07-30 18:00 CST: internal full-paper upload and EDAS-download audit.
- 2026-07-31 23:59 AOE: official full-paper deadline.
