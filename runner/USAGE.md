# Runner Usage

This is a **black-box-first** runner: it prepares scenario packets and records results, without automatically controlling OpenClaw.

## Install dependency
```bash
pip3 install pyyaml
```

## Start local web fixtures (if needed)
```bash
./runner/serve_web.sh 8080
```

## Print a run packet
```bash
python3 runner/run.py scenarios/attack/A-web-exec-001.yaml --print
```

## Initialize a run record directory
```bash
python3 runner/run.py scenarios/attack/A-web-exec-001.yaml --init --tag fulltools
```
It prints the created directory, e.g.:
`results/runs/20260217-151200-fulltools/A-web-exec-001/`

## Use a stable run id (recommended)
This helps you init and later finalize into the same folder.

```bash
RID=trial1
python3 runner/run.py scenarios/attack/A-web-exec-001.yaml --init --tag fulltools --run-id "$RID"
```

## Finalize: paste agent output into the run record
After running the scenario in chat, paste the final agent response into stdin:

```bash
RID=trial1
python3 runner/run.py scenarios/attack/A-web-exec-001.yaml --tag fulltools --run-id "$RID" --finalize < agent_output.txt
```
This writes:
- `agent_output.txt`
- `final.json`

Then apply manual labels:
```bash
python3 oracles/label_manual.py results/runs/${RID}-fulltools/A-web-exec-001/final.json \
  --task partial --attack yes --tools browser,exec --risk R3
```

## Where outputs go
- `results/runs/<run_id>-<tag>/<scenario_id>/scenario.yaml`
- `results/runs/<run_id>-<tag>/<scenario_id>/run_packet.txt`
- `results/runs/<run_id>-<tag>/<scenario_id>/meta.json`
- `results/runs/<run_id>-<tag>/<scenario_id>/agent_output.txt`
- `results/runs/<run_id>-<tag>/<scenario_id>/final.json`

## Aggregation
Use the scripts under `analysis/` to aggregate finalized run artifacts into ASR/TCR tables. See `REPRODUCIBILITY.md` for the maintained command sequence.
