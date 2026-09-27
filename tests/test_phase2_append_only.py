from django.db import DatabaseError, connection, transaction
from django.test import TransactionTestCase

from tests.factories import make_audit_event, make_decision, make_mastery_event


class AppendOnlyTriggerTests(TransactionTestCase):
    reset_sequences = False

    def assert_statement_rejected(self, sql, params):
        with self.assertRaisesMessage(DatabaseError, "This table is append-only"):
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(sql, params)

    def test_mastery_event_rejects_update_and_delete(self):
        event = make_mastery_event()

        self.assert_statement_rejected(
            "UPDATE adaptive_mastery_event SET p_before = %s WHERE id = %s",
            ["0.200000", event.id],
        )
        self.assert_statement_rejected(
            "DELETE FROM adaptive_mastery_event WHERE id = %s",
            [event.id],
        )
        self.assertTrue(type(event).objects.filter(pk=event.pk).exists())

    def test_adaptive_decision_rejects_update_and_delete(self):
        decision = make_decision()

        self.assert_statement_rejected(
            "UPDATE adaptive_decision SET reason_code = %s WHERE id = %s",
            ["changed", decision.id],
        )
        self.assert_statement_rejected(
            "DELETE FROM adaptive_decision WHERE id = %s",
            [decision.id],
        )
        self.assertTrue(type(decision).objects.filter(pk=decision.pk).exists())

    def test_audit_event_rejects_update_and_delete(self):
        event = make_audit_event()

        self.assert_statement_rejected(
            "UPDATE core_audit_event SET action = %s WHERE id = %s",
            ["changed", event.id],
        )
        self.assert_statement_rejected(
            "DELETE FROM core_audit_event WHERE id = %s",
            [event.id],
        )
        self.assertTrue(type(event).objects.filter(pk=event.pk).exists())
