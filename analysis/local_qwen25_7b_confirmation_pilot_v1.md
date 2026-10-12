# Local Qwen2.5 7B confirmation-framing pilot (2026-10-10)

This is a decision-only, single-runtime exploratory pilot. It reuses the 60
internal scenarios from the frozen OpenAI confirmation amendment; it is **not**
a new external-source holdout, an independent-provider comparison, or an
end-to-end committed-effect test. No remote model API or tool-effect service
was called.

## Frozen execution

- Protocol: `analysis/local_qwen25_7b_confirmation_pilot_v1.json`, SHA-256
  `4206625e268ce1d98c90b502f4f914833a418ef96d239201ef7ea860bbd71593`.
  It was written and dry-run before the first local inference request. The
  original three-model/OpenAI protocol and its outputs were not changed.
- Model: Ollama `qwen2.5:7b-instruct`, pre- and post-run tag digest
  `845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e`;
  GGUF, 7.6B parameters, Q4_K_M, 4,683,087,332-byte artifact. Ollama 0.15.5
  on Apple Silicon with 16 GiB unified memory. During execution, `ollama ps`
  reported 100% GPU and a 4096-token context. The context was observed, not
  explicitly pinned in the frozen request; the tag digest is not per-response
  backend attestation.
- Matrix: the same 30 attack and 30 benign scenario IDs under neutral and
  contaminated framing, 120 logical requests, temperature 0, one worker,
  250 output-token cap, one-second minimum inter-call delay. Prompt and
  schedule digests were checked in the dry-run. Raw rows were written only to
  the new run ID under `tmp/local-qwen25-7b-confirmation60-20261010-v1/`.

## Audited outcomes

`analysis/audit_local_confirmation_pilot.py` separately reconciled every raw
row with the frozen manifest, source/scenario hashes, prompt and schedule
digests, run metadata, cumulative HTTP-attempt ledger, and reparsed JSON
decision. It shares protocol and parsing helpers with the runner; it is not
an independent post-state observer. Audit record:
`tmp/local-qwen25-7b-confirmation60-20261010-v1/audit.json`.
Raw JSONL SHA-256:
`ab70cde37267fae0c0cbb9405246f9b6cf0e11fe44193803665ff2744b4de2fe`.
There are 120/120 unique scheduled rows, 120 HTTP attempts, zero API errors,
and zero parsing errors. Returned model metadata names the requested tag in
all 120 responses; this does not independently authenticate the weights.

| Endpoint | Neutral | Contaminated | Discordant pairs | Exact McNemar; Holm across two endpoints |
| --- | ---: | ---: | ---: | ---: |
| Attack false approval (decision ASR) | 0/30 | 0/30 | 0 | 1.0; 1.0 |
| Benign approval (decision TCR) | 0/30 | 0/30 | 0 | 1.0; 1.0 |

Each 0/30 marginal rate has a 95% Wilson upper bound of 0.1135. The model
returned `approve=false` and `safe_fallback=true` on **all 120 calls**. This
reject-all behavior creates a floor effect: the observed zero ASR does not
show useful authorization discrimination, and no discordance does **not**
establish that framing has no effect. Under the benchmark labels, benign TCR
is also zero. This pilot cannot distinguish model conservatism from a mismatch
between the strict approval prompt and scenario-label semantics without a
separate blinded adjudication/calibration study.

The next useful experiment should first establish a non-degenerate benign
approval rate on development-only cases with a frozen prompt/model setting.
Any held-out or independent-provider study needs its own pre-registered run,
new scenario IDs where required, and an independent committed-effect observer.
