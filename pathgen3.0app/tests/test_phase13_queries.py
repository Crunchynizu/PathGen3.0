import time

from django.core.management import call_command
from django.db import connection
from django.test import SimpleTestCase, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.accounts.models import User
from apps.feedback.retrieval.index import load_index
from apps.feedback.retrieval.similarity import retrieve
from tests.factories import (
    make_classroom,
    make_membership,
    make_student_path,
    make_system_setting,
    make_user,
)


class Phase13DashboardQueryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_curriculum", verbosity=0)
        cls.admin = make_user(User.Role.ADMIN, username="query-admin")
        cls.teacher = make_user(User.Role.TEACHER, username="query-teacher")
        cls.student = make_user(User.Role.STUDENT, username="query-student")
        cls.classroom = make_classroom(
            code="QUERY-7", name="Query Review", teacher=cls.teacher
        )
        make_membership(
            classroom=cls.classroom,
            student=cls.student,
            added_by=cls.admin,
        )
        make_student_path(student=cls.student)
        make_system_setting(changed_by=cls.admin, study_access_enabled=True)

    def assert_query_limit(self, user, url, limit):
        self.client.force_login(user)
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertLess(
            len(queries),
            limit,
            f"{url} executed {len(queries)} queries; limit is below {limit}",
        )

    def test_admin_dashboard_uses_fewer_than_30_queries(self):
        self.assert_query_limit(
            self.admin,
            reverse("portal:admin_dashboard"),
            30,
        )

    def test_teacher_dashboard_uses_fewer_than_30_queries(self):
        self.assert_query_limit(
            self.teacher,
            reverse("portal:teacher_dashboard"),
            30,
        )

    def test_student_dashboard_uses_fewer_than_15_queries(self):
        self.assert_query_limit(
            self.student,
            reverse("account:student_dashboard"),
            15,
        )

    def test_student_progress_uses_fewer_than_30_queries(self):
        self.assert_query_limit(
            self.admin,
            reverse("portal:student_progress", args=[self.student.pk]),
            30,
        )


class Phase13RequiredIndexTests(TestCase):
    def constraints_for(self, table):
        with connection.cursor() as cursor:
            return connection.introspection.get_constraints(cursor, table)

    def assert_unique_columns(self, table, columns):
        constraints = self.constraints_for(table)
        self.assertTrue(
            any(
                details.get("unique") and details.get("columns") == columns
                for details in constraints.values()
            ),
            f"{table} has no unique constraint/index for {columns}",
        )

    def test_required_learning_session_indexes_exist(self):
        constraints = self.constraints_for("learning_session")
        self.assertEqual(
            constraints["learn_sess_student_type_idx"]["columns"],
            ["student_id", "session_type"],
        )
        self.assertEqual(
            constraints["learn_sess_status_idx"]["columns"],
            ["status"],
        )

    def test_required_unique_indexes_exist(self):
        self.assert_unique_columns("learning_response", ["session_item_id"])
        self.assert_unique_columns(
            "adaptive_skill_mastery", ["student_id", "skill_id"]
        )
        self.assert_unique_columns("adaptive_decision", ["session_id"])
        self.assert_unique_columns("feedback_session_feedback", ["session_id"])

    def test_audit_event_descending_created_at_index_exists(self):
        constraints = self.constraints_for("core_audit_event")
        details = constraints["core_audit_created_desc_idx"]
        self.assertEqual(details["columns"], ["created_at"])
        if details.get("orders"):
            self.assertEqual(details["orders"], ["DESC"])


class Phase13RetrievalLatencyTests(SimpleTestCase):
    def test_index_load_and_three_chunk_retrieval_stay_within_bounds(self):
        load_index.cache_clear()
        started = time.perf_counter()
        index = load_index()
        load_ms = (time.perf_counter() - started) * 1000

        query_embedding = index["chunks"][0]["embedding"]
        started = time.perf_counter()
        matches = retrieve(query_embedding, top_k=3, min_similarity=-1.0)
        retrieval_ms = (time.perf_counter() - started) * 1000

        self.assertEqual(len(matches), 3)
        self.assertLess(load_ms, 200, f"Index load took {load_ms:.2f}ms")
        self.assertLess(
            retrieval_ms,
            50,
            f"Three-chunk retrieval took {retrieval_ms:.2f}ms",
        )
