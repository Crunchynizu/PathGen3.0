"""Local route, access, rendering, and template-reference smoke tests."""

import re
import uuid
from html.parser import HTMLParser
from pathlib import Path
from types import SimpleNamespace

from django.conf import settings
from django.test import Client
from django.template.loader import get_template
from django.urls import URLResolver, get_resolver, reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.adaptive.models import MasteryEvent
from apps.core.models import AuditEvent, SystemSetting
from apps.curriculum.models import Lesson, Question, QuestionSet, Video
from apps.learning.models import Response, Session, StudentPath
from tests.factories import make_classroom, make_membership, make_user
from tests.phase6_helpers import Phase6SeededTestCase


class RenderedAccessibility(HTMLParser):
    def __init__(self):
        super().__init__()
        self.label_for = set()
        self.label_depth = 0
        self.inputs = []
        self.canvases = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "label":
            self.label_depth += 1
            if attrs.get("for"):
                self.label_for.add(attrs["for"])
        elif tag == "input":
            self.inputs.append((attrs, bool(self.label_depth)))
        elif tag == "canvas":
            self.canvases.append(attrs)

    def handle_endtag(self, tag):
        if tag == "label":
            self.label_depth -= 1


class ButtonAudit(HTMLParser):
    ACTION_HOOKS = {
        "data-access-switch", "data-dialog-close", "data-dialog-confirm",
        "data-dialog-open", "data-drawer-close", "data-drawer-open",
        "data-hint-open", "data-lesson-next", "data-lesson-prev",
        "data-reveal-question",
    }

    def __init__(self):
        super().__init__()
        self.form_depth = 0
        self.buttons = []

    def handle_starttag(self, tag, attrs):
        if tag == "form":
            self.form_depth += 1
        elif tag == "button":
            self.buttons.append((dict(attrs), bool(self.form_depth)))

    def handle_endtag(self, tag):
        if tag == "form":
            self.form_depth -= 1


def all_route_names(patterns, namespace=""):
    for pattern in patterns:
        if isinstance(pattern, URLResolver):
            child_namespace = f"{namespace}{pattern.namespace}:" if pattern.namespace else namespace
            yield from all_route_names(pattern.url_patterns, child_namespace)
        elif pattern.name:
            yield f"{namespace}{pattern.name}"


class QAWalkthroughTests(Phase6SeededTestCase):
    PASSWORD = "Qa-walkthrough-password-934!"
    PUBLIC = {"home", "health", "account:login"}
    ALL_AUTH = {
        "account:logout", "account:my_account", "account:update_name",
        "account:update_password",
    }
    ADMIN = {
        "account:admin_dashboard", "portal:admin_dashboard", "portal:user_management",
        "portal:create_user", "portal:update_user", "portal:deactivate_user",
        "portal:reactivate_user", "portal:delete_user", "portal:class_management",
        "portal:create_class", "portal:update_class", "portal:assign_teacher",
        "portal:add_student", "portal:remove_student", "portal:archive_class",
        "portal:reactivate_class", "portal:delete_class", "portal:override",
        "portal:audit_logs",
    }
    TEACHER = {
        "account:teacher_dashboard", "portal:teacher_dashboard", "portal:my_classes",
        "portal:class_detail",
    }
    STUDENT = {
        "account:student_dashboard", "account:my_lesson", "learning:lesson",
        "learning:complete_lesson", "learning:pretest_overview",
        "learning:activity_overview", "learning:posttest_overview",
        "learning:exercise_overview", "learning:assessment_session",
        "learning:submit_response", "learning:assessment_result",
        "learning:transcript",
    }
    ADMIN_TEACHER = {
        "curriculum:content", "curriculum:view_lessons", "curriculum:view_questions",
        "portal:student_progress", "portal:content",
    }
    POST_ONLY = {
        "account:logout", "account:update_name", "account:update_password",
        "portal:create_user", "portal:update_user", "portal:deactivate_user",
        "portal:reactivate_user", "portal:delete_user", "portal:create_class",
        "portal:update_class", "portal:assign_teacher", "portal:add_student",
        "portal:remove_student", "portal:archive_class", "portal:reactivate_class",
        "portal:delete_class", "learning:complete_lesson", "learning:submit_response",
    }

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.teacher = make_user(User.Role.TEACHER)
        for user in (cls.admin, cls.teacher, cls.student):
            user.set_password(cls.PASSWORD)
            user.save(update_fields=["password"])
        cls.classroom = make_classroom(teacher=cls.teacher)
        cls.membership = make_membership(cls.classroom, cls.student, cls.admin)
        cls.first_lesson = Lesson.objects.get(lesson_order=1)
        cls.video = Video.objects.order_by("code").first()

    def route_kwargs(self, name, *, active_session=None, completed_session=None):
        values = {
            "user_id": self.student.pk,
            "classroom_id": self.classroom.pk,
            "membership_id": self.membership.pk,
            "student_id": self.student.pk,
            "slug": self.first_lesson.slug,
            "session_type": Session.SessionType.REGULAR,
            "session_id": (
                completed_session.pk if name == "learning:assessment_result" else active_session.pk
            ) if active_session else None,
            "video_code": self.video.code,
        }
        return {key: value for key, value in values.items() if value is not None}

    def route_url(self, name, **extra):
        kwargs = self.route_kwargs(name, **extra)
        route_params = {
            "portal:update_user": ("user_id",),
            "portal:deactivate_user": ("user_id",),
            "portal:reactivate_user": ("user_id",),
            "portal:delete_user": ("user_id",),
            "portal:update_class": ("classroom_id",),
            "portal:assign_teacher": ("classroom_id",),
            "portal:add_student": ("classroom_id",),
            "portal:archive_class": ("classroom_id",),
            "portal:reactivate_class": ("classroom_id",),
            "portal:delete_class": ("classroom_id",),
            "portal:class_detail": ("classroom_id",),
            "portal:remove_student": ("membership_id",),
            "portal:student_progress": ("student_id",),
            "learning:lesson": ("slug",),
            "learning:complete_lesson": ("slug",),
            "learning:exercise_overview": ("session_type", "slug"),
            "learning:assessment_session": ("session_id",),
            "learning:submit_response": ("session_id",),
            "learning:assessment_result": ("session_id",),
            "learning:transcript": ("video_code",),
        }.get(name, ())
        return reverse(name, kwargs={key: kwargs[key] for key in route_params})

    def assert_accessible_html(self, url, response):
        if response.streaming or "text/html" not in response.get("Content-Type", ""):
            return
        html = response.content.decode()
        parsed = RenderedAccessibility()
        parsed.feed(html)
        for attrs, wrapped in parsed.inputs:
            if attrs.get("type") == "hidden":
                continue
            self.assertTrue(
                wrapped or attrs.get("id") in parsed.label_for or attrs.get("aria-label")
                or attrs.get("aria-labelledby"),
                f"{url}: input {attrs.get('name')} has no label",
            )
        for attrs in parsed.canvases:
            self.assertTrue(attrs.get("aria-label"), f"{url}: canvas lacks aria-label")
        if url in (reverse("portal:admin_dashboard"), reverse("portal:teacher_dashboard")):
            chart_articles = [
                article for article in re.findall(r"<article\b.*?</article>", html, re.S)
                if "View data table" in article
            ]
            self.assertEqual(len(chart_articles), 5 if "admin" in url else 4, url)
            for article in chart_articles:
                self.assertIn("<table", article, f"{url}: chart has no paired table")

    def test_every_named_route_and_role_scope(self):
        role_routes = {
            User.Role.ADMIN: self.ADMIN | self.ADMIN_TEACHER | {"portal:class_detail"},
            User.Role.TEACHER: self.TEACHER | self.ADMIN_TEACHER,
            User.Role.STUDENT: self.STUDENT,
        }
        expected = self.PUBLIC | self.ALL_AUTH | self.ADMIN | self.TEACHER | self.STUDENT | self.ADMIN_TEACHER
        self.assertEqual(set(all_route_names(get_resolver().url_patterns)), expected)

        self.set_path(status=StudentPath.Status.LEARNING, stage=StudentPath.Stage.LESSON, lesson=self.first_lesson)
        prepost = self.question_set(QuestionSet.SetType.PREPOST)
        active = self.make_session_from_set(session_type=Session.SessionType.PRETEST, question_set=prepost, limit=1)
        activity = self.question_set(QuestionSet.SetType.ACTIVITY)
        completed = self.make_session_from_set(session_type=Session.SessionType.ACTIVITY, question_set=activity, limit=1)
        now = timezone.now()
        completed.status = Session.Status.COMPLETED
        completed.started_at = now
        completed.submitted_at = now
        completed.completed_at = now
        completed.save(update_fields=["status", "started_at", "submitted_at", "completed_at"])

        users = {User.Role.ADMIN: self.admin, User.Role.TEACHER: self.teacher, User.Role.STUDENT: self.student}
        for role, user in users.items():
            self.assertTrue(self.client.login(username=user.username, password=self.PASSWORD))
            for name in sorted(expected):
                url = self.route_url(name, active_session=active, completed_session=completed)
                allowed = name in self.PUBLIC | self.ALL_AUTH | role_routes[role]
                with self.subTest(role=role, url=url, route=name):
                    response = self.client.get(url, follow=allowed and name not in self.POST_ONLY)
                    if not allowed:
                        self.assertIn(response.status_code, (403, 404), f"{url}: expected denial, got {response.status_code}")
                    elif name in self.POST_ONLY:
                        self.assertEqual(response.status_code, 405, f"{url}: expected POST-only 405")
                    else:
                        self.assertEqual(response.status_code, 200, f"{url}: expected page 200")
                        self.assert_accessible_html(url, response)
            self.client.logout()

    def test_login_logout_csrf_and_cookie_policy(self):
        self.assertEqual(self.client.get(reverse("health")).status_code, 200)
        wrong = self.client.post(reverse("account:login"), {"username": "nonexistent-qa", "password": "wrong"})
        self.assertEqual(wrong.status_code, 200)
        self.assertContains(wrong, "Incorrect username or password. Please try again.")
        self.assertContains(wrong, 'role="alert"')
        self.assertNotContains(wrong, "No account exists")
        known_wrong = self.client.post(reverse("account:login"), {
            "username": self.admin.username, "password": "wrong",
        })
        self.assertEqual(known_wrong.status_code, 200)
        self.assertContains(known_wrong, "Incorrect username or password. Please try again.")
        self.assertEqual(
            list(wrong.context["form"].non_field_errors()),
            list(known_wrong.context["form"].non_field_errors()),
        )
        login_response = self.client.post(reverse("account:login"), {
            "username": self.admin.username, "password": self.PASSWORD,
        })
        self.assertEqual(login_response.status_code, 302)
        session_cookie = login_response.cookies[settings.SESSION_COOKIE_NAME]
        self.assertEqual(bool(session_cookie["httponly"]), settings.SESSION_COOKIE_HTTPONLY)
        self.assertEqual(bool(session_cookie["secure"]), settings.SESSION_COOKIE_SECURE)
        self.assertEqual(session_cookie["samesite"], settings.SESSION_COOKIE_SAMESITE)
        self.assertEqual(bool(login_response.cookies[settings.CSRF_COOKIE_NAME]["secure"]), settings.CSRF_COOKIE_SECURE)
        self.assertIn("django.middleware.csrf.CsrfViewMiddleware", settings.MIDDLEWARE)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.admin)
        csrf_response = csrf_client.post(reverse("portal:override"), {
            "expected_revision": self.setting.revision, "setting_name": "study_access",
            "enabled": "true", "reason": "QA without token",
        })
        self.assertEqual(csrf_response.status_code, 403)
        self.assertEqual(self.client.get(reverse("account:logout")).status_code, 405)
        self.assertEqual(self.client.post(reverse("account:logout")).status_code, 302)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_study_and_posttest_access_states(self):
        self.setting.study_access_enabled = False
        self.setting.save(update_fields=["study_access_enabled"])
        self.client.force_login(self.student)
        blocked = self.client.post(reverse("learning:pretest_overview"))
        self.assertEqual(blocked.status_code, 200)
        self.assertContains(blocked, "Student Study Access is currently closed")
        self.assertFalse(Session.objects.filter(student=self.student).exists())
        self.client.logout()
        for user, dashboard in ((self.admin, "portal:admin_dashboard"), (self.teacher, "portal:teacher_dashboard")):
            self.client.force_login(user)
            self.assertEqual(self.client.get(reverse(dashboard)).status_code, 200)
            self.client.logout()

        self.setting.study_access_enabled = True
        self.setting.save(update_fields=["study_access_enabled"])
        self.set_path(status=StudentPath.Status.POSTTEST_READY, stage=StudentPath.Stage.POSTTEST, lesson=self.lesson(3))
        self.client.force_login(self.student)
        locked = self.client.get(reverse("learning:posttest_overview"))
        self.assertEqual(locked.status_code, 200)
        self.assertContains(locked, "Post-test locked")
        self.assertContains(locked, "Post-test Access")

    def test_override_revision_and_audit(self):
        self.client.force_login(self.admin)
        initial = self.setting.revision
        url = reverse("portal:override")
        accepted = self.client.post(url, {
            "expected_revision": initial, "setting_name": "study_access",
            "enabled": "false", "reason": "QA closes access",
        })
        self.assertRedirects(accepted, url)
        self.setting.refresh_from_db()
        self.assertFalse(self.setting.study_access_enabled)
        self.assertEqual(self.setting.revision, initial + 1)
        self.assertEqual(AuditEvent.objects.filter(reason="QA closes access").count(), 1)
        stale = self.client.post(url, {
            "expected_revision": initial, "setting_name": "study_access",
            "enabled": "true", "reason": "QA stale update",
        })
        self.assertEqual(stale.status_code, 409)
        self.setting.refresh_from_db()
        self.assertFalse(self.setting.study_access_enabled)
        self.assertFalse(AuditEvent.objects.filter(reason="QA stale update").exists())

    def test_resume_and_duplicate_response_post(self):
        self.client.force_login(self.student)
        overview = reverse("learning:pretest_overview")
        first = self.client.post(overview)
        second = self.client.post(overview)
        self.assertEqual(first.status_code, 302)
        self.assertEqual(first["Location"], second["Location"])
        session = Session.objects.get(student=self.student, session_type=Session.SessionType.PRETEST)
        self.assertEqual(Session.objects.filter(student=self.student).count(), 1)
        item = session.items.order_by("display_order").first()
        choice = item.question.choices.order_by("display_order").first()
        payload = {"session_item": str(item.pk), "choice": str(choice.pk)}
        submit_url = reverse("learning:submit_response", args=[session.pk])
        self.assertEqual(self.client.post(submit_url, payload).status_code, 302)
        self.assertEqual(self.client.post(submit_url, payload).status_code, 302)
        self.assertEqual(Response.objects.filter(session_item=item).count(), 1)
        self.assertEqual(MasteryEvent.objects.filter(response__session_item=item).count(), 1)

    def test_posttest_response_creates_no_bkt_event(self):
        self.set_path(status=StudentPath.Status.POSTTEST_READY, stage=StudentPath.Stage.POSTTEST, lesson=self.lesson(3))
        self.setting.posttest_access_enabled = True
        self.setting.save(update_fields=["posttest_access_enabled"])
        self.client.force_login(self.student)
        started = self.client.post(reverse("learning:posttest_overview"))
        self.assertEqual(started.status_code, 302)
        session = Session.objects.get(student=self.student, session_type=Session.SessionType.POSTTEST)
        item = session.items.order_by("display_order").first()
        choice = item.question.choices.order_by("display_order").first()
        submitted = self.client.post(reverse("learning:submit_response", args=[session.pk]), {
            "session_item": str(item.pk), "choice": str(choice.pk),
        })
        self.assertEqual(submitted.status_code, 302)
        self.assertEqual(Response.objects.filter(session_item=item).count(), 1)
        self.assertEqual(MasteryEvent.objects.count(), 0)

    def test_every_reached_lesson_and_video_transcript_renders(self):
        self.set_path(
            status=StudentPath.Status.ACTIVITY_READY,
            stage=StudentPath.Stage.ACTIVITY,
            lesson=self.lesson(3),
        )
        self.client.force_login(self.student)
        for lesson in Lesson.objects.filter(is_published=True).order_by("lesson_order"):
            url = reverse("learning:lesson", args=[lesson.slug])
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200, url)
                self.assert_accessible_html(url, response)
        for video in Video.objects.order_by("code"):
            url = reverse("learning:transcript", args=[video.code])
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200, url)

    def test_static_template_references_and_controls(self):
        templates_root = Path(settings.BASE_DIR) / "templates"
        vendor = (Path(settings.BASE_DIR) / "static/vendor/lucide/lucide.min.js").read_text(encoding="utf-8")
        sidebar_names = set()
        action_names = set()
        static_paths = set()
        lucide_names = set()
        missing = []
        button_count = 0
        for path in templates_root.rglob("*.html"):
            source = path.read_text(encoding="utf-8")
            url_names = re.findall(r"{%\s*url\s+['\"]([^'\"]+)['\"]", source)
            if path.name == "sidebar.html":
                sidebar_names.update(url_names)
            action_names.update(re.findall(r"<form\b[^>]*\baction=\"{%\s*url\s+['\"]([^'\"]+)['\"]", source, re.S))
            for name in url_names:
                with self.subTest(template=str(path), url_name=name):
                    sample = SimpleNamespace(pk=uuid.uuid4())
                    self.route_url(name, active_session=sample, completed_session=sample)
            for name in re.findall(r"{%\s*(?:extends|include)\s+['\"]([^'\"]+)['\"]", source):
                with self.subTest(template=str(path), referenced_template=name):
                    get_template(name)
            static_paths.update(re.findall(r"{%\s*static\s+['\"]([^'\"]+)['\"]\s*%}", source))
            lucide_names.update(re.findall(r"data-lucide=\"([^\"]+)\"", source))
            self.assertNotIn('href="#"', source, str(path))
            parsed = ButtonAudit()
            parsed.feed(source)
            for attrs, inside_form in parsed.buttons:
                button_count += 1
                kind = attrs.get("type")
                if not kind:
                    missing.append(f"{path}: button without type")
                elif kind == "submit" and not (inside_form or attrs.get("form")):
                    missing.append(f"{path}: submit button outside form")
                elif kind == "button" and not ButtonAudit.ACTION_HOOKS.intersection(attrs):
                    missing.append(f"{path}: button without JS hook")
        for static_path in static_paths:
            with self.subTest(static=static_path):
                self.assertTrue((Path(settings.BASE_DIR) / "static" / static_path).is_file())
        for name in lucide_names:
            pascal = "".join(part.capitalize() for part in name.split("-"))
            with self.subTest(lucide=name):
                self.assertRegex(vendor, rf"\b{pascal}:[A-Za-z_$]")
        self.assertTrue(sidebar_names)
        self.assertTrue(action_names)
        self.assertTrue(static_paths)
        self.assertTrue(lucide_names)
        self.assertGreater(button_count, 0)
        self.assertEqual(missing, [])

    def test_every_seeded_figure_asset_exists(self):
        paths = {
            block["image_asset"]
            for lesson in Lesson.objects.filter(is_published=True)
            for block in lesson.content_json.get("blocks", [])
            if block.get("image_asset")
        }
        paths.update(
            Question.objects.filter(image_asset__isnull=False)
            .exclude(image_asset="")
            .values_list("image_asset", flat=True)
        )
        self.assertEqual(len(paths), 26)
        static_root = (Path(settings.BASE_DIR) / "static").resolve()
        for asset in sorted(paths):
            with self.subTest(asset=asset):
                target = (static_root / asset).resolve()
                self.assertTrue(target.is_relative_to(static_root), asset)
                self.assertTrue(target.is_file(), asset)

    def test_modal_accessibility_and_destructive_styling(self):
        modals_root = Path(settings.BASE_DIR) / "templates/modals"
        modals = sorted(modals_root.rglob("*.html"))
        self.assertEqual(len(modals), 24)
        destructive = {
            "deactivate_user_confirm.html", "delete_user_confirm.html",
            "archive_class_confirm.html", "delete_class_confirm.html",
            "remove_student_class_confirm.html", "close_study_access_confirm.html",
            "lock_posttest_confirm.html",
        }
        for path in modals:
            with self.subTest(modal=str(path)):
                source = path.read_text(encoding="utf-8")
                self.assertIn("aria-labelledby=", source)
                self.assertRegex(source, r"(?i)\bCancel\b")
                if path.name in destructive:
                    self.assertIn("var(--color-danger)", source)
