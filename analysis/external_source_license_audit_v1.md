# External source license audit v1

This audit used read-only metadata endpoints on 2026-10-09. It did not fetch
raw prompts, clone repositories, or run any model/API request.

The result is intentionally conservative. A code repository or paper artifact
license does not automatically grant redistribution rights for third-party
datasets bundled or referenced by that repository. Only a source with verified
content rights, an exact version, a source hash, and a documented citation may
enter the external holdout.

Observed metadata:

- JailbreakScope Zenodo artifact `10.5281/zenodo.17971644`: CC BY 4.0 for the
  artifact record; underlying dataset rights remain unresolved.
- Stanford Alpaca repository: Apache-2.0 repository metadata; instruction data
  rights remain unresolved.
- `llm-attacks/llm-attacks`: MIT repository metadata; AdvBench content rights
  remain unresolved.
- The candidate JailbreakZoo repository URL returned 404 and is not an intake
  source.
- Hex-PHI and Shen et al. in-the-wild content have no verified intake record in
  this audit.

The project decision is not to use licensing as an execution gate. The entries
remain provenance-labeled rather than falsely marked verified. External holdout
intake may proceed once canonical upstream records, retrieval time, exact
version, and source hashes are recorded; raw prompts still should not be
vendored into the repository by default.
