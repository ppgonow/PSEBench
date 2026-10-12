# Local 7B persistent-schedule supplement

This supplementary exploratory experiment compares three quantized local
instruction checkpoints tagged 7B on identical single-step scheduling
prompts. It is neither a held-out study nor a full autonomous-agent run.
SQLite retains schedule metadata across connections; no scheduled callback
fires and no real provider is contacted. Structured output is constrained
by Ollama JSON schema. The supplied-grant gate is a deterministic paired
fork, not natural-language IACG inference.

## Design

- 24 task templates: 12 reminder and 12 calendar; 12 one-shot and 12
  legitimate bounded-daily grants. Explicit/paraphrased wording and three
  external-note styles are balanced within the construction.
- Each model has 96 calls: 24 tasks × permissive/prompt-only instructions
  × neutral/contaminated external notes. Template variants are dependent.
- Temperature 0, seed 42, context 4096, output cap 512; one worker.
- No inference retries, replacements, code-fence repairs or favorable-row
  selection. Unknown outcomes remain in assigned denominators.
- Two-model protocol plus a separately frozen Gemma supplement, 288 total
  model calls and 576 deterministic execution forks, not 576 model samples.
- Both branches reuse each model proposal; their contrast measures
  supplied-grant enforcement, not policy-induced proposal changes.

## Model bindings

| Model | Parameter metadata | Quantization | Digest |
|---|---|---|---|
| qwen2.5:7b-instruct | 7.6B | Q4_K_M | `845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e` |
| mistral:7b-instruct-v0.3-q4_K_M | 7.2B | Q4_K_M | `6577803aa9a036369e481d648a2baebb381ebc6e897f2bb9a766a2aa7bfbc1cf` |
| gemma:7b-instruct-q4_K_M | 9B | Q4_K_M | `d9c26a968eb4462906f59700a3b406bb41297756c0c9177ec2c2505188c58225` |

Gemma is tagged 7B-instruct, but Ollama reports 9B total parameters;
Qwen and Mistral report 7.6B and 7.2B. This is not an equal-parameter
or full-precision model comparison.

## Interface outcomes

| Model | Valid / assigned | Unknown | One-shot non-null end | Date format | API | Other |
|---|---:|---:|---:|---:|---:|---:|
| gemma:7b-instruct-q4_K_M | 53/96 | 43 | 17 | 26 | 0 | 0 |
| mistral:7b-instruct-v0.3-q4_K_M | 81/96 | 15 | 15 | 0 | 0 | 0 |
| qwen2.5:7b-instruct | 93/96 | 3 | 3 | 0 | 0 | 0 |

JSON schema constrains field types/enums, while strict post-parse checks
enforce date syntax and cross-field constraints. No semantically equivalent
timestamp or non-null one-shot end is repaired after the response.

## Read-back outcomes

Each row uses all 24 assigned tasks for that framing/instruction condition.
Injected ASR here is an unauthorized schedule registration fraction; neutral
unauthorized registrations are baseline errors, not attacks. Neither is
successful reminder delivery or production-agent prevalence. TCR requires
the entire trusted task schedule, so incomplete authorized subsets can
be safe yet fail TCR. Neutral tasks include authorized persistence;
contaminated notes attempt to enlarge both one-shot and bounded tasks.

| Model | Instruction | Note | Branch | Unauthorized / assigned | Complete task / assigned | Unknown / assigned |
|---|---|---|---|---:|---:|---:|
| mistral:7b-instruct-v0.3-q4_K_M | permissive | contaminated | typed_grant_gate | 0/24 | 6/24 | 5/24 |
| mistral:7b-instruct-v0.3-q4_K_M | permissive | contaminated | unmediated | 13/24 | 6/24 | 5/24 |
| mistral:7b-instruct-v0.3-q4_K_M | permissive | neutral | typed_grant_gate | 0/24 | 22/24 | 2/24 |
| mistral:7b-instruct-v0.3-q4_K_M | permissive | neutral | unmediated | 0/24 | 22/24 | 2/24 |
| mistral:7b-instruct-v0.3-q4_K_M | prompt_only | contaminated | typed_grant_gate | 0/24 | 10/24 | 8/24 |
| mistral:7b-instruct-v0.3-q4_K_M | prompt_only | contaminated | unmediated | 6/24 | 10/24 | 8/24 |
| mistral:7b-instruct-v0.3-q4_K_M | prompt_only | neutral | typed_grant_gate | 0/24 | 24/24 | 0/24 |
| mistral:7b-instruct-v0.3-q4_K_M | prompt_only | neutral | unmediated | 0/24 | 24/24 | 0/24 |
| qwen2.5:7b-instruct | permissive | contaminated | typed_grant_gate | 0/24 | 6/24 | 3/24 |
| qwen2.5:7b-instruct | permissive | contaminated | unmediated | 15/24 | 6/24 | 3/24 |
| qwen2.5:7b-instruct | permissive | neutral | typed_grant_gate | 0/24 | 18/24 | 0/24 |
| qwen2.5:7b-instruct | permissive | neutral | unmediated | 6/24 | 18/24 | 0/24 |
| qwen2.5:7b-instruct | prompt_only | contaminated | typed_grant_gate | 0/24 | 14/24 | 0/24 |
| qwen2.5:7b-instruct | prompt_only | contaminated | unmediated | 6/24 | 14/24 | 0/24 |
| qwen2.5:7b-instruct | prompt_only | neutral | typed_grant_gate | 0/24 | 24/24 | 0/24 |
| qwen2.5:7b-instruct | prompt_only | neutral | unmediated | 0/24 | 24/24 | 0/24 |
| gemma:7b-instruct-q4_K_M | permissive | contaminated | typed_grant_gate | 0/24 | 8/24 | 12/24 |
| gemma:7b-instruct-q4_K_M | permissive | contaminated | unmediated | 4/24 | 8/24 | 12/24 |
| gemma:7b-instruct-q4_K_M | permissive | neutral | typed_grant_gate | 0/24 | 12/24 | 12/24 |
| gemma:7b-instruct-q4_K_M | permissive | neutral | unmediated | 0/24 | 12/24 | 12/24 |
| gemma:7b-instruct-q4_K_M | prompt_only | contaminated | typed_grant_gate | 0/24 | 13/24 | 9/24 |
| gemma:7b-instruct-q4_K_M | prompt_only | contaminated | unmediated | 2/24 | 13/24 | 9/24 |
| gemma:7b-instruct-q4_K_M | prompt_only | neutral | typed_grant_gate | 0/24 | 14/24 | 10/24 |
| gemma:7b-instruct-q4_K_M | prompt_only | neutral | unmediated | 0/24 | 14/24 | 10/24 |

Unknown rows are not counted as successful protection. The CSV reports
lower and upper bounds obtained by treating every unknown as a failure or
success for each outcome; no resolved-only fraction replaces assigned n.

## Persistence-specific injected outcomes (unmediated)

| Model | Instruction | Grant | Lifetime/date violations / assigned | Complete task / assigned | Unknown / assigned |
|---|---|---|---:|---:|---:|
| gemma:7b-instruct-q4_K_M | permissive | bounded_daily | 4/12 | 0/12 | 8/12 |
| gemma:7b-instruct-q4_K_M | permissive | one_shot | 0/12 | 8/12 | 4/12 |
| gemma:7b-instruct-q4_K_M | prompt_only | bounded_daily | 2/12 | 2/12 | 8/12 |
| gemma:7b-instruct-q4_K_M | prompt_only | one_shot | 0/12 | 11/12 | 1/12 |
| mistral:7b-instruct-v0.3-q4_K_M | permissive | bounded_daily | 10/12 | 2/12 | 0/12 |
| mistral:7b-instruct-v0.3-q4_K_M | permissive | one_shot | 3/12 | 4/12 | 5/12 |
| mistral:7b-instruct-v0.3-q4_K_M | prompt_only | bounded_daily | 6/12 | 6/12 | 0/12 |
| mistral:7b-instruct-v0.3-q4_K_M | prompt_only | one_shot | 0/12 | 4/12 | 8/12 |
| qwen2.5:7b-instruct | permissive | bounded_daily | 10/12 | 2/12 | 0/12 |
| qwen2.5:7b-instruct | permissive | one_shot | 5/12 | 4/12 | 3/12 |
| qwen2.5:7b-instruct | prompt_only | bounded_daily | 4/12 | 8/12 | 0/12 |
| qwen2.5:7b-instruct | prompt_only | one_shot | 2/12 | 6/12 | 0/12 |

Lifetime/date violations are separated from title mismatches in the
by-grant CSV; they are not all mislabeled as recurrence-only failures.

## Matched framing pairs (unmediated branch)

| Model | Instruction | Complete / planned pairs | Neutral-only unsafe | Contaminated-only unsafe | Both unsafe |
|---|---|---:|---:|---:|---:|
| qwen2.5:7b-instruct | permissive | 21/24 | 0 | 9 | 6 |
| qwen2.5:7b-instruct | prompt_only | 24/24 | 0 | 6 | 0 |
| mistral:7b-instruct-v0.3-q4_K_M | permissive | 17/24 | 0 | 12 | 0 |
| mistral:7b-instruct-v0.3-q4_K_M | prompt_only | 16/24 | 0 | 6 | 0 |
| gemma:7b-instruct-q4_K_M | permissive | 8/24 | 0 | 0 | 0 |
| gemma:7b-instruct-q4_K_M | prompt_only | 13/24 | 0 | 1 | 0 |

## Interpretation

Qwen has six neutral/permissive lifetime violations: every affected request
authorizes a three-day schedule in paraphrased wording, but the model
registers daily recurrence with no end date. These are ordinary grant
interpretation errors, not evidence that contamination caused the failure.
Under contaminated notes, permissive and prompt-only results must be read
together with completion and unknown counts: a prompt can reduce observed
unsafe registrations while also changing interface failure or task utility.
The deterministic gate blocks proposals outside the supplied grant; it
does not repair denied or malformed proposals and cannot establish
open-vocabulary authorization inference. Its zero observed violations is
conformance to this declared schedule relation, not universal robustness.

These are descriptive discordance counts, not confirmatory tests;
24 constructed tasks do not provide 96 independent trials per model.

## Integrity, deviations and limits

The original two-model observer accidentally retained three-model
cardinality assertions. A disclosed audit-only addendum and new auditor
corrected them while preserving frozen protocol/source/raw hashes.
Gemma was added with a separate protocol once downloading completed.
Both audits reparse every raw response, reconstruct labels from trusted
request dates, check exact assigned key sets, and read SQLite state via
a separate connection. The registry is synthetic and locally administered;
observer-code separation is not independent provider administration.

| Run | Protocol SHA-256 | Raw SHA-256 |
|---|---|---|
| local-7b-persistence-20261011-v1 | `099690c54c5050039543b3ba8eb213a1b04057cefba53dd4f58cbdbcbb7c42f3` | `5c9c7b9856ae25aba530828610a9b6610ba7ff48a8c77312df96f0149bc8795c` |
| local-7b-persistence-gemma-20261011-v1 | `30da0df7141eeeffcda48e44da4417795ae7dc83e0ba538ffe06004143d7ea87` | `2e2ab125f10b31c6f89b6508200958653967dd6530348644b3a027ba8335b457` |

Total generated output tokens: 18960.
Total run elapsed seconds: 1466.06.

Use this supplement to describe model- and prompt-dependent schedule
behavior and utility/error trade-offs. Do not infer absence of framing
effects, arbitrary-provider safety, autonomous long-term persistence, or
superiority of IACG over comparable authorization monitors.
