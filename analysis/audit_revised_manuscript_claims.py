#!/usr/bin/env python3
"""Audit the evidence and boundaries claimed by the 2026-07-30 manuscript."""

from __future__ import annotations

import argparse
from collections import Counter
import csv
import pathlib
import re
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_PAPER = ROOT / "paper_versions" / "infocom_nature_polished_2026-07-22" / "src"


def read_csv(path: pathlib.Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def one(rows: list[dict[str, str]], **values: str) -> dict[str, str]:
    selected = [row for row in rows if all(row.get(key) == value for key, value in values.items())]
    if len(selected) != 1:
        raise ValueError(f"expected one row for {values}, found {len(selected)}")
    return selected[0]


class Audit:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    def check(self, check_id: str, source: str, condition: bool, observed: str) -> None:
        self.rows.append(
            {
                "check_id": check_id,
                "source": source,
                "status": "pass" if condition else "fail",
                "observed": observed,
            }
        )

    @property
    def failures(self) -> list[str]:
        return [str(row["check_id"]) for row in self.rows if row["status"] == "fail"]


def load_paper(source: pathlib.Path) -> dict[str, str]:
    names = (
        "abstract",
        "introduction",
        "background_threat_model",
        "psebench_iacg",
        "evaluation",
        "related_work",
        "discussion_limitations",
        "conclusion",
    )
    sections = {
        name: (source / "sections" / f"{name}.tex").read_text(encoding="utf-8")
        for name in names
    }
    sections["all"] = "\n".join(sections.values())
    return sections


def run_audit(source: pathlib.Path) -> list[dict[str, Any]]:
    paper = load_paper(source)
    audit = Audit()

    oracle = one(read_csv(ROOT / "analysis" / "benchmark_oracle_capability_integrity.csv"))
    audit.check(
        "agentdojo_source_inventory",
        "analysis/benchmark_oracle_capability_integrity.csv",
        oracle["agentdojo_revision"].startswith("089ed468")
        and oracle["task_security_methods"] == "27"
        and oracle["post_state_methods"] == "25"
        and oracle["pre_post_methods"] == "14",
        str(oracle),
    )
    audit.check(
        "agentdojo_claim_present",
        "evaluation.tex",
        "Of 27 injection-task security methods, 25 inspect post-task state and 14 inspect both pre- and post-state."
        in paper["evaluation"],
        "27 methods; 25 post-state; 14 pre/post",
    )
    audit.check(
        "agentdojo_no_impossibility_claim",
        "introduction.tex; evaluation.tex; discussion_limitations.tex",
        "AgentDojo is not tool-call-only" in paper["evaluation"]
        and "A custom task could add such a predicate" in paper["evaluation"]
        and "not expressive impossibility" in paper["evaluation"],
        "post-state capability and extensibility are disclosed",
    )

    oracle_distinguishability = read_csv(
        ROOT / "analysis" / "official_oracle_distinguishability_summary.csv"
    )
    oracle_overall = one(oracle_distinguishability, scope="overall")
    oracle_families = [
        row for row in oracle_distinguishability if row["scope"] != "overall"
    ]
    oracle_distinguishability_ok = (
        oracle_overall["cases"] == "16"
        and oracle_overall["labels_differ"] == "8"
        and oracle_overall["official_yes_grant_safe"] == "4"
        and oracle_overall["official_no_grant_violation"] == "4"
        and oracle_overall["both_yes"] == "4"
        and oracle_overall["both_no"] == "4"
        and len(oracle_families) == 4
        and all(
            row["cases"] == "4"
            and row["labels_differ"] == "2"
            and row["official_yes_grant_safe"] == "1"
            and row["official_no_grant_violation"] == "1"
            and row["both_yes"] == "1"
            and row["both_no"] == "1"
            for row in oracle_families
        )
    )
    audit.check(
        "official_oracle_distinguishability",
        "analysis/official_oracle_distinguishability_summary.csv",
        oracle_distinguishability_ok
        and "We then froze 16 no-model states across four official tasks and four effect families."
        in paper["evaluation"]
        and "Labels differed in 8/16 cases, with four disagreements in each direction"
        in paper["evaluation"]
        and "This balance follows the factorial design and is not a prevalence estimate."
        in paper["evaluation"],
        str(oracle_overall),
    )

    oracle_integrity = one(
        read_csv(ROOT / "analysis" / "official_oracle_distinguishability_integrity.csv")
    )
    audit.check(
        "official_oracle_manifest_integrity",
        "analysis/official_oracle_distinguishability_integrity.csv",
        oracle_integrity["manifest_sha256"]
        == "9a21c1f81169f364e1db55cce02c0d4b8b505262ca751173048f1b26d53a82e1"
        and oracle_integrity["agentdojo_revision"].startswith("089ed468")
        and oracle_integrity["agentdojo_core_revision"].startswith("23bf9259")
        and oracle_integrity["same_state_dual_oracle_rows"] == "16"
        and oracle_integrity["family_label_cells_balanced"] == "1",
        str(oracle_integrity),
    )

    summary = read_csv(ROOT / "analysis" / "same_tool_native_commit_summary.csv")
    expected = {
        "gpt-5.5": (5, 0, 44, 48),
        "grok-4.5": (25, 0, 27, 32),
        "gpt-5.4": (4, 0, 44, 44),
        "gpt-5.6-sol": (5, 0, 44, 45),
    }
    native_ok = True
    for model, values in expected.items():
        permissive = one(
            summary,
            requested_alias=model,
            scope="overall",
            cell="all",
            exposure="injected",
            policy="permissive",
        )
        guarded = one(
            summary,
            requested_alias=model,
            scope="overall",
            cell="all",
            exposure="injected",
            policy="IACG",
        )
        observed = (
            int(permissive["attack_yes"]),
            int(guarded["attack_yes"]),
            int(permissive["task_yes"]),
            int(guarded["task_yes"]),
        )
        native_ok &= observed == values
    audit.check(
        "same_tool_native_table",
        "analysis/same_tool_native_commit_summary.csv",
        native_ok
        and all(
            row in paper["evaluation"]
            for row in (
                "GPT-5.5 & 5$\\mid$0 & 1 & 0 & 4 & 44$\\mid$48 & 0.1875",
                "Grok-4.5 & 25$\\mid$0 & 7 & 3 & 11 & 27$\\mid$32",
                "GPT-5.4 & 4$\\mid$0 & 2 & 1 & 1 & 44$\\mid$44 & 0.1875",
                "GPT-5.6-sol & 5$\\mid$0 & 1 & 0 & 4 & 44$\\mid$45 & 0.1875",
            )
        ),
        str(expected),
    )

    multiplicity = read_csv(ROOT / "analysis" / "same_tool_native_commit_multiplicity.csv")
    holm_expected = {
        "gpt-5.5": 0.1875,
        "grok-4.5": 2.384185791015625e-07,
        "gpt-5.4": 0.1875,
        "gpt-5.6-sol": 0.1875,
    }
    holm_ok = all(
        abs(float(one(multiplicity, requested_alias=model)["holm_adjusted_p"]) - value) < 1e-12
        for model, value in holm_expected.items()
    )
    audit.check(
        "holm_family",
        "analysis/same_tool_native_commit_multiplicity.csv",
        holm_ok and "Holm correction" in paper["evaluation"] and "$p_H$" in paper["evaluation"],
        str(holm_expected),
    )

    clusters = read_csv(ROOT / "analysis" / "same_tool_native_commit_cluster_paired.csv")
    cluster_expected = {
        "gpt-5.5": 0.125,
        "grok-4.5": 0.0009765625,
        "gpt-5.4": 0.125,
        "gpt-5.6-sol": 0.125,
    }
    cluster_ok = all(
        abs(
            float(
                one(
                    clusters,
                    requested_alias=model,
                    comparison="permissive-vs-IACG",
                    outcome="attack",
                )["exact_signflip_p"]
            )
            - value
        )
        < 1e-12
        for model, value in cluster_expected.items()
    )
    audit.check(
        "exact_block_sensitivity",
        "analysis/same_tool_native_commit_cluster_paired.csv",
        cluster_ok and "$p=0.000977$" in paper["evaluation"],
        str(cluster_expected),
    )

    bootstrap = read_csv(ROOT / "analysis" / "same_tool_native_commit_cluster_bootstrap.csv")
    bootstrap_expected = {
        "gpt-5.5": (0.020833, 0.208333),
        "grok-4.5": (0.395833, 0.625),
        "gpt-5.4": (0.020833, 0.145833),
        "gpt-5.6-sol": (0.020833, 0.208333),
    }
    bootstrap_ok = all(
        (
            float(one(bootstrap, requested_alias=model)["cluster_bootstrap_CI_low"]),
            float(one(bootstrap, requested_alias=model)["cluster_bootstrap_CI_high"]),
        )
        == values
        for model, values in bootstrap_expected.items()
    )
    audit.check(
        "cluster_bootstrap_intervals",
        "analysis/same_tool_native_commit_cluster_bootstrap.csv",
        bootstrap_ok and "These intervals are descriptive" in paper["evaluation"],
        str(bootstrap_expected),
    )

    detail = [
        row
        for row in read_csv(ROOT / "analysis" / "same_tool_native_commit_detail.csv")
        if row["exposure"] == "injected"
    ]
    workflow_yes = Counter()
    workflow_n = Counter()
    alias_workflow_yes = Counter()
    alias_workflow_n = Counter()
    carrier_yes = Counter()
    carrier_n = Counter()
    for row in detail:
        workflow_yes[row["workflow"]] += int(row["permissive_attack"])
        workflow_n[row["workflow"]] += 1
        alias_workflow_yes[(row["requested_alias"], row["workflow"])] += int(
            row["permissive_attack"]
        )
        alias_workflow_n[(row["requested_alias"], row["workflow"])] += 1
        carrier_yes[row["carrier"]] += int(row["permissive_attack"])
        carrier_n[row["carrier"]] += 1
    expected_alias_workflows = {
        ("gpt-5.5", "file"): 1,
        ("gpt-5.5", "calendar"): 0,
        ("gpt-5.5", "message"): 4,
        ("gpt-5.5", "reminder"): 0,
        ("grok-4.5", "file"): 7,
        ("grok-4.5", "calendar"): 3,
        ("grok-4.5", "message"): 11,
        ("grok-4.5", "reminder"): 4,
        ("gpt-5.4", "file"): 2,
        ("gpt-5.4", "calendar"): 1,
        ("gpt-5.4", "message"): 1,
        ("gpt-5.4", "reminder"): 0,
        ("gpt-5.6-sol", "file"): 1,
        ("gpt-5.6-sol", "calendar"): 0,
        ("gpt-5.6-sol", "message"): 4,
        ("gpt-5.6-sol", "reminder"): 0,
    }
    audit.check(
        "alias_workflow_breakdown",
        "analysis/same_tool_native_commit_detail.csv",
        dict(alias_workflow_yes) == expected_alias_workflows
        and set(alias_workflow_n) == set(expected_alias_workflows)
        and set(alias_workflow_n.values()) == {12}
        and "Across the three non-reminder workflows, permissive attacks total 5/36, 21/36, 4/36, and 5/36 in table order."
        in paper["evaluation"]
        and "Some 12-case cells remain zero, so these strata are descriptive and aliases remain separate."
        in paper["evaluation"],
        f"yes={dict(alias_workflow_yes)} n={dict(alias_workflow_n)}",
    )
    audit.check(
        "carrier_breakdown",
        "analysis/same_tool_native_commit_detail.csv",
        dict(carrier_yes) == {"message": 19, "retrieved-document": 10, "tool-output": 10}
        and set(carrier_n.values()) == {64}
        and "message 19/64, retrieved-document 10/64, and tool-output 10/64"
        in paper["evaluation"],
        f"yes={dict(carrier_yes)} n={dict(carrier_n)}",
    )

    precision = read_csv(ROOT / "analysis" / "same_tool_native_commit_precision.csv")
    precision_ok = all(
        row["minimum_one_direction_discordant_unadjusted_0_05"] == "6"
        and row["minimum_one_direction_discordant_bonferroni_0_05"] == "8"
        and abs(float(row["best_case_power_10pp_unadjusted"]) - 0.346934) < 1e-6
        and abs(float(row["best_case_power_20pp_unadjusted"]) - 0.93787) < 1e-6
        and abs(float(row["best_case_power_30pp_unadjusted"]) - 0.998792) < 1e-6
        for row in precision
    )
    audit.check(
        "fixed_design_sensitivity",
        "analysis/same_tool_native_commit_precision.csv",
        precision_ok and "34.7\%, 93.8\%, and 99.9\%" in paper["evaluation"],
        "min discordance 6/8; best-case power 0.346934/0.937870/0.998792",
    )

    adaptive = one(read_csv(ROOT / "analysis" / "adaptive_effect_v2_integrity.csv"))
    adaptive_ok = (
        adaptive["cases"] == "42"
        and adaptive["safe_cases"] == "12"
        and adaptive["unsafe_cases"] == "30"
        and adaptive["legacy_unsafe_allowed"] == "16"
        and adaptive["strict_v2_unsafe_allowed"] == "0"
        and adaptive["strict_v2_safe_direct_allow"] == "8"
        and adaptive["strict_v2_safe_reviewed"] == "4"
    )
    audit.check(
        "adaptive_v2_outcomes",
        "analysis/adaptive_effect_v2_integrity.csv",
        adaptive_ok
        and "Legacy v1 & 30 & 16 & 14 & 0 & 12/12" in paper["evaluation"]
        and "Strict v2 & 30 & 0 & 14 & 16 & 8/12" in paper["evaluation"],
        str(adaptive),
    )
    audit.check(
        "adaptive_v2_claim_boundary",
        "abstract.tex; discussion_limitations.tex",
        "not universal provider-side safety" in paper["abstract"]
        and "reviews 4/12 safe controls" in paper["discussion_limitations"],
        "provider scope and safe-review cost disclosed",
    )

    commits = read_csv(ROOT / "analysis" / "same_tool_native_commit_commit_summary.csv")
    commit_totals = Counter()
    for row in commits:
        commit_totals[(row["policy"], row["state"])] += int(row["commits"])
    expected_commits = {
        ("cached-pre-action", "stable"): 192,
        ("cached-pre-action", "revoked"): 192,
        ("receipt-bound", "stable"): 192,
        ("receipt-bound", "revoked"): 0,
    }
    audit.check(
        "native_commit_bridge",
        "analysis/same_tool_native_commit_commit_summary.csv",
        dict(commit_totals) == expected_commits
        and "Both policies complete every stable control" in paper["evaluation"]
        and "receipt-bound commit admits none" in paper["evaluation"],
        str(dict(commit_totals)),
    )
    rq3 = paper["evaluation"].split("\\subsection{RQ3", 1)[1].split("\\subsection{RQ4", 1)[0]
    audit.check(
        "forced_invalidation_framing",
        "evaluation.tex RQ3",
        "controlled fault injections" in rq3
        and "not race prevalence" in rq3
        and re.search(r"\\?p\s*=", rq3) is None,
        "RQ3 uses conformance language and no hypothesis-test p-values",
    )

    receipt = read_csv(ROOT / "analysis" / "receipt_field_ablation_summary.csv")
    overall = [row for row in receipt if row["scope"] == "overall"]
    receipt_ok = (
        int(one(overall, policy="receipt-full")["attack_yes"]) == 0
        and int(one(overall, policy="online-reauthorize-at-commit")["attack_yes"]) == 0
        and all(
            int(row["attack_yes"]) == 20
            for row in overall
            if row["policy"].startswith("receipt-no-")
        )
    )
    audit.check(
        "online_reauthorization_tie",
        "analysis/receipt_field_ablation_summary.csv",
        receipt_ok
        and "Online reauthorization ties full receipt" in paper["evaluation"]
        and "not an advantage over a policy engine" in paper["evaluation"],
        "full receipt=0/100; online=0/100; each omission=20/100",
    )

    methods = read_csv(ROOT / "analysis" / "method_comparison_overall_candidate_action.csv")
    tied = all(
        one(methods, comparator_id=identifier)["attack_successes"] == "0"
        and one(methods, comparator_id=identifier)["task_successes"] == "135"
        for identifier in ("CMP-03", "CMP-04", "IACG")
    )
    audit.check(
        "typed_adaptation_tie",
        "analysis/method_comparison_overall_candidate_action.csv",
        tied and "tie IACG on this supplied-effect matrix" in paper["evaluation"],
        "PAuth-style=PCAS-style=IACG: 0/110 ASR, 135/135 TCR",
    )
    audit.check(
        "baseline_fairness_boundary",
        "related_work.tex",
        "We do not infer that the original systems cannot be deployed at commit"
        in paper["related_work"]
        and "online-reauthorization baseline models that strongest placement"
        in paper["related_work"],
        "original systems are not claimed incapable of commit placement",
    )

    formal = paper["background_threat_model"]
    audit.check(
        "formal_object_distinction",
        "background_threat_model.tex",
        all(
            token in formal
            for token in (
                "proposed call",
                "candidate effect",
                "observed committed effect",
                "service-local transaction commit",
                "sequence cardinality",
                "unsupported schema",
            )
        ),
        "proposal/candidate/post-state/linearization/sequence/schema are defined",
    )
    proposition = paper["psebench_iacg"]
    audit.check(
        "conditional_safety_assumptions",
        "psebench_iacg.tex",
        "Conditional safety proposition" in proposition
        and "cover every security-relevant provider field" in proposition
        and "no write bypasses the service transaction" in proposition
        and "not a new cryptographic theorem" in proposition,
        "normalization, observer, receipt, authority, and atomicity assumptions disclosed",
    )
    audit.check(
        "real_provider_limit",
        "discussion_limitations.tex",
        all(
            token in paper["discussion_limitations"]
            for token in (
                "Google Calendar",
                "Microsoft Graph",
                "Provider defaults",
                "undocumented side effects",
                "provider-specific observers",
            )
        ),
        "real-service and provider-observer gap is explicit",
    )
    audit.check(
        "no_sweeping_prior_work_claim",
        "all manuscript sections",
        all(
            forbidden not in paper["all"]
            for forbidden in (
                "Existing tool-call evaluation stops",
                "Benchmarks that exclude already-required tools cannot expose",
                "Existing systems primarily specify or evaluate authorization before execution",
            )
        ),
        "three prior overgeneralizations are absent",
    )
    audit.check(
        "conclusion_scope",
        "conclusion.tex",
        "controlled adapters, service-local atomicity, and forced state changes"
        in paper["conclusion"]
        and "not inferred from tool invocation or task success alone" in paper["conclusion"],
        "conclusion remains within evaluated scope",
    )
    return audit.rows


def write_csv(path: pathlib.Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=pathlib.Path, default=DEFAULT_PAPER)
    parser.add_argument(
        "--output",
        type=pathlib.Path,
        default=ROOT / "analysis" / "revised_manuscript_claim_audit.csv",
    )
    args = parser.parse_args()
    rows = run_audit(args.source)
    write_csv(args.output, rows)
    failures = [row["check_id"] for row in rows if row["status"] == "fail"]
    print(f"revised manuscript claim audit: checks={len(rows)} failures={len(failures)}")
    if failures:
        raise SystemExit("claim audit failed: " + ", ".join(failures))


if __name__ == "__main__":
    main()
