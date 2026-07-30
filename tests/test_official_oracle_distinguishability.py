import csv
import hashlib
import importlib.util
import pathlib
import subprocess
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "analysis" / "audit_official_oracle_distinguishability.py"
SPEC = importlib.util.spec_from_file_location("oracle_distinguishability", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def compatible_python():
    candidates = [
        pathlib.Path(sys.executable),
        pathlib.Path("/opt/homebrew/bin/python3.12"),
        pathlib.Path("/opt/homebrew/bin/python3.11"),
    ]
    for candidate in candidates:
        if not candidate.is_file():
            continue
        probe = subprocess.run(
            [str(candidate), "-c", "import pydantic; assert hasattr(pydantic.BaseModel, 'model_copy')"],
            capture_output=True,
            text=True,
        )
        if probe.returncode == 0:
            return candidate
    return None


class OfficialOracleDistinguishabilityTests(unittest.TestCase):
    def test_manifest_is_prefrozen_and_balanced(self):
        manifest_path = (
            ROOT / "scenarios" / "oracle-distinguishability" / "official_agentdojo_v1.json"
        )
        manifest = MODULE.load_manifest()
        self.assertTrue(manifest["frozen_before_evaluation"])
        self.assertEqual(len(manifest["cases"]), 16)
        self.assertEqual(
            hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
            "9a21c1f81169f364e1db55cce02c0d4b8b505262ca751173048f1b26d53a82e1",
        )
        counts = {}
        for case in manifest["cases"]:
            counts[case["family"]] = counts.get(case["family"], 0) + 1
        self.assertEqual(set(counts.values()), {4})

    def test_stored_result_has_all_four_label_cells_per_family(self):
        path = ROOT / "analysis" / "official_oracle_distinguishability_summary.csv"
        if not path.is_file():
            self.skipTest("stored distinguishability result has not been generated")
        rows = read_csv(path)
        family_rows = [row for row in rows if row["scope"] != "overall"]
        self.assertEqual(len(family_rows), 4)
        for row in family_rows:
            self.assertEqual(row["cases"], "4")
            self.assertEqual(row["official_yes_grant_safe"], "1")
            self.assertEqual(row["official_no_grant_violation"], "1")
            self.assertEqual(row["both_yes"], "1")
            self.assertEqual(row["both_no"], "1")
        overall = next(row for row in rows if row["scope"] == "overall")
        self.assertEqual(overall["cases"], "16")
        self.assertEqual(overall["labels_differ"], "8")
        self.assertEqual(overall["official_yes_grant_safe"], "4")
        self.assertEqual(overall["official_no_grant_violation"], "4")

    def test_official_predicates_reproduce_frozen_labels(self):
        if not (ROOT / "external" / "official_reproduction" / "agentdojo").is_dir():
            self.skipTest("official AgentDojo checkout is intentionally not bundled")
        python = compatible_python()
        if python is None:
            self.skipTest("no Python with pydantic>=2 is available")
        with tempfile.TemporaryDirectory() as directory:
            prefix = pathlib.Path(directory) / "oracle"
            completed = subprocess.run(
                [str(python), str(SCRIPT), "--output-prefix", str(prefix)],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
            generated = read_csv(pathlib.Path(f"{prefix}_detail.csv"))
        stored_path = ROOT / "analysis" / "official_oracle_distinguishability_detail.csv"
        if not stored_path.is_file():
            self.skipTest("stored distinguishability result has not been generated")
        stored = read_csv(stored_path)
        columns = (
            "case_id",
            "official_goal_satisfied",
            "current_grant_violation",
            "labels_differ",
            "pse_reason",
        )
        self.assertEqual(
            [{column: row[column] for column in columns} for row in generated],
            [{column: row[column] for column in columns} for row in stored],
        )


if __name__ == "__main__":
    unittest.main()
