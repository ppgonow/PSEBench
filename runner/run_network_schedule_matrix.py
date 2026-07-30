#!/usr/bin/env python3
"""Stress commit authorization under controlled cross-service HTTP schedules."""

from __future__ import annotations

import argparse
import csv
from contextlib import ExitStack
from dataclasses import dataclass
import pathlib
import secrets
import statistics
import sys
import threading
import time
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runner"))
from run_http_commit_race import load_scenarios  # noqa: E402
from run_multiprocess_commit_race import (  # noqa: E402
    PersistentJsonPool,
    ServiceCluster,
    percentile,
)


POLICIES = ("check-once", "receipt-bound")


@dataclass(frozen=True)
class ScheduleProfile:
    name: str
    attempt_delays_ms: tuple[float, ...]
    duplicate_downstream: bool = False
    expected_arrival_order: tuple[int, ...] | None = None


PROFILES = (
    ScheduleProfile("single", (2.0,)),
    ScheduleProfile("delayed-40ms", (40.0,)),
    ScheduleProfile("duplicate-downstream", (2.0,), duplicate_downstream=True),
    ScheduleProfile("concurrent-retry", (2.0, 2.0)),
    ScheduleProfile(
        "reordered-retry",
        (20.0, 0.0),
        expected_arrival_order=(2, 1),
    ),
)


class ScheduleClients:
    def __init__(self, cluster: ServiceCluster, size: int = 4):
        self.cluster = cluster
        self.size = size
        self.stack = ExitStack()
        self.pools: dict[str, PersistentJsonPool] = {}

    def __enter__(self) -> "ScheduleClients":
        for role in ("authorization", "gateway", "effect"):
            self.pools[role] = self.stack.enter_context(
                PersistentJsonPool(self.cluster.urls[role], self.size)
            )
        return self

    def post(
        self,
        role: str,
        path: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        return self.pools[role].post(path, payload)

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.stack.close()


def dispatch_attempts(
    clients: ScheduleClients,
    payload: dict[str, Any],
    profile: ScheduleProfile,
    *,
    active_trial_id: str | None = None,
) -> tuple[list[tuple[int, dict[str, Any]]], float, bool]:
    responses: dict[int, dict[str, Any]] = {}
    active_observations: dict[int, bool] = {}
    errors: list[BaseException] = []
    barrier = threading.Barrier(len(profile.attempt_delays_ms) + 1)
    started_ns = time.perf_counter_ns()

    def worker(attempt: int, delay_ms: float) -> None:
        try:
            barrier.wait()
            time.sleep(delay_ms / 1000.0)
            if active_trial_id is not None:
                status = clients.post(
                    "authorization",
                    "/mutation-status",
                    {"trial_id": active_trial_id},
                )
                active_observations[attempt] = bool(
                    status["mutation_applied_ns"] is not None
                    and status["mutation_completed_ns"] is None
                )
                if not active_observations[attempt]:
                    raise RuntimeError(
                        f"mutation was not active before attempt {attempt}"
                    )
            responses[attempt] = clients.post(
                "gateway",
                "/commit",
                payload,
            )
        except BaseException as exc:  # pragma: no cover - CLI failure path
            errors.append(exc)

    workers = [
        threading.Thread(target=worker, args=(attempt, delay_ms))
        for attempt, delay_ms in enumerate(profile.attempt_delays_ms, start=1)
    ]
    for worker_thread in workers:
        worker_thread.start()
    barrier.wait()
    for worker_thread in workers:
        worker_thread.join()
    elapsed_us = (time.perf_counter_ns() - started_ns) / 1000.0
    if errors:
        raise RuntimeError(f"gateway schedule failed: {errors}")
    if set(responses) != set(range(1, len(profile.attempt_delays_ms) + 1)):
        raise RuntimeError(f"incomplete gateway responses: {responses}")
    active_gate = active_trial_id is None or (
        set(active_observations) == set(responses)
        and all(active_observations.values())
    )
    return sorted(responses.items()), elapsed_us, active_gate


def run_case(
    cluster: ServiceCluster,
    clients: ScheduleClients,
    scenario: dict[str, Any],
    policy: str,
    profile: ScheduleProfile,
    *,
    mutation_hold_ms: float,
) -> dict[str, Any]:
    scenario_id = str(scenario["id"])
    trial_id = f"network-schedule:{profile.name}:{policy}:{scenario_id}"
    race = scenario["commit_race"]
    checked = clients.post(
        "authorization",
        "/check",
        {
            "trial_id": trial_id,
            "policy": policy,
            "authorized_effect": race["authorized_effect"],
            "checked_effect": race["checked_effect"],
            "check_context": race["check_context"],
        },
    )
    commit_payload = {
        "trial_id": trial_id,
        "policy": policy,
        "receipt": checked["receipt"],
        "commit_effect": race["commit_effect"],
        "duplicate_delivery": profile.duplicate_downstream,
    }

    mutation_response: dict[str, Any] | None = None
    mutation_errors: list[BaseException] = []
    if scenario["type"] == "attack":
        response_box: dict[str, dict[str, Any]] = {}

        def mutate_worker() -> None:
            try:
                response_box["mutation"] = clients.post(
                    "authorization",
                    "/mutate",
                    {
                        "trial_id": trial_id,
                        "commit_effect": race["commit_effect"],
                        "commit_context": race["commit_context"],
                        "hold_ms": mutation_hold_ms,
                    },
                )
            except BaseException as exc:  # pragma: no cover - CLI failure path
                mutation_errors.append(exc)

        mutation_thread = threading.Thread(target=mutate_worker)
        mutation_thread.start()
        deadline = time.monotonic() + 10
        while True:
            status = clients.post(
                "authorization",
                "/mutation-status",
                {"trial_id": trial_id},
            )
            if status["mutation_applied_ns"] is not None:
                break
            if time.monotonic() >= deadline:
                raise TimeoutError(f"mutation gate timed out: {trial_id}")
            time.sleep(0.0005)
        if status["mutation_completed_ns"] is not None:
            raise RuntimeError(f"mutation ended before dispatch: {trial_id}")
        attempt_responses, profile_e2e_us, active_gate = dispatch_attempts(
            clients,
            commit_payload,
            profile,
            active_trial_id=trial_id,
        )
        mutation_thread.join()
        if mutation_errors:
            raise RuntimeError(f"mutation request failed: {mutation_errors}")
        mutation_response = response_box["mutation"]
    else:
        attempt_responses, profile_e2e_us, _ = dispatch_attempts(
            clients,
            commit_payload,
            profile,
        )

    final_count = clients.post(
        "effect",
        "/count",
        {"trial_id": trial_id},
    )
    arrivals = sorted(
        (
            int(response["commit_request_received_ns"]),
            attempt,
        )
        for attempt, response in attempt_responses
    )
    observed_order = tuple(attempt for _, attempt in arrivals)
    active_gate = int(active_gate) if mutation_response is not None else 0

    committed = any(bool(response["committed"]) for _, response in attempt_responses)
    valid_at_commit = bool(race["expected_valid_at_commit"])
    ledger_rows = int(final_count["ledger_rows"])
    delivery_attempts = int(final_count["delivery_attempts"])
    reorder_gate = int(
        profile.expected_arrival_order is None
        or observed_order == profile.expected_arrival_order
    )
    arrival_gap_us = 0.0
    if len(arrivals) > 1:
        arrival_gap_us = (arrivals[-1][0] - arrivals[0][0]) / 1000.0
    return {
        "profile": profile.name,
        "policy": policy,
        "scenario_id": scenario_id,
        "family": scenario["family"],
        "scenario_type": scenario["type"],
        "invalidation": race["pre_registered_invalidation"],
        "attack": int(committed and not valid_at_commit),
        "task": int(committed and valid_at_commit),
        "committed": int(committed),
        "valid_at_commit": int(valid_at_commit),
        "gateway_attempts": len(attempt_responses),
        "logical_arrival_order": ";".join(map(str, observed_order)),
        "reorder_gate": reorder_gate,
        "mutation_active_gate": active_gate,
        "delivery_attempts": delivery_attempts,
        "ledger_rows": ledger_rows,
        "profile_e2e_us": round(profile_e2e_us, 3),
        "arrival_gap_us": round(arrival_gap_us, 3),
        "gateway_max_us": round(
            max(float(response["gateway_total_us"]) for _, response in attempt_responses),
            3,
        ),
        "role_distinct": int(len(set(cluster.pids.values())) == 3),
    }


def summarize(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for profile in PROFILES:
        for policy in POLICIES:
            selected = [
                row
                for row in rows
                if row["profile"] == profile.name and row["policy"] == policy
            ]
            attacks = [row for row in selected if row["scenario_type"] == "attack"]
            controls = [row for row in selected if row["scenario_type"] == "benign"]
            latencies = [float(row["profile_e2e_us"]) for row in selected]
            output.append(
                {
                    "profile": profile.name,
                    "policy": policy,
                    "rows": len(selected),
                    "attack_n": len(attacks),
                    "attack_yes": sum(int(row["attack"]) for row in attacks),
                    "control_n": len(controls),
                    "task_yes": sum(int(row["task"]) for row in controls),
                    "gateway_attempts": sum(int(row["gateway_attempts"]) for row in selected),
                    "delivery_attempts": sum(int(row["delivery_attempts"]) for row in selected),
                    "ledger_rows": sum(int(row["ledger_rows"]) for row in selected),
                    "active_attack_rows": sum(
                        int(row["mutation_active_gate"]) for row in attacks
                    ),
                    "reorder_pass_rows": sum(int(row["reorder_gate"]) for row in selected),
                    "client_p50_us": round(percentile(latencies, 0.50), 3),
                    "client_p95_us": round(percentile(latencies, 0.95), 3),
                    "client_p99_us": round(percentile(latencies, 0.99), 3),
                    "client_median_us": round(statistics.median(latencies), 3),
                }
            )
    return output


def validate(rows: list[dict[str, Any]], scenarios: list[dict[str, Any]]) -> None:
    expected_keys = {
        (profile.name, policy, str(scenario["id"]))
        for profile in PROFILES
        for policy in POLICIES
        for scenario in scenarios
    }
    observed_keys = {
        (str(row["profile"]), str(row["policy"]), str(row["scenario_id"]))
        for row in rows
    }
    if len(rows) != len(expected_keys) or observed_keys != expected_keys:
        raise RuntimeError("network schedule matrix is incomplete or duplicated")
    profile_by_name = {profile.name: profile for profile in PROFILES}
    for row in rows:
        profile = profile_by_name[str(row["profile"])]
        is_attack = row["scenario_type"] == "attack"
        expected_allow = row["policy"] == "check-once" or not is_attack
        expected_deliveries = 0
        if expected_allow:
            expected_deliveries = (
                2 if profile.duplicate_downstream else len(profile.attempt_delays_ms)
            )
        if (
            int(row["committed"]) != int(expected_allow)
            or int(row["attack"]) != int(expected_allow and is_attack)
            or int(row["task"]) != int(expected_allow and not is_attack)
            or int(row["gateway_attempts"]) != len(profile.attempt_delays_ms)
            or int(row["delivery_attempts"]) != expected_deliveries
            or int(row["ledger_rows"]) != int(expected_allow)
            or int(row["role_distinct"]) != 1
            or (is_attack and int(row["mutation_active_gate"]) != 1)
            or int(row["reorder_gate"]) != 1
        ):
            raise RuntimeError(f"network schedule invariant failed: {row}")
    totals = {
        "gateway_attempts": sum(int(row["gateway_attempts"]) for row in rows),
        "delivery_attempts": sum(int(row["delivery_attempts"]) for row in rows),
        "ledger_rows": sum(int(row["ledger_rows"]) for row in rows),
        "active_attack_rows": sum(
            int(row["mutation_active_gate"])
            for row in rows
            if row["scenario_type"] == "attack"
        ),
        "reordered_rows": sum(
            1 for row in rows if row["profile"] == "reordered-retry"
        ),
    }
    expected_totals = {
        "gateway_attempts": 2100,
        "delivery_attempts": 1600,
        "ledger_rows": 1000,
        "active_attack_rows": 1000,
        "reordered_rows": 300,
    }
    if len(scenarios) == 150 and totals != expected_totals:
        raise RuntimeError(f"network schedule totals mismatch: {totals}")


def write_csv(path: pathlib.Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scenario-dir",
        type=pathlib.Path,
        default=ROOT / "scenarios" / "commit-race-heldout",
    )
    parser.add_argument(
        "--output-root",
        type=pathlib.Path,
        default=ROOT / "results" / "network_schedule",
    )
    parser.add_argument(
        "--analysis-prefix",
        type=pathlib.Path,
        default=ROOT / "analysis" / "network_schedule",
    )
    parser.add_argument("--state-delay-ms", type=float, default=0.5)
    parser.add_argument("--service-delay-ms", type=float, default=0.5)
    parser.add_argument("--mutation-hold-ms", type=float, default=100.0)
    parser.add_argument("--pilot", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if (
        args.state_delay_ms != 0.5
        or args.service_delay_ms != 0.5
        or args.mutation_hold_ms != 100.0
    ):
        raise SystemExit("frozen schedule run requires delays 0.5/0.5/100 ms")

    scenarios = load_scenarios(args.scenario_dir)
    if args.pilot:
        attack = next(row for row in scenarios if row["type"] == "attack")
        control = next(row for row in scenarios if row["type"] == "benign")
        scenarios = [attack, control]
        args.output_root = ROOT / "tmp" / "network_schedule_pilot"
    elif len(scenarios) != 150:
        raise SystemExit("formal schedule run requires all 150 frozen scenarios")

    detail_path = pathlib.Path(f"{args.analysis_prefix}_detail.csv")
    summary_path = pathlib.Path(f"{args.analysis_prefix}_summary.csv")
    database_paths = {
        profile.name: args.output_root / f"{profile.name}.sqlite"
        for profile in PROFILES
    }
    protected_paths = list(database_paths.values())
    if not args.pilot:
        protected_paths.extend([detail_path, summary_path])
    if any(path.exists() for path in protected_paths) and not args.overwrite:
        raise SystemExit("schedule output exists; pass --overwrite for a fresh run")
    args.output_root.mkdir(parents=True, exist_ok=True)
    for database_path in database_paths.values():
        database_path.unlink(missing_ok=True)

    rows: list[dict[str, Any]] = []
    authentication_key = secrets.token_bytes(32)
    for profile_index, profile in enumerate(PROFILES):
        with ServiceCluster(
            database_paths[profile.name],
            authentication_key,
            state_delay_ms=args.state_delay_ms,
            service_delay_ms=args.service_delay_ms,
            pooled_http=True,
            pool_size=4,
        ) as cluster:
            with ScheduleClients(cluster, size=4) as clients:
                policy_order = (
                    POLICIES if profile_index % 2 == 0 else tuple(reversed(POLICIES))
                )
                for policy in policy_order:
                    for scenario in scenarios:
                        rows.append(
                            run_case(
                                cluster,
                                clients,
                                scenario,
                                policy,
                                profile,
                                mutation_hold_ms=args.mutation_hold_ms,
                            )
                        )
    validate(rows, scenarios)
    if args.pilot:
        for database_path in database_paths.values():
            database_path.unlink(missing_ok=True)
        print(f"network schedule pilot passed: rows={len(rows)}")
    else:
        write_csv(detail_path, rows)
        write_csv(summary_path, summarize(rows))
        print(f"network schedule matrix passed: rows={len(rows)}")


if __name__ == "__main__":
    main()
