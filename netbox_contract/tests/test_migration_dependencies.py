import ast
import unittest
from pathlib import Path


MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations"


def get_dependencies(migration_name):
    tree = ast.parse((MIGRATIONS_DIR / migration_name).read_text(encoding="utf-8"))
    migration_class = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "Migration"
    )
    dependencies = next(
        node
        for node in migration_class.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "dependencies"
            for target in node.targets
        )
    )
    return ast.literal_eval(dependencies.value)


class RevenueMigrationDependencyTest(unittest.TestCase):
    def test_revenue_migrations_do_not_require_newer_netbox_extras_migrations(self):
        expected_dependencies = {
            "0048_revenuebillingrule_revenuecontract_and_more.py": [
                ("netbox_contract", "0047_alter_contract_external_party_object_type"),
            ],
            "0053_revenuereceivableplan_revenuereceivableplanversion_and_more.py": [
                ("netbox_contract", "0052_remove_revenue_adjustment"),
            ],
        }

        for migration_name, expected in expected_dependencies.items():
            with self.subTest(migration=migration_name):
                self.assertEqual(get_dependencies(migration_name), expected)


if __name__ == "__main__":
    unittest.main()
