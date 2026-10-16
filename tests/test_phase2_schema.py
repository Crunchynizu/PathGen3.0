import uuid

from django.db import connection, models
from django.test import TransactionTestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.adaptive.models import Decision, MasteryEvent, SkillMastery
from apps.classrooms.models import Classroom, StudentMembership
from apps.core.models import AuditEvent
from apps.curriculum.models import (
    Lesson,
    Question,
    QuestionChoice,
    QuestionSet,
    Skill,
    Video,
)
from apps.feedback.models import SessionFeedback
from apps.learning.models import Response, Session, SessionItem
from tests.factories import make_audit_event


DOMAIN_TABLES = {
    "accounts_user",
    "classrooms_classroom",
    "classrooms_student_membership",
    "curriculum_skill",
    "curriculum_lesson",
    "curriculum_lesson_skill",
    "curriculum_video",
    "curriculum_question",
    "curriculum_question_choice",
    "curriculum_question_set",
    "curriculum_question_set_item",
    "learning_student_path",
    "learning_session",
    "learning_session_item",
    "learning_response",
    "adaptive_skill_mastery",
    "adaptive_mastery_event",
    "adaptive_decision",
    "adaptive_decision_target_skill",
    "feedback_session_feedback",
    "core_system_setting",
    "core_audit_event",
}

EXPECTED_COLUMNS = {
    "accounts_user": {
        "id", "username", "email", "first_name", "last_name", "role",
        "password", "is_active", "deactivated_at", "deactivated_by_id",
        "deactivation_reason", "anonymized_at", "is_staff", "is_superuser",
        "created_at", "updated_at",
    },
    "classrooms_classroom": {
        "id", "code", "name", "teacher_id", "status", "archived_at",
        "archived_by_id", "archive_reason", "created_at", "updated_at",
    },
    "classrooms_student_membership": {
        "id", "classroom_id", "student_id", "joined_at", "left_at",
        "added_by_id", "removed_by_id",
    },
    "curriculum_skill": {
        "id", "code", "name", "description", "p_l0", "p_t", "p_g", "p_s",
        "created_at", "updated_at",
    },
    "curriculum_lesson": {
        "id", "code", "slug", "lesson_order", "unit_number", "part_number",
        "unit_title", "title", "summary", "content_json", "content_schema_version",
        "is_published", "created_at", "updated_at",
    },
    "curriculum_lesson_skill": {"lesson_id", "skill_id", "display_order"},
    "curriculum_video": {
        "id", "code", "title", "youtube_video_id", "duration_seconds",
        "transcript", "created_at", "updated_at",
    },
    "curriculum_question": {
        "id", "code", "skill_id", "prompt", "difficulty", "presentation_type",
        "cognitive_level", "solution_steps_json", "explanation", "hint",
        "feedback_correct", "feedback_incorrect", "image_asset", "image_alt",
        "visual_component", "visual_config_json", "video_id",
        "video_pause_seconds", "is_published", "created_at", "updated_at",
    },
    "curriculum_question_choice": {
        "id", "question_id", "label", "text", "is_correct",
        "misconception_code", "display_order",
    },
    "curriculum_question_set": {
        "id", "code", "name", "set_type", "lesson_id", "skill_id",
        "is_published", "created_at", "updated_at",
    },
    "curriculum_question_set_item": {
        "question_set_id", "question_id", "display_order",
    },
    "learning_student_path": {
        "student_id", "status", "current_lesson_id", "current_stage",
        "created_at", "updated_at",
    },
    "learning_session": {
        "id", "student_id", "session_type", "lesson_id", "status",
        "attempt_number", "voided_at", "voided_by_id", "void_reason",
        "started_at", "submitted_at", "completed_at", "created_at", "updated_at",
    },
    "learning_session_item": {
        "id", "session_id", "question_id", "display_order",
    },
    "learning_response": {
        "id", "session_item_id", "selected_choice_id", "hint_used", "answered_at",
    },
    "adaptive_skill_mastery": {
        "id", "student_id", "skill_id", "p_known", "evidence_count",
        "created_at", "updated_at",
    },
    "adaptive_mastery_event": {
        "id", "mastery_id", "response_id", "p_before", "p_after_observation",
        "p_after_learning", "learning_transition_applied", "created_at",
    },
    "adaptive_decision": {
        "id", "session_id", "action", "reason_code", "policy_version",
        "input_snapshot_json", "created_at",
    },
    "adaptive_decision_target_skill": {
        "decision_id", "skill_id", "target_kind",
    },
    "feedback_session_feedback": {
        "id", "session_id", "feedback_text", "generation_status", "model_name",
        "created_at",
    },
    "core_system_setting": {
        "singleton_key", "study_access_enabled", "posttest_access_enabled",
        "changed_by_id", "changed_at", "revision",
    },
    "core_audit_event": {
        "id", "actor_id", "action", "target_type", "target_id",
        "target_snapshot_json", "reason", "metadata_json", "created_at",
    },
}


class SchemaContractTests(TransactionTestCase):
    def test_exactly_22_domain_tables_exist(self):
        tables = set(connection.introspection.table_names())
        domain_tables = {
            table
            for table in tables
            if table.startswith(
                (
                    "accounts_",
                    "classrooms_",
                    "curriculum_",
                    "learning_",
                    "adaptive_",
                    "feedback_",
                    "core_",
                )
            )
        }

        self.assertEqual(domain_tables, DOMAIN_TABLES)
        self.assertEqual(len(domain_tables), 22)

    def test_domain_table_columns_match_documented_schema(self):
        with connection.cursor() as cursor:
            for table, expected_columns in EXPECTED_COLUMNS.items():
                with self.subTest(table=table):
                    description = connection.introspection.get_table_description(
                        cursor,
                        table,
                    )
                    actual_columns = {column.name for column in description}
                    self.assertEqual(actual_columns, expected_columns)

    def test_uuid_primary_keys(self):
        uuid_models = [
            User,
            Classroom,
            StudentMembership,
            Skill,
            Lesson,
            Video,
            Question,
            QuestionChoice,
            QuestionSet,
            Session,
            SessionItem,
            Response,
            SkillMastery,
            MasteryEvent,
            Decision,
            SessionFeedback,
            AuditEvent,
        ]
        for model in uuid_models:
            with self.subTest(model=model._meta.label):
                self.assertIsInstance(model._meta.pk, models.UUIDField)
                self.assertEqual(model._meta.pk.default, uuid.uuid4)

    def test_required_database_indexes_exist(self):
        with connection.cursor() as cursor:
            membership = connection.introspection.get_constraints(
                cursor,
                "classrooms_student_membership",
            )
            choice = connection.introspection.get_constraints(
                cursor,
                "curriculum_question_choice",
            )

        self.assertTrue(membership["unique_active_classroom_membership"]["unique"])
        self.assertTrue(choice["unique_correct_choice_per_question"]["unique"])
        self.assertTrue(any(value["index"] for value in membership.values()))

    def test_timestamps_are_timezone_aware(self):
        event = make_audit_event()

        self.assertTrue(timezone.is_aware(event.created_at))

    def test_protected_foreign_keys(self):
        protected_fields = [
            Question._meta.get_field("skill"),
            Session._meta.get_field("student"),
            SessionItem._meta.get_field("session"),
            SessionItem._meta.get_field("question"),
            Response._meta.get_field("session_item"),
            Response._meta.get_field("selected_choice"),
            SkillMastery._meta.get_field("student"),
            SkillMastery._meta.get_field("skill"),
            MasteryEvent._meta.get_field("mastery"),
            MasteryEvent._meta.get_field("response"),
            Decision._meta.get_field("session"),
            SessionFeedback._meta.get_field("session"),
        ]

        for field in protected_fields:
            with self.subTest(field=f"{field.model._meta.label}.{field.name}"):
                self.assertIs(field.remote_field.on_delete, models.PROTECT)
