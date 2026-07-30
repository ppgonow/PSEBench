import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runner"))

from postgres_integrated_commit import validate_loopback_dsn, validate_schema_name


class PostgresGuardrailTests(unittest.TestCase):
    def test_schema_accepts_fixed_condition_identifier(self):
        self.assertEqual(
            validate_schema_name("pse_pre_transaction_service_atomic"),
            "pse_pre_transaction_service_atomic",
        )

    def test_schema_rejects_quoted_or_qualified_identifier(self):
        for value in ("PSE", "pse-public", "pse.public", 'pse"public'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_schema_name(value)

    def test_dsn_accepts_loopback_and_rejects_remote_host(self):
        local = "postgresql://user:password@127.0.0.1:5432/psebench"
        self.assertEqual(validate_loopback_dsn(local), local)
        with self.assertRaises(ValueError):
            validate_loopback_dsn(
                "postgresql://user:password@database.test/psebench"
            )


if __name__ == "__main__":
    unittest.main()
