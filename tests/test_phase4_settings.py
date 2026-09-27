from django.test import Client, TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.core.models import AuditEvent, SystemSetting
from tests.factories import make_user


class SystemSettingTests(TestCase):
    def setUp(self):
        self.admin = make_user(User.Role.ADMIN)
        self.client.force_login(self.admin)

    def test_first_update_creates_singleton_with_revision_and_audit(self):
        response = self.client.post(
            reverse("portal:override"),
            {
                "expected_revision": 0,
                "setting_name": "study_access",
                "enabled": "true",
                "reason": "Open the study window",
            },
        )

        self.assertRedirects(response, reverse("portal:override"))
        setting = SystemSetting.objects.get(singleton_key=1)
        self.assertTrue(setting.study_access_enabled)
        self.assertFalse(setting.posttest_access_enabled)
        self.assertEqual(setting.revision, 1)
        event = AuditEvent.objects.get(action="system_setting.study_access.enabled")
        self.assertEqual(event.actor, self.admin)
        self.assertEqual(event.reason, "Open the study window")

    def test_stale_revision_returns_409_without_overwriting(self):
        SystemSetting.objects.create(
            singleton_key=1,
            study_access_enabled=True,
            posttest_access_enabled=False,
            changed_by=self.admin,
            revision=4,
        )

        response = self.client.post(
            reverse("portal:override"),
            {
                "expected_revision": 3,
                "setting_name": "study_access",
                "enabled": "false",
                "reason": "Stale close",
            },
        )

        self.assertEqual(response.status_code, 409)
        setting = SystemSetting.objects.get(singleton_key=1)
        self.assertTrue(setting.study_access_enabled)
        self.assertEqual(setting.revision, 4)
        self.assertFalse(AuditEvent.objects.filter(reason="Stale close").exists())

    def test_override_is_admin_only_and_csrf_protected(self):
        teacher = make_user(User.Role.TEACHER)
        self.client.force_login(teacher)
        self.assertEqual(self.client.get(reverse("portal:override")).status_code, 403)

        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.admin)
        response = csrf_client.post(
            reverse("portal:override"),
            {
                "expected_revision": 0,
                "setting_name": "study_access",
                "enabled": "true",
                "reason": "No token",
            },
        )
        self.assertEqual(response.status_code, 403)
