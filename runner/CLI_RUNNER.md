# CLI runner (hybrid)

This runner executes **message/cron** actions via `openclaw` CLI and records outputs as JSONL.
It is a reproducible fallback when the in-session tool API is unreliable.

Examples:

```bash
cd ~/Desktop/PSEBench
source .venv/bin/activate

# Safe (no recurring persistence)
python runner/run_hybrid_cli.py scenarios/hybrid/H-msg-cron-required-002.yaml \
  --run-id r1 --tag safe --chat-id <CHAT_ID>

# Permissive baseline (create recurring injected cron)
python runner/run_hybrid_cli.py scenarios/hybrid/H-msg-cron-required-002.yaml \
  --run-id r1 --tag permissive --chat-id <CHAT_ID> --permissive
```

Outputs:
- `results/runs/<runid>-<tag>/<scenario_id>/cli_events.jsonl`
- `.../final.json`
