# CLI Runner

This runner executes **message/cron** actions via `openclaw` CLI and records outputs as JSONL.
It is a reproducible fallback when the in-session tool API is unreliable.

Examples:

```bash
cd PSEBench
source .venv/bin/activate

# IACG/default path (no injected recurring persistence)
python runner/run_hybrid_cli.py scenarios/hybrid/H-msg-cron-required-002.yaml \
  --run-id r1 --tag iacg --chat-id <CHAT_ID>

# Permissive baseline (create recurring injected cron)
python runner/run_hybrid_cli.py scenarios/hybrid/H-msg-cron-required-002.yaml \
  --run-id r1 --tag permissive --chat-id <CHAT_ID> --allow-injected
```

Outputs:
- `results/runs/<runid>-<tag>/<scenario_id>/cli_events.jsonl`
- `.../final.json`
