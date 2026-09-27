from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from apps.accounts.models import User
from apps.core.models import AuditEvent


class BootstrapAdminCommandTests(TestCase):
    def test_command_creates_admin_and_audit_event(self):
        output = StringIO()
        with patch.dict(
            "os.environ",
            {"PATHGEN_BOOTSTRAP_ADMIN_PASSWORD": "Bootstrap!Password934"},
        ):
            call_command(
                "bootstrap_admin",
                username="initial-admin",
                email="admin@example.test",
                noinput=True,
                stdout=output,
            )

        admin = User.objects.get(username="initial-admin")
        self.assertEqual(admin.role, User.Role.ADMIN)
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)
        self.assertTrue(admin.check_password("Bootstrap!Password934"))
        self.assertTrue(
            AuditEvent.objects.filter(
                action="account.admin_bootstrapped", target_id=admin.pk
            ).exists()
        )
        self.assertIn("created", output.getvalue())
