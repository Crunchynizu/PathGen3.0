from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

from tests.test_phase2_schema import DOMAIN_TABLES


class MigrationRoundTripTests(TransactionTestCase):
    reset_sequences = False

    def test_phase2_migrations_roll_back_and_reapply(self):
        executor = MigrationExecutor(connection)
        latest_targets = executor.loader.graph.leaf_nodes()
        phase2_apps = {
            "adaptive",
            "classrooms",
            "core",
            "curriculum",
            "feedback",
            "learning",
        }
        phase1_targets = [
            target
            for target in latest_targets
            if target[0] not in phase2_apps and target[0] != "accounts"
        ]
        phase1_targets.extend((app_label, None) for app_label in phase2_apps)
        phase1_targets.append(("accounts", "0001_initial"))

        executor.migrate(phase1_targets)
        rolled_back_tables = set(connection.introspection.table_names())
        self.assertEqual(rolled_back_tables & DOMAIN_TABLES, {"accounts_user"})

        executor = MigrationExecutor(connection)
        executor.migrate(latest_targets)
        restored_tables = set(connection.introspection.table_names())
        self.assertEqual(restored_tables & DOMAIN_TABLES, DOMAIN_TABLES)
