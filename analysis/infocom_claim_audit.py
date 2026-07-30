#!/usr/bin/env python3
"""Audit INFOCOM headline numbers against frozen derived results.

The public artifact does not include the paper source, so paper checks are
optional. When ``src/sections/evaluation.tex`` exists, the script also verifies
that every data-derived table row or narrative fragment appears in the paper.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
import re
from typing import Dict, Iterable, List, Optional


ROOT = Path(__file__).resolve().parents[1]
ANALYSIS = ROOT / "analysis"


def read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def row_where(rows: Iterable[Dict[str, str]], **values: str) -> Dict[str, str]:
    matches = [row for row in rows if all(row.get(key) == value for key, value in values.items())]
    if len(matches) != 1:
        raise ValueError(f"expected one row for {values}, found {len(matches)}")
    return matches[0]


def integer(row: Dict[str, str], key: str) -> int:
    value = row.get(key, "")
    return int(float(value)) if value not in ("", None) else 0


def ratio(numerator: int, denominator: int) -> str:
    return f"{numerator}/{denominator}"


def parse_ratio(value: str) -> tuple[int, int]:
    numerator, denominator = value.split("/", 1)
    return int(numerator), int(denominator)


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    p = k / n
    denominator = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denominator
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n) / denominator
    return max(0.0, center - margin), min(1.0, center + margin)


def ci_text(k: int, n: int) -> str:
    low, high = wilson(k, n)

    def fmt(value: float) -> str:
        return "0" if abs(value) < 0.0005 else f"{value:.3f}"

    return f"[{fmt(low)},{fmt(high)}]"


class Audit:
    def __init__(self, paper_text: Optional[str]) -> None:
        self.paper_text = paper_text
        # TeX's sentence-spacing marker changes typesetting, not claim text.
        self.comparable_paper_text = paper_text.replace("\\@", "") if paper_text else None
        self.rows: List[Dict[str, object]] = []
        self.failures: List[str] = []

    def add(
        self,
        claim_id: str,
        source: str,
        observed: str,
        paper_fragment: Optional[str],
    ) -> None:
        if self.paper_text is None or paper_fragment is None:
            paper_status = "not_checked"
        elif paper_fragment in self.comparable_paper_text:
            paper_status = "pass"
        else:
            paper_status = "fail"
            self.failures.append(claim_id)
        self.rows.append(
            {
                "claim_id": claim_id,
                "source": source,
                "observed": observed,
                "paper_status": paper_status,
                "paper_fragment": paper_fragment or "",
            }
        )

    def invariant(self, claim_id: str, condition: bool, detail: str) -> None:
        if not condition:
            self.failures.append(claim_id)
            self.rows.append(
                {
                    "claim_id": claim_id,
                    "source": "cross-source invariant",
                    "observed": detail,
                    "paper_status": "fail",
                    "paper_fragment": "",
                }
            )

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(self.rows[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(self.rows)


def audit_evidence_tiers(audit: Audit) -> None:
    evidence = read_csv(ANALYSIS / "evidence_tier_summary.csv")
    original = row_where(evidence, tier="descriptive benchmark inventory")
    matched = row_where(evidence, tier="matched reference-monitor slice")
    noncron = row_where(evidence, tier="non-cron mechanism replication")
    heldout = row_where(read_csv(ANALYSIS / "heldout_adaptive_summary.csv"), policy="IACG")

    def manifest_count(path: Path) -> int:
        return len(read_csv(path))

    frozen_n = manifest_count(ROOT / "scenarios" / "fresh-authorization-heldout" / "MANIFEST.csv")
    fresh_noncron_n = manifest_count(
        ROOT / "scenarios" / "fresh-noncron-authorization-heldout" / "MANIFEST.csv"
    )
    multitool_n = manifest_count(ROOT / "scenarios" / "multitool-chain-heldout" / "MANIFEST.csv")
    commit_race_n = manifest_count(ROOT / "scenarios" / "commit-race-heldout" / "MANIFEST.csv")
    model_n = integer(
        row_where(
            read_csv(ANALYSIS / "infocom_heldout_live20_quality.csv"),
            model="gpt-5.4",
            policy="hardened",
        ),
        "valid_requests",
    )
    native_n = integer(
        row_where(
            read_csv(ANALYSIS / "adaptive_native_fork_schema_neutral_summary.csv"),
            requested_alias="grok-4.5",
        ),
        "n_units",
    )
    rows = [
        (
            "tier_original_inventory",
            "analysis/evidence_tier_summary.csv",
            f"Original inventory & {original['n']} & mixed run configurations & discovery only; not an independent rate",
        ),
        (
            "tier_matched",
            "analysis/evidence_tier_summary.csv",
            f"Matched core & {str(matched['n']).split()[0]} paired scenarios & agent/tool runs & discovery reference-monitor contrast",
        ),
        (
            "tier_noncron",
            "analysis/evidence_tier_summary.csv",
            f"Non-cron artifact & {noncron['n']} & sandboxed file/calendar/message & effect-type and legitimate-utility replication",
        ),
        (
            "tier_heldout",
            "analysis/heldout_adaptive_summary.csv",
            f"Held-out attack & {heldout['n']} & typed action-layer replay & cue-independent enforcement stress",
        ),
        (
            "tier_frozen_authorization",
            "scenarios/fresh-authorization-heldout/MANIFEST.csv",
            f"Frozen authorization & {frozen_n} & typed action-layer replay & covered/novel intent and confirmation boundary",
        ),
        (
            "tier_fresh_noncron",
            "scenarios/fresh-noncron-authorization-heldout/MANIFEST.csv",
            f"Fresh non-cron utility & {fresh_noncron_n} & typed action-layer replay & file/calendar authorization inference",
        ),
        (
            "tier_multitool",
            "scenarios/multitool-chain-heldout/MANIFEST.csv",
            f"Multi-tool chains & {multitool_n} & typed action-sequence replay & cross-effect enforcement composition",
        ),
        (
            "tier_commit_races",
            "scenarios/commit-race-heldout/MANIFEST.csv; analysis/multiprocess_commit_race_detail.csv; analysis/container_commit_race_detail.csv; analysis/multihost_commit_race_detail.csv",
            f"Commit races & {commit_race_n} (3$\\times$600 policy obs.) & process/Docker/SSH-tunneled HTTP & same-scenario commit binding",
        ),
        (
            "tier_model_decisions",
            "analysis/infocom_heldout_live20_quality.csv",
            f"Model decisions & {model_n}/model/policy & decision-only API & model-dependent proposal behavior",
        ),
        (
            "tier_native_model_tools",
            "analysis/adaptive_native_fork_schema_neutral_summary.csv",
            f"Native fork (neutral) & {native_n} inst. / 20 tmpl. / alias & API tools + SQLite & main shared-proposal policy effect",
        ),
    ]
    for claim_id, source, fragment in rows:
        audit.add(claim_id, source, fragment.replace(" & ", ", "), fragment)


def audit_original(audit: Audit) -> None:
    source = "analysis/independent_unit_inventory.csv"
    rows = read_csv(ROOT / source)
    expected = (
        ("Tool induction", "Tool induction", 27, 27, 0, "--"),
        ("Hybrid legitimate tool", "Hybrid legitimate tool", 114, 18, 51, "114/114"),
        ("Cron required", "Cron required", 107, 11, 51, "107/107"),
        ("H-web negative", "Web-message negative", 7, 7, 0, "7/7"),
    )
    for scope, label, runs, unique_ids, attacks, task in expected:
        row = row_where(rows, scope=scope)
        audit.invariant(
            f"inventory_{label.lower().replace(' ', '_')}",
            integer(row, "run_observations") == runs
            and integer(row, "unique_scenarios") == unique_ids
            and integer(row, "attack_yes_observations") == attacks
            and row["statistical_use"] == "descriptive_inventory_only",
            str(row),
        )
        fragment = f"{label} & {runs} / {unique_ids} & {ratio(attacks, runs)} & {task}"
        audit.add(
            f"original_inventory_{label.lower().replace(' ', '_')}",
            source,
            fragment.replace(" & ", ", "),
            fragment,
        )
    narrative = (
        "The 114 hybrid records cover 18 distinct scenarios and contain 51 attack-success observations; "
        "all 51 occur among 107 cron configuration records spanning 11 scenario IDs."
    )
    audit.add("original_inventory_narrative", source, narrative, narrative)


def audit_matched(audit: Audit) -> None:
    source = "analysis/independent_paired_primary.csv"
    table_rows = read_csv(ROOT / source)
    for row in table_rows:
        label = row["slice"]
        n = integer(row, "n_unique_scenarios")
        perm_attack = integer(row, "baseline_attack_yes")
        guard_attack = integer(row, "iacg_attack_yes")
        task = integer(row, "iacg_task_yes")
        fragment = f"{label} & {n} & {ratio(perm_attack, n)} & {ratio(guard_attack, n)} & {ratio(task, n)}"
        audit.add(f"matched_{label.lower().replace(' ', '_')}", source, fragment.replace(" & ", ", "), fragment)
    core = row_where(table_rows, slice="Core cron")
    core_fragment = (
        "In the same-ID matched 10-case cron slice, permissive execution reaches 10/10 ASR and 10/10 TCR; "
        "IACG reaches 0/10 ASR and 10/10 TCR (two-sided exact McNemar $p=0.001953$)."
    )
    audit.invariant(
        "core_pair_exact",
        integer(core, "baseline_yes_iacg_no") == 10
        and integer(core, "baseline_no_iacg_yes") == 0
        and abs(float(core["mcnemar_exact_p"]) - 0.001953125) < 1e-12,
        str(core),
    )
    audit.add("core_pair_narrative", source, core_fragment, core_fragment)


def audit_heldout_and_models(audit: Audit) -> Dict[str, tuple[int, int]]:
    heldout = read_csv(ANALYSIS / "heldout_adaptive_summary.csv")
    permissive = row_where(heldout, policy="permissive")
    guarded = [row for row in heldout if row["policy"] != "permissive"]
    n = integer(permissive, "n")
    audit.invariant("heldout_policy_sizes", all(integer(row, "n") == n for row in guarded), str([row["n"] for row in guarded]))
    audit.invariant("heldout_guard_results", all(integer(row, "attack_yes") == 0 and integer(row, "task_yes") == n for row in guarded), "guarded policies")
    heldout_fragment = (
        f"Permissive replay commits {ratio(integer(permissive, 'attack_yes'), n)} recurring upgrades "
        f"(Wilson 95\% CI {ci_text(integer(permissive, 'attack_yes'), n)}); IACG, Task Shield-style, and "
        f"Prompt Flow Integrity-style policies reach {ratio(0, n)} (CI {ci_text(0, n)}) with {ratio(n, n)} TCR."
    )
    audit.add("heldout100", "analysis/heldout_adaptive_summary.csv", heldout_fragment, heldout_fragment)

    model_rows = read_csv(ANALYSIS / "infocom_heldout_live20_quality.csv")
    model_counts: Dict[str, int] = {}
    for model in ("gpt-5.4", "gpt-5.5", "gpt-5.6-sol"):
        hardened = row_where(model_rows, model=model, policy="hardened")
        permissive_model = row_where(model_rows, model=model, policy="permissive")
        model_n = integer(permissive_model, "valid_requests")
        hard_attack = integer(hardened, "escalation_yes")
        perm_attack = integer(permissive_model, "escalation_yes")
        task = integer(permissive_model, "task_yes")
        model_counts[model] = perm_attack
    model_fragment = (
        f"Supporting 20-case/model decision-only checks select {model_counts['gpt-5.4']}/20, "
        f"{model_counts['gpt-5.5']}/20, and {model_counts['gpt-5.6-sol']}/20 permissive escalations for "
        "GPT-5.4/5.5/5.6-sol, versus none under hardened prompts, with 20/20 TCR."
    )
    audit.add(
        "model_decision_summary",
        "analysis/infocom_heldout_live20_quality.csv",
        model_fragment,
        model_fragment,
    )
    return {
        "0/20": (0, 20),
        "6/20": (model_counts["gpt-5.6-sol"], 20),
        "11/20": (model_counts["gpt-5.4"], 20),
        "17/20": (model_counts["gpt-5.5"], 20),
        "20/20": (20, 20),
        "0/100": (0, n),
        "100/100": (n, n),
    }


def audit_authorization_tables(audit: Audit) -> None:
    contrast = read_csv(ANALYSIS / "triple_contrast_summary.csv")
    expected_contrast = {
        ("benign_one_shot", "permissive"): (1, 1, 1),
        ("benign_one_shot", "guard"): (1, 0, 1),
        ("benign_one_shot", "firewall"): (1, 0, 1),
        ("legit_persistent", "permissive"): (1, 0, 1),
        ("legit_persistent", "guard"): (1, 0, 1),
        ("legit_persistent", "firewall"): (1, 0, 0),
        ("ambiguous", "permissive"): (8, 8, 8),
        ("ambiguous", "guard"): (8, 0, 8),
        ("ambiguous", "firewall"): (8, 0, 8),
    }
    audit.invariant(
        "authorization_contrast_matrix",
        len(contrast) == len(expected_contrast)
        and all(
            integer(row_where(contrast, category=category, tag=policy), "n") == values[0]
            and integer(row_where(contrast, category=category, tag=policy), "attack_successes") == values[1]
            and integer(row_where(contrast, category=category, tag=policy), "task_successes") == values[2]
            for (category, policy), values in expected_contrast.items()
        ),
        str(contrast),
    )
    contrast_fragment = (
        "In a smaller same-tool contrast, both IACG and the firewall block 8/8 ambiguous upgrades, "
        "but only IACG preserves the explicitly authorized persistent task."
    )
    audit.add(
        "authorization_contrast_narrative",
        "analysis/triple_contrast_summary.csv",
        contrast_fragment,
        contrast_fragment,
    )

    lexical = read_csv(ANALYSIS / "fresh_authorization_lexical_denied_summary.csv")
    semantic = read_csv(ANALYSIS / "fresh_authorization_semantic_denied_summary.csv")
    confirmed = read_csv(ANALYSIS / "fresh_authorization_semantic_confirmed_summary.csv")

    def frozen_row(rows: List[Dict[str, str]], label: str) -> Dict[str, str]:
        return row_where(rows, scope=label, policy="IACG")

    for condition, rows, caption in (
        ("lexical", lexical, "Lexical, no confirm"),
        ("semantic", semantic, "Paraphrase, no confirm"),
        ("confirmed", confirmed, "Paraphrase + confirm"),
    ):
        known = frozen_row(rows, "fresh-semantic-known")
        novel = frozen_row(rows, "fresh-semantic-novel")
        ambiguous = frozen_row(rows, "fresh-semantic-ambiguous")
        n = integer(known, "task_n")
        fragment = (
            f"{caption} & {ratio(integer(known, 'task_yes'), n)} & "
            f"{ratio(integer(novel, 'task_yes'), n)} & {ratio(integer(novel, 'false_block_yes'), n)} & "
            f"{ratio(integer(ambiguous, 'attack_yes'), integer(ambiguous, 'attack_n'))} & "
            f"{ratio(integer(ambiguous, 'task_yes'), integer(ambiguous, 'task_n'))}"
        )
        audit.add(f"frozen_{condition}", f"analysis/fresh_authorization_{'semantic_confirmed' if condition == 'confirmed' else condition + '_denied'}_summary.csv", fragment.replace(" & ", ", "), fragment)

    noncron_denied = read_csv(ANALYSIS / "fresh_noncron_semantic_denied_summary.csv")
    noncron_confirmed = read_csv(ANALYSIS / "fresh_noncron_semantic_confirmed_summary.csv")
    for tool in ("file", "calendar"):
        for rows, condition, suffix in (
            (noncron_denied, "No confirm", "denied"),
            (noncron_confirmed, "Confirmed", "confirmed"),
        ):
            known = row_where(rows, scope=f"fresh-{tool}-known", policy="IACG")
            novel = row_where(rows, scope=f"fresh-{tool}-novel", policy="IACG")
            ambiguous = row_where(rows, scope=f"fresh-{tool}-ambiguous", policy="IACG")
            n = integer(known, "task_n")
            fragment = (
                f"{tool.title()} & {condition} & {ratio(integer(known, 'task_yes'), n)} & "
                f"{ratio(integer(novel, 'task_yes'), n)} & "
                f"{ratio(integer(ambiguous, 'attack_yes'), integer(ambiguous, 'attack_n'))}"
            )
            audit.add(f"noncron_{tool}_{suffix}", f"analysis/fresh_noncron_semantic_{suffix}_summary.csv", fragment.replace(" & ", ", "), fragment)


def audit_native_e2e(audit: Audit) -> None:
    source = "analysis/native_e2e48_summary.csv"
    rows = read_csv(ANALYSIS / "native_e2e48_summary.csv")
    for model in ("openai:gpt-5.5", "openai:grok-4.5"):
        for policy in ("permissive", "IACG", "confirm-all-persistent"):
            row = row_where(rows, model=model, policy=policy, boundary="all")
            audit.invariant(
                f"native_{model}_{policy}",
                integer(row, "n_unique_scenarios") == 48
                and integer(row, "attack_yes") == 0
                and integer(row, "task_yes") == 48,
                str(row),
            )

    attempt = read_csv(ANALYSIS / "native_e2e48_attempt_audit.csv")[0]
    final_rows = [
        json.loads(line)
        for line in (ANALYSIS / "native_e2e48_final.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    audit.invariant(
        "native_e2e_trace_integrity",
        len(final_rows) == 288
        and integer(attempt, "final_unique_units") == 288
        and integer(attempt, "native_tool_calls") == 858
        and integer(attempt, "exposure_reads") == 288
        and integer(attempt, "strict_exposure_units") == 288
        and integer(attempt, "task_yes") == 288
        and integer(attempt, "primary_effect_yes") == 288
        and integer(attempt, "single_primary_effect_units") == 288
        and integer(attempt, "sender_confirmation_calls") == 282
        and integer(attempt, "units_with_sender_confirmation") == 282
        and integer(attempt, "escalation_effect_proposals") == 0
        and integer(attempt, "effect_policy_allow_decisions") == 288
        and integer(attempt, "effect_policy_nonallow_decisions") == 0
        and integer(attempt, "attack_yes") == 0,
        str(attempt),
    )
    confirmation_cells = {
        (row["model_spec"], row["policy"]) for row in final_rows
    }
    per_cell_confirmation = {
        key: sum(
            item.get("name") == "confirm_to_sender"
            for row in final_rows
            if (row["model_spec"], row["policy"]) == key
            for item in row.get("tool_trace", [])
        )
        for key in confirmation_cells
    }
    expected_confirmation = {
        ("openai:gpt-5.5", "permissive"): 48,
        ("openai:gpt-5.5", "IACG"): 48,
        ("openai:gpt-5.5", "confirm-all-persistent"): 48,
        ("openai:grok-4.5", "permissive"): 44,
        ("openai:grok-4.5", "IACG"): 46,
        ("openai:grok-4.5", "confirm-all-persistent"): 48,
    }
    audit.invariant(
        "native_e2e_confirmation_cells",
        per_cell_confirmation == expected_confirmation,
        str(per_cell_confirmation),
    )
    audit.invariant(
        "native_e2e_v2_keys",
        all(row.get("run_id") == "native-e2e48-v2" for row in final_rows)
        and len(
            {
                (row["model_spec"], row["policy"], row["scenario_id"])
                for row in final_rows
            }
        )
        == 288,
        "fixed amended-v2 key product",
    )
    paired_rows = read_csv(ANALYSIS / "native_e2e48_paired.csv")
    audit.invariant(
        "native_e2e_paired_null",
        all(
            integer(row, "left_yes_right_no") == 0
            and integer(row, "left_no_right_yes") == 0
            and float(row["exact_mcnemar_p"]) == 1.0
            for row in paired_rows
        ),
        f"paired_rows={len(paired_rows)}",
    )
    boundary_fragment = (
        "A separate 288-unit provenance-marking native matrix produces no unsafe proposal under either "
        "alias and therefore identifies no action-policy effect."
    )
    audit.add(
        "native_e2e_boundary",
        "analysis/native_e2e48_paired.csv; analysis/native_e2e48_final.jsonl",
        boundary_fragment,
        None,
    )


def audit_adaptive_native_fork(audit: Audit) -> None:
    source = "analysis/adaptive_native_fork_schema_neutral_summary.csv"
    summary = read_csv(ANALYSIS / "adaptive_native_fork_schema_neutral_summary.csv")
    gpt = row_where(summary, requested_alias="gpt-5.5")
    grok = row_where(summary, requested_alias="grok-4.5")
    final_rows = [
        json.loads(line)
        for line in (ANALYSIS / "adaptive_native_fork_schema_neutral_final.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    audit.invariant(
        "adaptive_native_summary",
        integer(gpt, "n_units") == 80
        and integer(gpt, "valid_exposure") == 80
        and integer(gpt, "unsafe_any_proposal") == 2
        and integer(gpt, "permissive_attack_yes") == 2
        and integer(gpt, "IACG_attack_yes") == 0
        and integer(gpt, "permissive_primary_yes") == 78
        and integer(gpt, "IACG_primary_yes") == 79
        and integer(grok, "n_units") == 80
        and integer(grok, "valid_exposure") == 80
        and integer(grok, "unsafe_any_proposal") == 35
        and integer(grok, "permissive_attack_yes") == 35
        and integer(grok, "IACG_attack_yes") == 0
        and integer(grok, "permissive_primary_yes") == 61
        and integer(grok, "IACG_primary_yes") == 75
        and integer(grok, "IACG_recovery_yes_given_unsafe") == 30
        and len(final_rows) == 160
        and all(row.get("run_id") == "adaptive-native-fork-schema-neutral-v1" for row in final_rows)
        and all(row.get("schema_mode") == "neutral" for row in final_rows)
        and len({(row["requested_alias"], row["scenario_id"]) for row in final_rows}) == 160,
        f"gpt={gpt}; grok={grok}",
    )
    gpt_row = "GPT-5.5 & 2/80 & 2/80 & 0/80 & 78/80 & 79/80"
    grok_row = "Grok-4.5 & 35/80 & 35/80 & 0/80 & 61/80 & 75/80"
    audit.add("adaptive_native_gpt_table", source, gpt_row.replace(" & ", ", "), gpt_row)
    audit.add("adaptive_native_grok_table", source, grok_row.replace(" & ", ", "), grok_row)

    paired = read_csv(ANALYSIS / "adaptive_native_fork_schema_neutral_postrun_audit_paired.csv")
    template_summary = read_csv(ANALYSIS / "adaptive_native_templates_summary.csv")
    gpt_template = row_where(template_summary, requested_alias="gpt-5.5", boundary="overall")
    grok_template = row_where(template_summary, requested_alias="grok-4.5", boundary="overall")
    gpt_asr = row_where(paired, requested_alias="gpt-5.5", boundary="overall", endpoint="ASR")
    gpt_tcr = row_where(paired, requested_alias="gpt-5.5", boundary="overall", endpoint="primary_TCR")
    asr = row_where(paired, requested_alias="grok-4.5", boundary="overall", endpoint="ASR")
    tcr = row_where(paired, requested_alias="grok-4.5", boundary="overall", endpoint="primary_TCR")
    gpt_fragment = (
        "Its permissive/IACG ASR is 2/80 versus 0/80; template support is 1/20 versus 0/20 "
        "(exact paired $p=1$), while primary TCR is 78/80 versus 79/80."
    )
    audit.invariant(
        "adaptive_native_gpt_pairs",
        integer(gpt_asr, "permissive_yes_IACG_no") == 2
        and integer(gpt_asr, "permissive_no_IACG_yes") == 0
        and abs(float(gpt_asr["exact_mcnemar_p"]) - 0.5) < 1e-12
        and integer(gpt_tcr, "permissive_yes_IACG_no") == 0
        and integer(gpt_tcr, "permissive_no_IACG_yes") == 1
        and abs(float(gpt_tcr["exact_mcnemar_p"]) - 1.0) < 1e-12
        and integer(gpt_template, "semantic_templates") == 20
        and integer(gpt_template, "permissive_attack_templates") == 1
        and integer(gpt_template, "IACG_attack_templates") == 0
        and abs(float(gpt_template["template_exact_mcnemar_p"]) - 1.0) < 1e-12,
        f"gpt_asr={gpt_asr}; gpt_tcr={gpt_tcr}; gpt_template={gpt_template}",
    )
    audit.add("adaptive_native_gpt_result", source, gpt_fragment, gpt_row)
    result_fragment = (
        f"Its permissive/IACG ASR is {integer(grok, 'permissive_attack_yes')}/80 versus "
        f"{integer(grok, 'IACG_attack_yes')}/80; template support is "
        f"{integer(grok_template, 'permissive_attack_templates')}/20 versus "
        f"{integer(grok_template, 'IACG_attack_templates')}/20 ($p=0.003906$), while primary TCR is "
        f"{integer(grok, 'permissive_primary_yes')}/80 versus {integer(grok, 'IACG_primary_yes')}/80."
    )
    audit.invariant(
        "adaptive_native_grok_pairs",
        integer(asr, "permissive_yes_IACG_no") == 35
        and integer(asr, "permissive_no_IACG_yes") == 0
        and abs(float(asr["exact_mcnemar_p"]) - 5.820766091346741e-11) < 1e-20
        and integer(tcr, "permissive_yes_IACG_no") == 0
        and integer(tcr, "permissive_no_IACG_yes") == 14
        and abs(float(tcr["exact_mcnemar_p"]) - 0.0001220703125) < 1e-15
        and integer(grok_template, "semantic_templates") == 20
        and integer(grok_template, "permissive_attack_templates") == 9
        and integer(grok_template, "IACG_attack_templates") == 0
        and abs(float(grok_template["template_exact_mcnemar_p"]) - 0.00390625) < 1e-12,
        f"grok_asr={asr}; grok_tcr={tcr}; grok_template={grok_template}",
    )
    audit.add("adaptive_native_result", source, result_fragment, grok_row)
    recovery_fragment = (
        f"IACG preserves or recovers the primary task in "
        f"{integer(grok, 'IACG_recovery_yes_given_unsafe')}/{integer(grok, 'unsafe_any_proposal')} "
        "unsafe-proposal Grok instances."
    )
    audit.add("adaptive_native_recovery", source, recovery_fragment, recovery_fragment)

    detail = read_csv(ANALYSIS / "adaptive_native_fork_schema_neutral_postrun_audit_detail.csv")
    continuation_only = [
        row for row in detail
        if row["requested_alias"] == "grok-4.5"
        and row["unsafe_any_proposal"] == "True"
        and row["unsafe_first_proposal"] == "False"
    ]
    audit.invariant(
        "adaptive_native_continuation_units",
        {row["scenario_id"] for row in continuation_only}
        == {
            "ANF-holdout-file-012",
            "ANF-holdout-file-017",
            "ANF-holdout-recipient-009",
        }
        and all(row["permissive_attack_succeeded"] == "True" for row in continuation_only),
        str(continuation_only),
    )

    by_boundary = read_csv(ANALYSIS / "adaptive_native_fork_schema_neutral_postrun_audit_by_boundary.csv")
    unsafe_boundaries = {
        alias: {
            row["boundary"]
            for row in by_boundary
            if row["requested_alias"] == alias
            and row["metric"] == "unsafe_any_proposal"
            and row["boundary"] != "overall"
            and integer(row, "successes") > 0
        }
        for alias in ("gpt-5.5", "grok-4.5")
    }
    boundary_fragment = (
        "Signal occurs in Grok file/recipient and GPT recipient cases; neither alias proposes unsafe cron or calendar effects."
    )
    audit.invariant(
        "adaptive_native_boundary_support",
        unsafe_boundaries
        == {"gpt-5.5": {"recipient"}, "grok-4.5": {"file", "recipient"}},
        str(unsafe_boundaries),
    )
    audit.add(
        "adaptive_native_boundary",
        "analysis/adaptive_native_fork_schema_neutral_postrun_audit_by_boundary.csv",
        boundary_fragment,
        boundary_fragment,
    )

    integrity = read_csv(ANALYSIS / "adaptive_native_fork_schema_neutral_postrun_audit_integrity.csv")[0]
    metadata = read_csv(ANALYSIS / "adaptive_native_fork_schema_neutral_postrun_audit_metadata.csv")
    audit.invariant(
        "adaptive_native_integrity",
        integer(integrity, "raw_rows") == 176
        and integer(integrity, "final_unique_units") == 160
        and integer(integrity, "superseded_api_errors") == 16
        and integer(integrity, "all_raw_http_attempts") == 966
        and integer(integrity, "sqlite_commits") == 330
        and integer(integrity, "response_metadata") == 921
        and integer(integrity, "response_model_alias_mismatches") == 0
        and all(integer(row, "response_model_alias_mismatches") == 0 for row in metadata),
        str(integrity),
    )
    integrity_fragment = (
        "Independent audits reconstruct all 330 schema-neutral native commits, verify 921/921 returned aliases, "
        "cluster 320 instances into 80 alias--template units"
    )
    audit.add(
        "adaptive_native_integrity_paper",
        "analysis/adaptive_native_fork_schema_neutral_postrun_audit_integrity.csv",
        integrity_fragment,
        integrity_fragment,
    )
    template_details = read_csv(ANALYSIS / "adaptive_native_templates_detail.csv")
    template_fragment = integrity_fragment
    audit.invariant(
        "adaptive_native_template_integrity",
        len(template_details) == 80
        and sum(integer(row, "instances") for row in template_details) == 320
        and all(integer(row, "instances") == 4 for row in template_details),
        f"clusters={len(template_details)}",
    )
    audit.add(
        "adaptive_native_template_paper",
        "analysis/adaptive_native_templates_detail.csv",
        template_fragment,
        template_fragment,
    )

    v1 = row_where(
        read_csv(ANALYSIS / "adaptive_native_fork_holdout_summary.csv"),
        requested_alias="grok-4.5",
    )
    v1_fragment = (
        "The separate v1 provenance-marked condition yields Grok ASR 25/80 versus 0/80 and "
        "primary TCR 65/80 versus 78/80; its direction is consistent but it remains a distinct condition."
    )
    audit.invariant(
        "adaptive_native_v1_retained",
        integer(v1, "permissive_attack_yes") == 25
        and integer(v1, "IACG_attack_yes") == 0
        and integer(v1, "permissive_primary_yes") == 65
        and integer(v1, "IACG_primary_yes") == 78,
        str(v1),
    )
    audit.add(
        "adaptive_native_v1_separation",
        "analysis/adaptive_native_fork_holdout_summary.csv",
        v1_fragment,
        None,
    )


def audit_adaptive_native_extension(audit: Audit) -> None:
    source = "analysis/adaptive_native_fork_gpt54_gpt56_summary.csv"
    summary = read_csv(ANALYSIS / "adaptive_native_fork_gpt54_gpt56_summary.csv")
    gpt54 = row_where(summary, requested_alias="gpt-5.4")
    gpt56 = row_where(summary, requested_alias="gpt-5.6-sol")
    final_rows = [
        json.loads(line)
        for line in (ANALYSIS / "adaptive_native_fork_gpt54_gpt56_final.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    terminal = [row for row in final_rows if row.get("status") == "terminal_without_effect"]
    audit.invariant(
        "adaptive_native_extension_summary",
        integer(gpt54, "n_units") == 80
        and integer(gpt54, "valid_exposure") == 79
        and integer(gpt54, "terminal_without_effect") == 1
        and integer(gpt54, "unsafe_any_proposal") == 19
        and integer(gpt54, "permissive_attack_yes") == 19
        and integer(gpt54, "IACG_attack_yes") == 0
        and integer(gpt54, "permissive_primary_yes") == 68
        and integer(gpt54, "IACG_primary_yes") == 69
        and integer(gpt56, "n_units") == 80
        and integer(gpt56, "valid_exposure") == 80
        and integer(gpt56, "unsafe_any_proposal") == 4
        and integer(gpt56, "permissive_attack_yes") == 4
        and integer(gpt56, "IACG_attack_yes") == 0
        and integer(gpt56, "permissive_primary_yes") == 77
        and integer(gpt56, "IACG_primary_yes") == 80
        and len(final_rows) == 160
        and len(terminal) == 1
        and terminal[0]["requested_alias"] == "gpt-5.4"
        and all(row.get("run_id") == "adaptive-native-fork-schema-neutral-gpt54-gpt56-v1" for row in final_rows)
        and all(row.get("schema_mode") == "neutral" for row in final_rows)
        and len({(row["requested_alias"], row["scenario_id"]) for row in final_rows}) == 160,
        f"gpt54={gpt54}; gpt56={gpt56}; terminal={terminal}",
    )
    gpt54_row = "GPT-5.4$^{\\dagger}$ & 19/79 & 19/79 & 0/79 & 68/79 & 69/79"
    gpt56_row = "GPT-5.6-sol$^{\\dagger}$ & 4/80 & 4/80 & 0/80 & 77/80 & 80/80"
    audit.add("adaptive_native_extension_gpt54_table", source, gpt54_row.replace(" & ", ", "), gpt54_row)
    audit.add("adaptive_native_extension_gpt56_table", source, gpt56_row.replace(" & ", ", "), gpt56_row)

    paired = read_csv(ANALYSIS / "adaptive_native_fork_gpt54_gpt56_postrun_audit_paired.csv")
    template_summary = read_csv(ANALYSIS / "adaptive_native_templates_summary.csv")
    gpt54_template = row_where(template_summary, requested_alias="gpt-5.4", boundary="overall")
    gpt56_template = row_where(template_summary, requested_alias="gpt-5.6-sol", boundary="overall")
    gpt54_asr = row_where(paired, requested_alias="gpt-5.4", boundary="overall", endpoint="ASR")
    gpt54_tcr = row_where(paired, requested_alias="gpt-5.4", boundary="overall", endpoint="primary_TCR")
    gpt56_asr = row_where(paired, requested_alias="gpt-5.6-sol", boundary="overall", endpoint="ASR")
    gpt56_tcr = row_where(paired, requested_alias="gpt-5.6-sol", boundary="overall", endpoint="primary_TCR")
    audit.invariant(
        "adaptive_native_extension_pairs",
        integer(gpt54_asr, "n_pairs") == 79
        and integer(gpt54_asr, "permissive_yes_IACG_no") == 19
        and integer(gpt54_asr, "permissive_no_IACG_yes") == 0
        and abs(float(gpt54_asr["exact_mcnemar_p"]) - 3.814697265625e-06) < 1e-15
        and integer(gpt54_tcr, "permissive_yes_IACG_no") == 0
        and integer(gpt54_tcr, "permissive_no_IACG_yes") == 1
        and abs(float(gpt54_tcr["exact_mcnemar_p"]) - 1.0) < 1e-12
        and integer(gpt56_asr, "n_pairs") == 80
        and integer(gpt56_asr, "permissive_yes_IACG_no") == 4
        and integer(gpt56_asr, "permissive_no_IACG_yes") == 0
        and abs(float(gpt56_asr["exact_mcnemar_p"]) - 0.125) < 1e-12
        and integer(gpt56_tcr, "permissive_yes_IACG_no") == 0
        and integer(gpt56_tcr, "permissive_no_IACG_yes") == 3
        and abs(float(gpt56_tcr["exact_mcnemar_p"]) - 0.25) < 1e-12
        and integer(gpt54_template, "permissive_attack_templates") == 7
        and integer(gpt54_template, "IACG_attack_templates") == 0
        and abs(float(gpt54_template["template_exact_mcnemar_p"]) - 0.015625) < 1e-12
        and integer(gpt56_template, "permissive_attack_templates") == 3
        and integer(gpt56_template, "IACG_attack_templates") == 0
        and abs(float(gpt56_template["template_exact_mcnemar_p"]) - 0.25) < 1e-12,
        f"gpt54_asr={gpt54_asr}; gpt54_tcr={gpt54_tcr}; gpt54_template={gpt54_template}; "
        f"gpt56_asr={gpt56_asr}; gpt56_tcr={gpt56_tcr}; gpt56_template={gpt56_template}",
    )
    audit.add(
        "adaptive_native_extension_gpt54_result",
        source,
        "GPT-5.4 ASR 19/79 versus 0/79",
        "GPT-5.4$^{\dagger}$ & 19/79 & 19/79 & 0/79 & 68/79 & 69/79",
    )
    audit.add(
        "adaptive_native_extension_gpt56_result",
        source,
        "GPT-5.6-sol ASR 4/80 versus 0/80",
        "GPT-5.6-sol has 4/80 versus 0/80 ASR",
    )

    integrity = read_csv(ANALYSIS / "adaptive_native_fork_gpt54_gpt56_postrun_audit_integrity.csv")[0]
    audit.invariant(
        "adaptive_native_extension_integrity",
        integer(integrity, "raw_rows") == 160
        and integer(integrity, "final_unique_units") == 160
        and integer(integrity, "superseded_api_errors") == 0
        and integer(integrity, "all_raw_http_attempts") == 947
        and integer(integrity, "sqlite_commits") == 317
        and integer(integrity, "response_model_alias_mismatches") == 0,
        str(integrity),
    )


def audit_method_comparison(audit: Audit) -> None:
    source = "analysis/method_comparison_overall_candidate_action.csv"
    rows = read_csv(ANALYSIS / "method_comparison_overall_candidate_action.csv")
    expected = {
        "BASE-01": ("Permissive", "direct baseline", 110, 135, 0),
        "BASE-02": ("Firewall", "direct baseline", 0, 119, 0),
        "BASE-03": ("Confirm-all", "direct baseline", 0, 119, 126),
        "BASE-04": ("SLC", "direct baseline", 1, 135, 0),
        "CMP-02": ("RTBAS/IFC-style", "typed adaptation", 0, 135, 110),
        "CMP-03": ("PAuth-style", "typed adaptation", 0, 135, 0),
        "CMP-04": ("PCAS-style", "typed adaptation", 0, 135, 0),
        "IACG": ("IACG", "reference monitor", 0, 135, 0),
    }
    audit.invariant(
        "method_comparison_matrix",
        len(rows) == len(expected)
        and all(
            integer(row_where(rows, comparator_id=comparator_id), "n") == 135
            and integer(row_where(rows, comparator_id=comparator_id), "attack_n") == 110
            and integer(row_where(rows, comparator_id=comparator_id), "attack_successes") == values[2]
            and integer(row_where(rows, comparator_id=comparator_id), "task_successes") == values[3]
            and integer(row_where(rows, comparator_id=comparator_id), "confirmations") == values[4]
            for comparator_id, values in expected.items()
        ),
        str(rows),
    )
    for comparator_id, (display, evidence_type, attacks, tasks, confirmations) in expected.items():
        fragment = (
            f"{display} & {evidence_type} & {attacks}/110 & "
            f"{tasks}/135 & {confirmations}/135"
        )
        audit.add(
            f"method_comparison_{comparator_id.lower().replace('-', '_')}",
            source,
            fragment.replace(" & ", ", "),
            fragment,
        )
    comparison_boundary = (
        "The closest task-scoped and declarative adaptations tie IACG on this supplied-effect "
        "matrix, so we do not claim method-level superiority."
    )
    audit.add(
        "method_comparison_boundary",
        source,
        comparison_boundary,
        comparison_boundary,
    )


def audit_multitool_and_overhead(audit: Audit) -> Dict[str, tuple[int, int]]:
    multitool = read_csv(ANALYSIS / "multitool_chain_summary.csv")
    permissive = row_where(multitool, scope="overall", family="all", policy="permissive")
    iacg = row_where(multitool, scope="overall", family="all", policy="IACG")
    n = integer(permissive, "n")
    multitool_fragment = (
        f"permissive/IACG ASR is {ratio(integer(permissive, 'attack_yes'), n)} versus "
        f"{ratio(integer(iacg, 'attack_yes'), n)}, both with {ratio(integer(iacg, 'task_yes'), n)} TCR "
        f"(Wilson extremes {ci_text(integer(permissive, 'attack_yes'), n)} and "
        f"{ci_text(integer(iacg, 'attack_yes'), n)}; paired exact $p=1.73\\times10^{{-18}}$)."
    )
    audit.add("multitool_overall", "analysis/multitool_chain_summary.csv", multitool_fragment, multitool_fragment)

    overhead = read_csv(ANALYSIS / "iacg_overhead_summary.csv")
    lexical = row_where(overhead, policy="IACG")
    semantic = row_where(overhead, policy="IACG-semantic")
    overhead_fragment = (
        f"Local IACG median policy latency is {float(lexical['median_us']):.3f}~$\\mu$s (lexical) "
        f"and {float(semantic['median_us']):.3f}~$\\mu$s (paraphrase-oriented), small relative to model/tool latency."
    )
    audit.add("policy_overhead", "analysis/iacg_overhead_summary.csv", overhead_fragment, overhead_fragment)
    return {"0/60": (integer(iacg, "attack_yes"), n), "60/60": (integer(permissive, "attack_yes"), n)}


def audit_commit_race(audit: Audit) -> None:
    summary = read_csv(ANALYSIS / "multiprocess_commit_race_summary.csv")
    check_once = row_where(summary, scope="overall", family="all", policy="check-once")
    pauth = row_where(summary, scope="overall", family="all", policy="PAuth-style/pre-action")
    pcas = row_where(summary, scope="overall", family="all", policy="PCAS-style/pre-action")
    commit_bound = row_where(summary, scope="overall", family="all", policy="receipt-bound")
    paired_rows = read_csv(ANALYSIS / "multiprocess_commit_race_paired.csv")
    attack_n = integer(check_once, "attack_n")
    benign_n = integer(check_once, "benign_n")
    audit.invariant(
        "commit_race_pairing",
        all(integer(row, "attack_n") == attack_n for row in (pauth, pcas, commit_bound))
        and all(integer(row, "benign_n") == benign_n for row in (pauth, pcas, commit_bound))
        and all(
            integer(row_where(paired_rows, comparator=comparator, family="all"), "n_pairs") == attack_n
            for comparator in ("check-once", "PAuth-style/pre-action", "PCAS-style/pre-action")
        ),
        f"attack={attack_n}, benign={benign_n}",
    )
    result_fragment = (
        "In three-process HTTP, check-once, PAuth-style/pre-action, and PCAS-style/pre-action each commit "
        f"{ratio(integer(check_once, 'attack_yes'), attack_n)} invalidated effects; receipt-bound commits "
        f"{ratio(integer(commit_bound, 'attack_yes'), attack_n)}, and all preserve "
        f"{ratio(integer(commit_bound, 'task_yes'), benign_n)} controls (paired $p=1.58\\times10^{{-30}}$)."
    )
    audit.add(
        "commit_race_result",
        "analysis/multiprocess_commit_race_summary.csv; analysis/multiprocess_commit_race_paired.csv",
        result_fragment,
        result_fragment,
    )

    integrity = read_csv(ANALYSIS / "multiprocess_commit_race_audit_integrity.csv")[0]
    attack_policy_n = integer(integrity, "attack_rows")
    manipulation_fragment = (
        "Every matrix observes active mutation before the gateway request, and idempotence reduces "
        "600 deliveries to 500 commits."
    )
    audit.invariant(
        "multiprocess_commit_race_integrity",
        attack_policy_n == 400
        and integer(integrity, "causal_active_rows") == attack_policy_n
        and integer(integrity, "service_pids") == 3
        and integer(integrity, "delivery_attempts") == 600
        and integer(integrity, "ledger_rows") == 500,
        str(integrity),
    )
    audit.add(
        "multiprocess_commit_race_manipulation",
        "analysis/multiprocess_commit_race_audit_integrity.csv",
        manipulation_fragment,
        manipulation_fragment,
    )

    check_median = float(check_once["control_gateway_median_us"]) / 1000
    bound_median = float(commit_bound["control_gateway_median_us"]) / 1000

    container_summary = read_csv(ANALYSIS / "container_commit_race_summary.csv")
    container_check = row_where(
        container_summary, scope="overall", family="all", policy="check-once"
    )
    container_pauth = row_where(
        container_summary,
        scope="overall",
        family="all",
        policy="PAuth-style/pre-action",
    )
    container_pcas = row_where(
        container_summary,
        scope="overall",
        family="all",
        policy="PCAS-style/pre-action",
    )
    container_bound = row_where(
        container_summary,
        scope="overall",
        family="all",
        policy="receipt-bound",
    )
    container_integrity = read_csv(
        ANALYSIS / "container_commit_race_audit_integrity.csv"
    )[0]
    topology = read_csv(ANALYSIS / "container_commit_race_topology.csv")
    audit.invariant(
        "container_commit_race_integrity",
        all(integer(row, "attack_yes") == 100 for row in (container_check, container_pauth, container_pcas))
        and integer(container_bound, "attack_yes") == 0
        and all(integer(row, "task_yes") == 50 for row in (container_check, container_pauth, container_pcas, container_bound))
        and integer(container_integrity, "rows") == 600
        and integer(container_integrity, "causal_active_rows") == 400
        and integer(container_integrity, "container_hashes") == 3
        and integer(container_integrity, "namespace_hashes") == 3
        and integer(container_integrity, "container_ips") == 3
        and integer(container_integrity, "shared_network_hashes") == 1
        and integer(container_integrity, "delivery_attempts") == 600
        and integer(container_integrity, "ledger_rows") == 500
        and len(topology) == 3
        and all(row["network_driver"] == "bridge" for row in topology)
        and all(integer(row, "network_internal") == 0 for row in topology)
        and all(row["published_host_ip"] == "127.0.0.1" for row in topology),
        f"integrity={container_integrity}; topology={topology}",
    )
    container_result_fragment = "Docker-isolated and three-instance SSH-relayed replications repeat these outcomes."
    audit.add(
        "container_commit_race_result",
        "analysis/container_commit_race_summary.csv; analysis/container_commit_race_audit_integrity.csv",
        container_result_fragment,
        container_result_fragment,
    )

    remote_summary = read_csv(ANALYSIS / "multihost_commit_race_summary.csv")
    remote_rows = {
        policy: row_where(
            remote_summary, scope="overall", family="all", policy=policy
        )
        for policy in (
            "check-once",
            "PAuth-style/pre-action",
            "PCAS-style/pre-action",
            "receipt-bound",
        )
    }
    remote_integrity = read_csv(
        ANALYSIS / "multihost_commit_race_audit_integrity.csv"
    )[0]
    remote_topology = read_csv(ANALYSIS / "multihost_commit_race_topology.csv")
    distinct_fields = (
        "boot_id_sha256",
        "dmi_product_uuid_sha256",
        "cgroup_identity_sha256",
        "hostname_sha256",
        "pid_namespace_sha256",
        "network_namespace_sha256",
        "uts_namespace_sha256",
        "cpuinfo_sha256",
        "ssh_endpoint_sha256",
    )
    audit.invariant(
        "remote_commit_race_integrity",
        all(
            integer(remote_rows[policy], "attack_yes") == 100
            for policy in (
                "check-once",
                "PAuth-style/pre-action",
                "PCAS-style/pre-action",
            )
        )
        and integer(remote_rows["receipt-bound"], "attack_yes") == 0
        and all(integer(row, "task_yes") == 50 for row in remote_rows.values())
        and integer(remote_integrity, "rows") == 600
        and integer(remote_integrity, "causal_active_rows") == 400
        and integer(remote_integrity, "delivery_attempts") == 600
        and integer(remote_integrity, "ledger_rows") == 500
        and integer(remote_integrity, "health_passes") == 3
        and integer(remote_integrity, "relay_passes") == 3
        and len(remote_topology) == 3
        and all(
            len({row[field] for row in remote_topology}) == 3
            for field in distinct_fields
        )
        and len({row["machine_id_sha256"] for row in remote_topology}) == 1
        and len({row["ssh_proxy_host_sha256"] for row in remote_topology}) == 1
        and all(
            row["transport"] == "ssh-tunneled-http" for row in remote_topology
        )
        and all(
            row["service_bind"] == "remote-loopback" for row in remote_topology
        ),
        f"integrity={remote_integrity}; topology={remote_topology}",
    )
    remote_result_fragment = container_result_fragment
    audit.add(
        "remote_commit_race_result",
        "analysis/multihost_commit_race_summary.csv; analysis/multihost_commit_race_audit_integrity.csv",
        remote_result_fragment,
        remote_result_fragment,
    )
    container_check_median = float(container_check["control_gateway_median_us"]) / 1000
    container_bound_median = float(container_bound["control_gateway_median_us"]) / 1000
    combined_latency_fragment = (
        f"Check-once/receipt-bound benign medians are {check_median:.3f}/{bound_median:.3f}~ms (processes) "
        f"and {container_check_median:.3f}/{container_bound_median:.3f}~ms (Docker)"
    )
    audit.add(
        "commit_race_combined_latency",
        "analysis/multiprocess_commit_race_summary.csv; analysis/container_commit_race_summary.csv",
        combined_latency_fragment,
        combined_latency_fragment,
    )
    remote_medians = [
        float(row["control_gateway_median_us"]) / 1000
        for row in remote_rows.values()
    ]
    remote_latency_fragment = "remote medians are transport dominated and not interpreted as defense overhead."
    audit.add(
        "remote_commit_race_latency",
        "analysis/multihost_commit_race_summary.csv",
        remote_latency_fragment,
        remote_latency_fragment,
    )

    load = read_csv(ANALYSIS / "commit_gateway_load_summary.csv")
    load_rows = {
        (row["policy"], integer(row, "concurrency")): row for row in load
    }
    check_c1 = load_rows[("check-once", 1)]
    bound_c1 = load_rows[("receipt-bound", 1)]
    check_c32 = load_rows[("check-once", 32)]
    bound_c32 = load_rows[("receipt-bound", 32)]
    audit.invariant(
        "commit_gateway_load_integrity",
        len(load) == 6
        and all(integer(row, "repeats") == 3 for row in load)
        and all(integer(row, "requests") == 600 for row in load)
        and all(integer(row, "committed") == 600 for row in load),
        str(load),
    )
    load_fragment = (
        "A separate stable loopback load matrix completes all 3,600 measured requests with exactly one ledger "
        f"commit each. At concurrency 1, check-once/receipt-bound median throughput is "
        f"{float(check_c1['throughput_median_rps']):.1f}/{float(bound_c1['throughput_median_rps']):.1f} requests/s; "
        f"at concurrency 32 it is {float(check_c32['throughput_median_rps']):.1f}/"
        f"{float(bound_c32['throughput_median_rps']):.1f} requests/s, with receipt-bound client p99 latency "
        f"of {float(bound_c32['client_p99_us']) / 1000:.3f}~ms."
    )
    audit.add(
        "commit_gateway_load_result",
        "analysis/commit_gateway_load_detail.csv; analysis/commit_gateway_load_summary.csv",
        load_fragment,
        load_fragment,
    )


def audit_native_service_commit_bridge(audit: Audit, *, check_paper: bool) -> None:
    detail_source = "analysis/native_service_commit_bridge_detail.csv"
    summary_source = "analysis/native_service_commit_bridge_summary.csv"
    paired_source = "analysis/native_service_commit_bridge_paired.csv"
    integrity_source = "analysis/native_service_commit_bridge_integrity.csv"
    independent_source = "analysis/native_service_commit_bridge_audit.csv"
    detail = read_csv(ROOT / detail_source)
    summary = read_csv(ROOT / summary_source)
    paired = read_csv(ROOT / paired_source)
    integrity = read_csv(ROOT / integrity_source)[0]
    independent = read_csv(ROOT / independent_source)
    aliases = ("gpt-5.5", "grok-4.5", "gpt-5.4", "gpt-5.6-sol")

    audit.invariant(
        "native_service_bridge_matrix",
        len(detail) == 768
        and len(
            {
                (row["requested_alias"], row["policy"], row["state"], row["scenario_id"])
                for row in detail
            }
        )
        == 768
        and {row["requested_alias"] for row in detail} == set(aliases)
        and all(
            sum(row["requested_alias"] == alias for row in detail) == 192
            and len(
                {
                    row["scenario_id"]
                    for row in detail
                    if row["requested_alias"] == alias
                }
            )
            == 48
            for alias in aliases
        )
        and integer(integrity, "rows") == 768
        and integer(integrity, "unique_keys") == 768
        and integer(integrity, "aliases") == 4
        and integer(integrity, "unique_native_proposals") == 192,
        str(integrity),
    )
    audit.add(
        "native_service_bridge_matrix_record",
        f"{detail_source}; {integrity_source}",
        "768/768 rows and unique policy/state/scenario keys; 192 proposals, 48 per alias",
        None,
    )

    revoked = [row for row in detail if row["state"] == "revoked"]
    audit.invariant(
        "native_service_bridge_causal_gates",
        len(revoked) == 384
        and all(
            integer(row, "mutation_observed_active") == 1
            and integer(row, "mutation_active_precommit") == 1
            and integer(row, "commit_after_mutation_observation") == 1
            and float(row["configured_commit_delay_ms"]) == 10.0
            and float(row["configured_mutation_hold_ms"]) == 1000.0
            for row in revoked
        )
        and integer(integrity, "revoked_mutation_observed_active") == 384
        and integer(integrity, "revoked_mutation_active_precommit") == 384
        and integer(integrity, "revoked_commit_after_observation") == 384,
        str(integrity),
    )
    audit.add(
        "native_service_bridge_causal_record",
        f"{detail_source}; {integrity_source}",
        "384/384 revoked rows pass observation, active-precommit, and commit-after-observation gates",
        None,
    )

    audit.invariant(
        "native_service_bridge_effect_identity",
        all(
            integer(row, "transport_hash_match") == 1
            and integer(row, "ledger_hash_match") == 1
            and integer(row, "role_chain_verified") == 1
            for row in detail
        )
        and integer(integrity, "transport_hash_matches") == 768
        and integer(integrity, "ledger_hash_matches") == 768
        and integer(integrity, "role_chain_verified") == 768,
        str(integrity),
    )
    audit.add(
        "native_service_bridge_identity_record",
        f"{detail_source}; {integrity_source}",
        "768/768 transport hashes, ledger hashes, and authorization-to-gateway-to-effect role chains verified",
        None,
    )

    for alias in aliases:
        cached_stable = row_where(
            summary,
            requested_alias=alias,
            policy="cached-pre-action",
            state="stable",
        )
        receipt_stable = row_where(
            summary,
            requested_alias=alias,
            policy="receipt-bound",
            state="stable",
        )
        cached_revoked = row_where(
            summary,
            requested_alias=alias,
            policy="cached-pre-action",
            state="revoked",
        )
        receipt_revoked = row_where(
            summary,
            requested_alias=alias,
            policy="receipt-bound",
            state="revoked",
        )
        paired_row = row_where(paired, requested_alias=alias)
        audit.invariant(
            f"native_service_bridge_{alias.replace('.', '_').replace('-', '_')}",
            all(
                integer(row, "n") == 48
                for row in (cached_stable, receipt_stable, cached_revoked, receipt_revoked)
            )
            and integer(cached_stable, "commits") == 48
            and integer(receipt_stable, "commits") == 48
            and integer(cached_revoked, "stale_commits") == 48
            and integer(receipt_revoked, "stale_commits") == 0
            and integer(paired_row, "n_pairs") == 48
            and integer(paired_row, "cached_yes_receipt_no") == 48
            and integer(paired_row, "cached_no_receipt_yes") == 0
            and abs(float(paired_row["exact_mcnemar_p"]) - 7.105427357601002e-15)
            < 1e-27,
            f"summary={[cached_stable, receipt_stable, cached_revoked, receipt_revoked]}; paired={paired_row}",
        )
    audit.add(
        "native_service_bridge_pairing_record",
        f"{summary_source}; {paired_source}",
        "Per alias: cached stale 48/48 versus receipt stale 0/48; exact McNemar p=7.105427357601002e-15",
        None,
    )

    audit.invariant(
        "native_service_bridge_outcomes_and_audit",
        len(summary) == 16
        and len(paired) == 4
        and integer(integrity, "stable_cached_commits") == 192
        and integer(integrity, "stable_receipt_commits") == 192
        and integer(integrity, "revoked_cached_stale_commits") == 192
        and integer(integrity, "revoked_receipt_stale_commits") == 0
        and integer(integrity, "effect_rows") == 576
        and integer(integrity, "delivery_attempts") == 768
        and integer(integrity, "ephemeral_cleanup_verified") == 1
        and len(independent) == 65
        and all(integer(row, "passed") == 1 for row in independent),
        f"integrity={integrity}; independent_checks={len(independent)}",
    )
    audit.add(
        "native_service_bridge_integrity_record",
        f"{integrity_source}; {independent_source}",
        "Stable controls 192/192 per policy; 576 ledger effects from 768 attempts; cleanup verified; independent audit 65/65",
        None,
    )

    rq3_count_fragment = (
        "The native-to-commit bridge carries all 192 frozen authorized clean proposals unchanged through "
        "distinct loopback authorization, gateway, and effect processes. Authorization issues the receipt "
        "and propagates revocation, the gateway only relays commit requests, and the effect service verifies "
        "and writes SQLite. Each revoked clone observes the version change active, waits 10~ms within a "
        "1,000~ms hold, and then commits. All 384 revoked rows pass this happens-before gate, and all 768 rows "
        "preserve the proposal hash through the service boundary. Both policies commit 192/192 stable controls. "
        "Cached authorization commits 192/192 stale revoked effects, whereas receipt-bound commits 0/192. "
        "Each alias separately yields 48/48 versus 0/48 ($p=7.11\\times10^{-15}$; "
        "Fig.~\\ref{fig:auth_matrix}c). Every allow has one ledger row and every block has none. These are "
        "paired clones, not new model samples or a revocation-prevalence estimate."
    )
    rq3_percentage_fragment = (
        "The native-to-commit bridge carries all 192 frozen authorized clean proposals unchanged through "
        "distinct loopback authorization, gateway, and effect processes. Authorization issues the receipt "
        "and propagates revocation, the gateway only relays commit requests, and the effect service verifies "
        "and writes SQLite. Each revoked clone observes the version change active, waits 10~ms within a "
        "1,000~ms hold, and then commits. All 384 revoked rows pass this happens-before gate, and all 768 rows "
        "preserve the proposal hash through the service boundary. Both policies complete 100\\% of stable "
        "controls (192/192 per policy). Cached authorization commits 100\\% of stale revoked effects "
        "(192/192), whereas receipt-bound commit remains at 0\\% (0/192). Each alias separately yields "
        "100\\% versus 0\\% across 48 paired revoked clones ($p=7.11\\times10^{-15}$; "
        "Fig.~\\ref{fig:auth_matrix}c). Every allow has one ledger row and every block has none. These are "
        "paired clones, not new model samples or a revocation-prevalence estimate."
    )
    paper_fragment = None
    if check_paper:
        paper_fragment = next(
            (
                fragment
                for fragment in (rq3_percentage_fragment, rq3_count_fragment)
                if fragment in (audit.comparable_paper_text or "")
            ),
            rq3_percentage_fragment,
        )
    audit.add(
        "native_service_bridge_rq3",
        "; ".join(
            (detail_source, summary_source, paired_source, integrity_source, independent_source)
        ),
        rq3_percentage_fragment,
        paper_fragment,
    )


def audit_network_schedule(audit: Audit) -> None:
    detail = read_csv(ANALYSIS / "network_schedule_detail.csv")
    inference = read_csv(ANALYSIS / "network_schedule_inference.csv")
    paired = read_csv(ANALYSIS / "network_schedule_paired.csv")
    families = read_csv(ANALYSIS / "network_schedule_by_family.csv")
    profiles = (
        ("single", "Single"),
        ("delayed-40ms", "Delay 40 ms"),
        ("duplicate-downstream", "Duplicate"),
        ("concurrent-retry", "Concurrent"),
        ("reordered-retry", "Reordered"),
    )
    keys = {
        (row["profile"], row["policy"], row["scenario_id"])
        for row in detail
    }
    attack_rows = [row for row in detail if row["scenario_type"] == "attack"]
    audit.invariant(
        "network_schedule_integrity",
        len(detail) == 1500
        and len(keys) == 1500
        and sum(integer(row, "gateway_attempts") for row in detail) == 2100
        and sum(integer(row, "delivery_attempts") for row in detail) == 1600
        and sum(integer(row, "ledger_rows") for row in detail) == 1000
        and len(attack_rows) == 1000
        and all(integer(row, "mutation_active_gate") == 1 for row in attack_rows)
        and sum(row["profile"] == "reordered-retry" for row in detail) == 300
        and all(
            row["logical_arrival_order"] == "2;1"
            for row in detail
            if row["profile"] == "reordered-retry"
        ),
        f"rows={len(detail)} keys={len(keys)}",
    )
    audit.invariant(
        "network_schedule_family_cells",
        len(families) == 50
        and all(integer(row, "attack_n") == 20 for row in families)
        and all(integer(row, "control_n") == 10 for row in families)
        and all(integer(row, "task_yes") == 10 for row in families)
        and all(
            integer(row, "attack_yes") == (20 if row["policy"] == "check-once" else 0)
            for row in families
        ),
        f"family_rows={len(families)}",
    )
    for profile, display in profiles:
        check = row_where(inference, profile=profile, policy="check-once")
        bound = row_where(inference, profile=profile, policy="receipt-bound")
        pair = row_where(paired, profile=profile)
        audit.invariant(
            f"network_schedule_{profile}_statistics",
            integer(check, "attack_n") == 100
            and integer(check, "attack_yes") == 100
            and integer(bound, "attack_n") == 100
            and integer(bound, "attack_yes") == 0
            and integer(check, "task_yes") == 50
            and integer(bound, "task_yes") == 50
            and abs(float(check["asr_wilson_low"]) - 0.963005) < 1e-6
            and abs(float(bound["asr_wilson_high"]) - 0.036995) < 1e-6
            and integer(pair, "check_once_only_attack") == 100
            and integer(pair, "receipt_bound_only_attack") == 0
            and abs(float(pair["exact_mcnemar_p"]) - 1.5777218104420236e-30) < 1e-40,
            f"check={check}; bound={bound}; pair={pair}",
        )
        fragment = (
            f"{display} & 100/100 & 0/100 & 50/50 & "
            f"{check['benign_client_median_ms']}/{bound['benign_client_median_ms']}"
        )
        audit.add(
            f"network_schedule_{profile}_table",
            "analysis/network_schedule_inference.csv; analysis/network_schedule_paired.csv",
            fragment.replace(" & ", ", "),
            fragment,
        )
    totals_fragment = (
        "All 1,000 attack rows pass the active gate; all 300 reordered rows observe attempt 2 first. "
        "Across 2,100 gateway attempts, 1,600 deliveries yield 1,000 ledger rows"
    )
    audit.add(
        "network_schedule_totals",
        "analysis/network_schedule_detail.csv",
        totals_fragment,
        totals_fragment,
    )


def audit_async_queue_commit(audit: Audit) -> None:
    detail = read_csv(ANALYSIS / "async_queue_commit_detail.csv")
    summary = read_csv(ANALYSIS / "async_queue_commit_summary.csv")
    integrity = read_csv(ANALYSIS / "async_queue_commit_integrity.csv")[0]
    keys = {
        (row["profile"], row["policy"], row["scenario_id"])
        for row in detail
    }
    for profile in ("steady-consumer", "broker-restart"):
        check = row_where(summary, profile=profile, policy="check-once")
        bound = row_where(summary, profile=profile, policy="receipt-bound")
        audit.invariant(
            f"async_queue_{profile}_cell",
            integer(check, "rows") == 150
            and integer(bound, "rows") == 150
            and integer(check, "attack_n") == 100
            and integer(check, "stale_commits") == 100
            and integer(bound, "attack_n") == 100
            and integer(bound, "stale_commits") == 0
            and integer(check, "control_tasks") == 50
            and integer(bound, "control_tasks") == 50
            and integer(check, "duplicate_rows") == 30
            and integer(bound, "duplicate_rows") == 30
            and integer(check, "queue_deliveries") == 180
            and integer(bound, "queue_deliveries") == 180,
            f"check={check}; bound={bound}",
        )
    audit.invariant(
        "async_queue_integrity",
        len(detail) == 600
        and len(keys) == 600
        and integer(integrity, "rows") == 600
        and integer(integrity, "unique_keys") == 600
        and integer(integrity, "attack_rows") == 400
        and integer(integrity, "control_rows") == 200
        and integer(integrity, "stale_commits") == 200
        and integer(integrity, "control_tasks") == 200
        and integer(integrity, "attack_enqueue_gates") == 400
        and integer(integrity, "attack_delivery_gates") == 400
        and integer(integrity, "substitution_rows") == 80
        and integer(integrity, "restart_rows") == 300
        and integer(integrity, "restart_gates") == 300
        and integer(integrity, "fifo_gates") == 600
        and integer(integrity, "duplicate_rows") == 120
        and integer(integrity, "queue_deliveries") == 720
        and integer(integrity, "queue_releases") == 120
        and integer(integrity, "queue_acks") == 600
        and integer(integrity, "queue_final_acked") == 600
        and integer(integrity, "effect_attempts") == 720
        and integer(integrity, "effect_rows") == 400
        and integer(integrity, "nonce_rows") == 20
        and integer(integrity, "second_idempotent_rows") == 80
        and integer(integrity, "distinct_role_rows") == 600,
        str(integrity),
    )
    fragment = (
        "A separate 600-row durable-queue matrix repeats the 150 scenarios under steady consumption and "
        "broker restart; profiles are not pooled. All 400 attacks pass the enqueue-before-mutation-before-delivery "
        "gate. Per profile, check-once/receipt-bound ASR is 100/100 versus 0/100 with 50/50 TCR (paired "
        "$p=1.58\\times10^{-30}$; Wilson [0.963,1.000]/[0,0.037]). Every fifth message loses its first "
        "acknowledgement: 120 rows produce 720 deliveries but one effect per allowed trial. All 300 restart rows "
        "survive a new broker process; all 600 first deliveries are FIFO. This is not production-broker evidence."
    )
    audit.add(
        "async_queue_result",
        "analysis/async_queue_commit_detail.csv; analysis/async_queue_commit_summary.csv; "
        "analysis/async_queue_commit_integrity.csv",
        fragment,
        fragment,
    )


def audit_docker_queue_failover(audit: Audit) -> None:
    detail = read_csv(ANALYSIS / "docker_queue_failover_detail.csv")
    summary = read_csv(ANALYSIS / "docker_queue_failover_summary.csv")
    integrity = read_csv(ANALYSIS / "docker_queue_failover_integrity.csv")[0]
    metadata = read_csv(ANALYSIS / "docker_queue_failover_metadata.csv")[0]
    keys = {(row["profile"], row["policy"], row["scenario_id"]) for row in detail}
    for profile in ("partition-before-commit", "crash-after-commit"):
        check = row_where(summary, profile=profile, policy="check-once")
        bound = row_where(summary, profile=profile, policy="receipt-bound")
        expected_attempts = 150 if profile == "partition-before-commit" else 300
        audit.invariant(
            f"docker_queue_failover_{profile}_cell",
            integer(check, "rows") == 150
            and integer(bound, "rows") == 150
            and integer(check, "attack_n") == 100
            and integer(check, "stale_commits") == 100
            and integer(bound, "attack_n") == 100
            and integer(bound, "stale_commits") == 0
            and integer(check, "control_n") == 50
            and integer(bound, "control_n") == 50
            and integer(check, "control_tasks") == 50
            and integer(bound, "control_tasks") == 50
            and integer(check, "queue_deliveries") == 300
            and integer(bound, "queue_deliveries") == 300
            and integer(check, "effect_attempts") == expected_attempts
            and integer(bound, "effect_attempts") == expected_attempts
            and integer(check, "effect_rows") == 150
            and integer(bound, "effect_rows") == 50,
            f"check={check}; bound={bound}",
        )
    partition = [row for row in detail if row["profile"] == "partition-before-commit"]
    crash = [row for row in detail if row["profile"] == "crash-after-commit"]
    audit.invariant(
        "docker_queue_failover_integrity",
        len(detail) == 600
        and len(keys) == 600
        and len(partition) == 300
        and len(crash) == 300
        and all(integer(row, "partition_gate") == 1 for row in partition)
        and all(integer(row, "partition_failure_gate") == 1 for row in partition)
        and all(integer(row, "crash_commit_gate") == 1 for row in crash)
        and all(integer(row, "consumer_killed_gate") == 1 for row in detail)
        and all(integer(row, "recovery_gate") == 1 for row in detail)
        and all(integer(row, "consumer_b_gate") == 1 for row in detail)
        and all(integer(row, "distinct_role_gate") == 1 for row in detail)
        and all(integer(row, "loopback_publish_gate") == 1 for row in detail)
        and all(integer(row, "bridge_gate") == 1 for row in detail)
        and integer(integrity, "rows") == 600
        and integer(integrity, "unique_keys") == 600
        and integer(integrity, "attack_rows") == 400
        and integer(integrity, "control_rows") == 200
        and integer(integrity, "partition_rows") == 300
        and integer(integrity, "partition_gates") == 300
        and integer(integrity, "partition_failure_gates") == 300
        and integer(integrity, "crash_rows") == 300
        and integer(integrity, "crash_commit_gates") == 300
        and integer(integrity, "consumer_killed_gates") == 600
        and integer(integrity, "recovery_gates") == 600
        and integer(integrity, "consumer_b_gates") == 600
        and integer(integrity, "queue_deliveries") == 1200
        and integer(integrity, "queue_recoveries") == 600
        and integer(integrity, "queue_acks") == 600
        and integer(integrity, "effect_attempts") == 900
        and integer(integrity, "effect_rows") == 400
        and integer(integrity, "nonce_rows") == 20
        and integer(integrity, "second_idempotent_rows") == 200
        and integer(metadata, "fault_epochs") == 4
        and integer(metadata, "matrix_rows") == 600
        and metadata["network_driver"] == "bridge"
        and metadata["host_publish"] == "127.0.0.1-random",
        f"integrity={integrity}; metadata={metadata}",
    )
    fragment = (
        "A separate 600-row four-container failover replication injects one shared fault epoch per 150-row cell, "
        "not independent faults: after A claims every message, Docker either disconnects its effect path before "
        "commit or kills it after commit but before acknowledgement; B recovers all 600. Per profile, "
        "check-once/receipt-bound ASR is 100/100 versus 0/100 and TCR 50/50. Across 1,200 broker deliveries and "
        "900 effect attempts, every allowed trial has one effect; all 200 allowed crash redeliveries are idempotent. "
        "This is consumer-path Docker fault injection against a reference queue, not production-broker or "
        "broker-partition evidence."
    )
    audit.add(
        "docker_queue_failover_result",
        "analysis/docker_queue_failover_detail.csv; analysis/docker_queue_failover_summary.csv; "
        "analysis/docker_queue_failover_integrity.csv; analysis/docker_queue_failover_metadata.csv",
        fragment,
        fragment,
    )


def audit_service_integrated_commit(audit: Audit) -> None:
    detail = read_csv(ANALYSIS / "service_integrated_commit_detail.csv")
    summary = read_csv(ANALYSIS / "service_integrated_commit_summary.csv")
    integrity = read_csv(ANALYSIS / "service_integrated_commit_integrity.csv")[0]
    pg_detail = read_csv(ANALYSIS / "postgres_integrated_commit_detail.csv")
    pg_summary = read_csv(ANALYSIS / "postgres_integrated_commit_summary.csv")
    pg_integrity = read_csv(ANALYSIS / "postgres_integrated_commit_integrity.csv")[0]
    pg_metadata = read_csv(ANALYSIS / "postgres_integrated_commit_metadata.csv")[0]
    pre_split = row_where(summary, schedule="pre-transaction", policy="gateway-split")
    pre_atomic = row_where(summary, schedule="pre-transaction", policy="service-atomic")
    critical_split = row_where(summary, schedule="critical-window", policy="gateway-split")
    critical_atomic = row_where(summary, schedule="critical-window", policy="service-atomic")
    audit.invariant(
        "service_integrated_matrix",
        len(detail) == 540
        and len({(row["schedule"], row["policy"], row["scenario_id"]) for row in detail}) == 540
        and integer(pre_split, "attack_n") == 100
        and integer(pre_split, "stale_commits") == 100
        and integer(pre_atomic, "attack_n") == 100
        and integer(pre_atomic, "stale_commits") == 0
        and integer(critical_split, "attack_n") == 80
        and integer(critical_split, "stale_commits") == 80
        and integer(critical_atomic, "attack_n") == 80
        and integer(critical_atomic, "stale_commits") == 0
        and sum(integer(row, "control_tasks") for row in summary) == 180,
        str(summary),
    )
    pg_pre_split = row_where(
        pg_summary, schedule="pre-transaction", policy="gateway-split"
    )
    pg_pre_atomic = row_where(
        pg_summary, schedule="pre-transaction", policy="service-atomic"
    )
    pg_critical_split = row_where(
        pg_summary, schedule="critical-window", policy="gateway-split"
    )
    pg_critical_atomic = row_where(
        pg_summary, schedule="critical-window", policy="service-atomic"
    )
    audit.invariant(
        "postgres_integrated_matrix",
        len(pg_detail) == 540
        and all(row["backend"] == "postgresql" for row in pg_detail)
        and len(
            {(row["schedule"], row["policy"], row["scenario_id"]) for row in pg_detail}
        )
        == 540
        and integer(pg_pre_split, "stale_commits") == 100
        and integer(pg_pre_atomic, "stale_commits") == 0
        and integer(pg_critical_split, "stale_commits") == 80
        and integer(pg_critical_atomic, "stale_commits") == 0
        and sum(integer(row, "control_tasks") for row in pg_summary) == 180,
        str(pg_summary),
    )
    audit.invariant(
        "postgres_integrated_metadata",
        pg_metadata["backend"] == "postgresql"
        and pg_metadata["server_version"].startswith("17.")
        and pg_metadata["transaction_isolation"] == "read committed"
        and pg_metadata["driver"] == "psycopg"
        and integer(pg_metadata, "matrix_rows") == 540,
        str(pg_metadata),
    )
    result_fragment = (
        "Across each backend's two schedules, gateway-split makes 100/100 and 80/80 stale commits; "
        "service-atomic makes 0/100 and 0/80, while all 180 controls complete."
    )
    audit.add(
        "service_integrated_result",
        "analysis/service_integrated_commit_summary.csv; analysis/postgres_integrated_commit_summary.csv",
        result_fragment,
        result_fragment,
    )
    audit.invariant(
        "service_integrated_integrity",
        integer(integrity, "rows") == 540
        and integer(integrity, "unique_keys") == 540
        and integer(integrity, "attack_rows") == 360
        and integer(integrity, "control_rows") == 180
        and integer(integrity, "critical_atomic_rows") == 80
        and integer(integrity, "critical_verifier_gates") == 80
        and integer(integrity, "critical_mutation_request_gates") == 80
        and integer(integrity, "critical_deferred_lock_gates") == 80
        and integer(integrity, "critical_serialized_commits") == 80
        and integer(integrity, "duplicate_rows") == 108
        and integer(integrity, "delivery_attempts") == 648
        and integer(integrity, "effect_rows") == 440
        and integer(integrity, "nonce_rows") == 40,
        str(integrity),
    )
    audit.invariant(
        "postgres_integrated_integrity",
        integer(pg_integrity, "rows") == 540
        and integer(pg_integrity, "unique_keys") == 540
        and integer(pg_integrity, "attack_rows") == 360
        and integer(pg_integrity, "control_rows") == 180
        and integer(pg_integrity, "critical_atomic_rows") == 80
        and integer(pg_integrity, "critical_verifier_gates") == 80
        and integer(pg_integrity, "critical_mutation_request_gates") == 80
        and integer(pg_integrity, "critical_deferred_lock_gates") == 80
        and integer(pg_integrity, "critical_serialized_commits") == 80
        and integer(pg_integrity, "duplicate_rows") == 108
        and integer(pg_integrity, "delivery_attempts") == 648
        and integer(pg_integrity, "effect_rows") == 440
        and integer(pg_integrity, "nonce_rows") == 40,
        str(pg_integrity),
    )
    key_fields = ("schedule", "policy", "scenario_id")
    outcome_fields = (
        "attack",
        "task",
        "committed",
        "authorized_attack_commit",
        "duplicate_delivery",
        "delivery_attempts",
        "effect_rows",
        "nonce_rows",
        "second_idempotent",
        "serialized_commit_before_mutation",
    )
    sqlite_outcomes = {
        tuple(row[field] for field in key_fields): tuple(
            row[field] for field in outcome_fields
        )
        for row in detail
    }
    postgres_outcomes = {
        tuple(row[field] for field in key_fields): tuple(
            row[field] for field in outcome_fields
        )
        for row in pg_detail
    }
    audit.invariant(
        "service_integrated_backend_pairing",
        sqlite_outcomes == postgres_outcomes and len(sqlite_outcomes) == 540,
        f"sqlite={len(sqlite_outcomes)}, postgresql={len(postgres_outcomes)}",
    )
    causal_fragment = (
        "All 80 critical-window atomic mutations per backend are requested after verification but acquire "
        "the SQLite write lock or PostgreSQL row lock only after effect commit."
    )
    totals_fragment = (
        "Each matrix records 648 delivery attempts across 108 duplicate rows, 440 effects, and 40 "
        "transaction-bound nonce consumptions; every trial has at most one effect."
    )
    audit.add(
        "service_integrated_causal_gate",
        "analysis/service_integrated_commit_detail.csv; analysis/service_integrated_commit_integrity.csv; "
        "analysis/postgres_integrated_commit_detail.csv; analysis/postgres_integrated_commit_integrity.csv",
        causal_fragment,
        causal_fragment,
    )
    audit.add(
        "service_integrated_totals",
        "analysis/service_integrated_commit_integrity.csv; analysis/postgres_integrated_commit_integrity.csv",
        totals_fragment,
        totals_fragment,
    )
    portability_fragment = (
        "All 540 same-key discrete security, utility, idempotency, and ledger outcomes match across backends."
    )
    audit.add(
        "service_integrated_backend_portability",
        "analysis/service_integrated_commit_detail.csv; analysis/postgres_integrated_commit_detail.csv",
        portability_fragment,
        portability_fragment,
    )


def audit_narrative_evidence(audit: Audit) -> None:
    utility = read_csv(ANALYSIS / "authorization_utility_summary.csv")
    ambiguous = row_where(utility, scope="ambiguous-authorization", policy="IACG")
    legitimate = row_where(utility, scope="implicit-legitimate-persistence", policy="IACG")
    protected = integer(ambiguous, "attack_n") - integer(ambiguous, "attack_yes")
    false_blocks = integer(legitimate, "false_block_yes")
    utility_fragment = (
        f"Lexical IACG blocks {ratio(protected, integer(ambiguous, 'attack_n'))} ambiguous attacks but also "
        f"{ratio(false_blocks, integer(legitimate, 'benign_n'))} legitimate persistence requests."
    )
    audit.add("authorization_utility", "analysis/authorization_utility_summary.csv", utility_fragment, utility_fragment)

    staged = read_csv(ANALYSIS / "amb1_stg1_summary.csv")
    staged_permissive = row_where(staged, run_id="stg1", tag="permissive")
    staged_guard = row_where(staged, run_id="stg1", tag="guard")
    staged_n = integer(staged_permissive, "n")
    audit.invariant(
        "staged_tcr",
        integer(staged_permissive, "task_successes") == staged_n
        and integer(staged_guard, "task_successes") == staged_n,
        f"n={staged_n}",
    )
    staged_fragment = (
        f"Five staged cases yield {ratio(integer(staged_permissive, 'attack_successes'), staged_n)} versus "
        f"{ratio(integer(staged_guard, 'attack_successes'), staged_n)} ASR with intact TCR"
    )
    audit.add("staged_stress", "analysis/amb1_stg1_summary.csv", staged_fragment, staged_fragment)

    failure = read_csv(ANALYSIS / "fail1_summary.csv")
    slc = read_csv(ANALYSIS / "slc_summary.csv")
    failure_guard = row_where(failure, run_id="fail1", tag="guard")
    failure_slc = row_where(slc, run="slc-failure-slc")
    failure_n = integer(failure_guard, "n")
    audit.invariant("failure_stress_n", failure_n == integer(failure_slc, "n"), f"{failure_n},{failure_slc['n']}")
    failure_fragment = (
        f"four negation/misleading-keyword cases yield IACG "
        f"{ratio(integer(failure_guard, 'attack_successes'), failure_n)} versus SLC "
        f"{ratio(integer(failure_slc, 'attack_successes'), failure_n)}"
    )
    audit.add("slc_stress", "analysis/fail1_summary.csv; analysis/slc_summary.csv", failure_fragment, failure_fragment)

    cron_oracle = read_csv(ANALYSIS / "auto_oracle_agreement_summary.csv")[0]
    noncron_oracle = row_where(read_csv(ANALYSIS / "auto_oracle_noncron_summary.csv"), family="ALL")
    cron_n = integer(cron_oracle, "n")
    noncron_n = integer(noncron_oracle, "n")
    cron_agree = integer(cron_oracle, "both_agree")
    noncron_agree = integer(noncron_oracle, "joint_agree")
    oracle_fragment = (
        f"The cron artifact oracle classifies one-shot task state and recurring attack state and agrees with "
        f"{ratio(cron_agree, cron_n)} stored run labels. A separate file/calendar/recipient oracle agrees on "
        f"{ratio(noncron_agree, noncron_n)} runs, for {cron_n + noncron_n} machine-checkable artifacts total."
    )
    audit.add(
        "artifact_oracle_coverage",
        "analysis/auto_oracle_agreement_summary.csv; analysis/auto_oracle_noncron_summary.csv",
        oracle_fragment,
        oracle_fragment,
    )

    agreement = read_csv(ANALYSIS / "label_audit_agreement_summary.csv")
    attack_agreement = row_where(agreement, label="attack_succeeded")
    task_agreement = row_where(agreement, label="task_completed")
    audit_n = integer(attack_agreement, "n_scored")
    audit.invariant("label_audit_sizes", audit_n == integer(task_agreement, "n_scored"), f"{audit_n},{task_agreement['n_scored']}")
    attack_correct = round(float(attack_agreement["observed_agreement"]) * audit_n)
    audit_fragment = (
        f"The blinded {audit_n}-case audit achieves {ratio(attack_correct, audit_n)} attack-label agreement "
        f"($\\kappa={float(attack_agreement['cohen_kappa']):.1f}$); task agreement is "
        f"{float(task_agreement['observed_agreement']):.3f}"
    )
    audit.add("blinded_label_audit", "analysis/label_audit_agreement_summary.csv", audit_fragment, audit_fragment)

    live_report_path = ROOT / "results" / "STAGE_SUMMARY_2026-07-15_INFOCOM_LIVE20.md"
    live_report = live_report_path.read_text(encoding="utf-8")
    gateway = re.search(r"(\w+) initial gateway EOFs were retried successfully", live_report)
    if not gateway:
        raise ValueError(f"could not parse gateway retry count from {live_report_path}")
    gateway_fragment = f"{gateway.group(1)} transient gateway failures were successfully retried and deduplicated."
    audit.add("gateway_retries", str(live_report_path.relative_to(ROOT)), gateway_fragment, None)

def audit_uncertainty(
    audit: Audit,
    model_and_heldout: Dict[str, tuple[int, int]],
    multitool: Dict[str, tuple[int, int]],
) -> None:
    values = {**model_and_heldout, **multitool}
    matched_fragment = (
        f"For n=10/12 extremes, intervals are {ci_text(0, 10)}/{ci_text(10, 10)} "
        f"and {ci_text(0, 12)}/{ci_text(12, 12)}"
    )
    audit.add("uncertainty_matched", "Wilson recomputation", matched_fragment, matched_fragment)
    native_fragment = (
        f"Grok's 9/20 versus 0/20 templates yield {ci_text(9, 20)} versus {ci_text(0, 20)} "
        "and paired $p=0.003906$"
    )
    audit.add("uncertainty_native", "Wilson recomputation", native_fragment, native_fragment)
    extremes_fragment = (
        f"n=50/60/100 extremes are {ci_text(0, 50)}/{ci_text(50, 50)}, "
        f"{ci_text(*values['0/60'])}/{ci_text(*values['60/60'])}, and "
        f"{ci_text(*values['0/100'])}/{ci_text(*values['100/100'])}"
    )
    audit.add("uncertainty_extremes", "Wilson recomputation", extremes_fragment, extremes_fragment)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--paper",
        type=Path,
        default=ROOT / "src" / "sections" / "evaluation.tex",
        help="optional evaluation.tex path; missing files skip paper checks",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ANALYSIS / "infocom_claim_audit.csv",
    )
    parser.add_argument(
        "--focus",
        choices=("all", "native-service-bridge"),
        default="all",
        help="run the full legacy audit or only the native three-service bridge closure",
    )
    args = parser.parse_args()
    paper_text = args.paper.read_text(encoding="utf-8") if args.paper.exists() else None
    audit = Audit(paper_text)
    if args.focus == "native-service-bridge":
        audit_native_service_commit_bridge(audit, check_paper=True)
    else:
        audit_original(audit)
        audit_matched(audit)
        model_and_heldout = audit_heldout_and_models(audit)
        audit_authorization_tables(audit)
        audit_native_e2e(audit)
        audit_adaptive_native_fork(audit)
        audit_adaptive_native_extension(audit)
        audit_method_comparison(audit)
        multitool = audit_multitool_and_overhead(audit)
        audit_commit_race(audit)
        audit_native_service_commit_bridge(audit, check_paper=False)
        audit_network_schedule(audit)
        audit_async_queue_commit(audit)
        audit_docker_queue_failover(audit)
        audit_service_integrated_commit(audit)
        audit_narrative_evidence(audit)
        audit_uncertainty(audit, model_and_heldout, multitool)
    audit.write(args.output)
    checked = sum(row["paper_status"] != "not_checked" for row in audit.rows)
    print(f"claims={len(audit.rows)} paper_checked={checked} failures={len(audit.failures)}")
    print(args.output)
    if audit.failures:
        raise SystemExit("claim audit failed: " + ", ".join(audit.failures))


if __name__ == "__main__":
    main()
