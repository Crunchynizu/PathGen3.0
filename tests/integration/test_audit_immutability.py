from django.db import DatabaseError, connection, transaction
from django.test import TransactionTestCase

from tests.factories import make_audit_event, make_decision, make_mastery_event
from tests.integration._helpers import ProviderGuardMixin


class AuditImmutabilityAcceptanceTests(ProviderGuardMixin, TransactionTestCase):
    reset_sequences = False

    def assert_rejected_without_count_change(
        self,
        *,
        model,
        update_sql,
        update_params,
        delete_sql,
        delete_params,
    ):
        original_count = model.objects.count()
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(update_sql, update_params)
        self.assertEqual(model.objects.count(), original_count)

        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(delete_sql, delete_params)
        self.assertEqual(model.objects.count(), original_count)

    def test_core_audit_event_rejects_raw_update_and_delete(self):
        event = make_audit_event()
        self.assert_rejected_without_count_change(
            model=type(event),
            update_sql=(
                "UPDATE core_audit_event SET action = %s WHERE id = %s"
            ),
            update_params=["tampered", event.pk],
            delete_sql="DELETE FROM core_audit_event WHERE id = %s",
            delete_params=[event.pk],
        )

    def test_adaptive_mastery_event_rejects_raw_update_and_delete(self):
        event = make_mastery_event()
        self.assert_rejected_without_count_change(
            model=type(event),
            update_sql=(
                "UPDATE adaptive_mastery_event SET p_before = %s WHERE id = %s"
            ),
            update_params=["0.200000", event.pk],
            delete_sql="DELETE FROM adaptive_mastery_event WHERE id = %s",
            delete_params=[event.pk],
        )

    def test_adaptive_decision_rejects_raw_update_and_delete(self):
        decision = make_decision()
        self.assert_rejected_without_count_change(
            model=type(decision),
            update_sql=(
                "UPDATE adaptive_decision SET reason_code = %s WHERE id = %s"
            ),
            update_params=["tampered", decision.pk],
            delete_sql="DELETE FROM adaptive_decision WHERE id = %s",
            delete_params=[decision.pk],
        )
