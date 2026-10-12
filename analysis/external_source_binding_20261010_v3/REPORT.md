# External source-binding corrective amendment v3

Three pinned snapshots and all 108 record hashes were verified against cached source bytes. No raw prompts are included. The original v2 file is unchanged.

## Corrected scope

These 36 AdvBench harmful-goal records and 36 Alpaca candidate control-language records are development seeds, consistent with the source registry. They are not a completed external holdout or 36 implemented jailbreak attacks. Six family names in v2 were only planned transformations; zero attack methods have been executed.

Donor association is not a clean/attack pair until both scenarios share a verified trusted request and grant. Alpaca safety screening and tool-attack conversion remain pending.

## Real in-the-wild source pool

The pinned verazuo/jailbreak_llms snapshot matches the Shen et al. paper cited by JBShield. 36 real upstream jailbreak records were selected from 1,405 rows by sorted normalized prompt-group hash, one record per exact normalized group, without using model outcomes. They are source candidates, not converted tool attacks or completed live scenarios. Only one actual upstream attack family is represented. Their text-group hashes do not overlap the 72 development donors; this does not prove semantic, historical, or model-training disjointness. Community cluster hashes are retained.

Selection was the legacy first 36 records per source, not a random/representative sample. Historical split disjointness and model training exposure have not been established.

## Independent rerun

Run `python3 -B analysis/prepare_external_source_binding_v3.py --cache-dir <outside-repository-cache> --audit-dir <this-directory>`. Use the two pinned download URLs in manifest.json, not a moving main branch. The CLI has no network or model-API code.

Initial download timestamps were not captured at intake; they remain unknown. The integrity record stores the timestamp of this verification, not a fabricated retrieval time.
