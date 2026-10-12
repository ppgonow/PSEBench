import copy
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runner"))
from external_attack_scenario import source_record_hash
from external_source_provenance import (
    PINNED_SOURCES, build_manifest, in_the_wild_candidates, load_pinned_sources,
    parse_source_bytes, prompt_group_hash, record_hash, validate_legacy_bindings,
    validate_manifest,
)


def fixture():
    records = {
        "advbench": [{"goal": f"Synthetic seed {i}", "target": "Fixture target"} for i in range(36)],
        "alpaca": [{"instruction": f"Synthetic control {i}", "input": "", "output": "Fixture output"} for i in range(36)],
        "shen-in-the-wild-jailbreaks": [
            {"platform": "fixture", "source": "fixture", "prompt": f"Synthetic non-operational wrapper {i}",
             "jailbreak": "True", "created_at": "fixture", "date": "fixture", "community": "fixture",
             "community_id": str(i % 3), "previous_community_id": ""} for i in range(42)
        ],
    }
    bindings = []
    for i in range(36):
        for source_id, suffix, partner in (("advbench", "attack", "benign"), ("alpaca", "benign", "attack")):
            other = "alpaca" if source_id == "advbench" else "advbench"
            item_id = f"advbench:harmful_behaviors.csv:row:{i + 1:04d}" if source_id == "advbench" else f"alpaca:alpaca_data.json:index:{i:04d}"
            bindings.append({
                "binding_id": f"EH-{i + 1:03d}-{suffix}", "scenario_id": f"EH-{i + 1:03d}-{suffix}",
                "source_id": source_id, "source_item_id": item_id,
                "source_item_hash": record_hash(records[source_id][i]),
                "source_file_sha256": PINNED_SOURCES[source_id]["file_sha256"],
                "clean_counterpart_id": f"EH-{i + 1:03d}-{partner}",
                "clean_counterpart_source_item_hash": record_hash(records[other][i]),
                "attack_family": "gradient_or_optimization", "attack_method": "GCG" if suffix == "attack" else "paired_control",
                "conversion_status": "pending", "prompt_content_stored": False,
            })
    legacy = {"item_bindings": bindings}
    registry = {"sources": [
        {"source_id": "advbench", "planned_split": "calibration_or_development"},
        {"source_id": "alpaca", "planned_split": "calibration_or_development"},
        {"source_id": "shen-in-the-wild-jailbreaks", "planned_split": "external_holdout"},
    ]}
    inventory = [{"source_id": source_id, "synthetic_fixture": True} for source_id in records]
    return legacy, records, inventory, registry


class SourceProvenanceTests(unittest.TestCase):
    def test_72_old_and_36_real_source_candidates_reconstruct(self):
        legacy, records, inventory, registry = fixture()
        payload = build_manifest(legacy, records, inventory, registry)
        summary = validate_manifest(payload, records, inventory, legacy, registry)
        self.assertEqual(summary["record_hashes_verified"], 108)
        self.assertEqual(summary["development_records"], 72)
        self.assertEqual(summary["real_in_the_wild_source_candidates"], 36)
        self.assertEqual(summary["external_holdout_scenarios"], 0)
        self.assertEqual(summary["implemented_attack_methods"], 0)

    def test_prefix_seeds_are_not_claimed_as_holdout_or_six_methods(self):
        legacy, records, inventory, registry = fixture()
        payload = build_manifest(legacy, records, inventory, registry)
        self.assertTrue(all(row["split"] == "development" for row in payload["item_bindings"]))
        self.assertTrue(all(row["observed_attack_family"] is None for row in payload["item_bindings"]))
        self.assertEqual(payload["implemented_attack_methods"], [])
        self.assertEqual({row["source_attack_family"] for row in payload["external_holdout_source_candidates"]}, {"in-the-wild"})

    def test_alpaca_language_donors_are_not_verified_benign_pairs(self):
        legacy, records, inventory, registry = fixture()
        payload = build_manifest(legacy, records, inventory, registry)
        controls = [row for row in payload["item_bindings"] if row["source_id"] == "alpaca"]
        self.assertEqual({row["role"] for row in controls}, {"candidate_control_language"})
        self.assertTrue(all(row["content_validity_review"] == "pending" for row in controls))

    def test_unicode_hash_matches_existing_conversion_helper(self):
        record = {"instruction": "保持边界 café", "input": "", "output": "fixture"}
        expected = __import__("hashlib").sha256(json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()
        self.assertEqual(record_hash(record), expected)
        self.assertEqual(source_record_hash(record), expected)

    def test_record_key_order_does_not_change_hash(self):
        self.assertEqual(record_hash({"a": "1", "b": "2"}), record_hash({"b": "2", "a": "1"}))

    def test_nan_cannot_enter_hash_canonicalization(self):
        with self.assertRaises(ValueError):
            record_hash({"value": float("nan")})

    def test_digest_is_recomputed_not_trusted_from_json(self):
        legacy, records, _, _ = fixture()
        legacy["item_bindings"][0]["source_item_hash"] = "f" * 64
        with self.assertRaisesRegex(ValueError, "reconstructed"):
            validate_legacy_bindings(legacy, records)

    def test_snapshot_mismatch_is_rejected(self):
        legacy, records, _, _ = fixture()
        legacy["item_bindings"][0]["source_file_sha256"] = "f" * 64
        with self.assertRaisesRegex(ValueError, "snapshot"):
            validate_legacy_bindings(legacy, records)

    def test_asymmetric_or_wrong_hash_donor_pairing_is_rejected(self):
        for field, value in (("clean_counterpart_id", "missing"), ("clean_counterpart_source_item_hash", "f" * 64)):
            legacy, records, _, _ = fixture()
            legacy["item_bindings"][0][field] = value
            with self.assertRaisesRegex(ValueError, "pairing|donor hash"):
                validate_legacy_bindings(legacy, records)

    def test_duplicate_binding_and_record_are_rejected(self):
        for field in ("binding_id", "source_item_hash"):
            legacy, records, _, _ = fixture()
            legacy["item_bindings"][1][field] = legacy["item_bindings"][0][field]
            with self.assertRaisesRegex(ValueError, "duplicate"):
                validate_legacy_bindings(legacy, records)

    def test_invalid_or_out_of_range_record_locator_is_rejected(self):
        for locator in ("arbitrary", "advbench:harmful_behaviors.csv:row:0000", "advbench:harmful_behaviors.csv:row:9999"):
            legacy, records, _, _ = fixture()
            legacy["item_bindings"][0]["source_item_id"] = locator
            with self.assertRaises(ValueError):
                validate_legacy_bindings(legacy, records)

    def test_source_registry_policy_cannot_be_silently_changed(self):
        legacy, records, inventory, registry = fixture()
        registry["sources"][0]["planned_split"] = "external_holdout"
        with self.assertRaisesRegex(ValueError, "amendment"):
            build_manifest(legacy, records, inventory, registry)

    def test_prompt_normalization_groups_case_unicode_and_space(self):
        self.assertEqual(prompt_group_hash("  ＡＢＣ   Café  "), prompt_group_hash("abc cafe\u0301"))

    def test_duplicate_ijp_prompts_do_not_inflate_candidates(self):
        legacy, records, _, _ = fixture()
        duplicate = {**records["shen-in-the-wild-jailbreaks"][0], "source": "other-observation"}
        records["shen-in-the-wild-jailbreaks"].append(duplicate)
        selected = in_the_wild_candidates(records, legacy)
        self.assertEqual(len({row["normalized_prompt_group_sha256"] for row in selected}), 36)

    def test_no_candidate_reuses_new_development_text(self):
        legacy, records, _, _ = fixture()
        records["shen-in-the-wild-jailbreaks"][0]["prompt"] = records["advbench"][0]["goal"]
        selected = in_the_wild_candidates(records, legacy)
        forbidden = prompt_group_hash(records["advbench"][0]["goal"])
        self.assertNotIn(forbidden, {row["normalized_prompt_group_sha256"] for row in selected})

    def test_selection_is_stable_and_does_not_use_model_outcomes(self):
        legacy, records, _, _ = fixture()
        self.assertEqual(in_the_wild_candidates(records, legacy), in_the_wild_candidates(copy.deepcopy(records), legacy))

    def test_insufficient_distinct_ijp_groups_fail_closed(self):
        legacy, records, _, _ = fixture()
        records["shen-in-the-wild-jailbreaks"] = records["shen-in-the-wild-jailbreaks"][:35]
        with self.assertRaisesRegex(ValueError, "fewer than 36"):
            in_the_wild_candidates(records, legacy)

    def test_unsupported_source_parser_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unsupported"):
            parse_source_bytes("unknown", b"{}")

    def test_strict_source_schemas_reject_missing_fields(self):
        for source_id, data in (("advbench", b"other,field\na,b\n"), ("alpaca", b'[{"instruction":"fixture"}]'),
                                ("shen-in-the-wild-jailbreaks", b"prompt\nfixture\n")):
            with self.subTest(source_id=source_id):
                with self.assertRaises(ValueError):
                    parse_source_bytes(source_id, data)

    def test_supported_csv_and_json_sources_parse(self):
        self.assertEqual(len(parse_source_bytes("advbench", b"goal,target\nfixture,fixture\n")), 1)
        self.assertEqual(len(parse_source_bytes("alpaca", b'[{"instruction":"fixture","input":"","output":"fixture"}]')), 1)

    def test_raw_source_cache_cannot_be_in_repository(self):
        with self.assertRaisesRegex(ValueError, "outside"):
            load_pinned_sources(ROOT / "tmp")

    def test_changed_source_bytes_fail_before_creating_manifest(self):
        with tempfile.TemporaryDirectory() as cache:
            pathlib.Path(cache, "advbench.raw").write_bytes(b"goal,target\nfixture,fixture\n")
            with self.assertRaisesRegex(ValueError, "bytes mismatch"):
                load_pinned_sources(pathlib.Path(cache))

    def test_manifest_tampering_or_false_live_flag_is_rejected(self):
        legacy, records, inventory, registry = fixture()
        payload = build_manifest(legacy, records, inventory, registry)
        for modified in ({**payload, "scheduled_units": 1}, {**payload, "implemented_attack_methods": ["GCG"]},
                         {**payload, "unexpected_raw_prompt": "fixture"}):
            with self.assertRaisesRegex(ValueError, "reconstructed"):
                validate_manifest(modified, records, inventory, legacy, registry)

    def test_cli_refuses_overwriting_existing_directory(self):
        with tempfile.TemporaryDirectory() as output:
            result = subprocess.run(
                [sys.executable, "-B", str(ROOT / "analysis/prepare_external_source_binding_v3.py"),
                 "--cache-dir", "/nonexistent", "--output-dir", output],
                capture_output=True, text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("output exists", result.stderr)
            self.assertEqual(list(pathlib.Path(output).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
