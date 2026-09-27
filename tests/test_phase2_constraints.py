from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TransactionTestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.adaptive.models import Decision, DecisionTargetSkill, MasteryEvent, SkillMastery
from apps.classrooms.models import Classroom, StudentMembership
from apps.core.models import SystemSetting
from apps.curriculum.models import (
    Lesson,
    LessonSkill,
    Question,
    QuestionChoice,
    QuestionSet,
    QuestionSetItem,
    Skill,
    Video,
)
from apps.feedback.models import SessionFeedback
from apps.learning.models import Session, SessionItem, StudentPath
from tests.factories import (
    make_choice,
    make_classroom,
    make_decision,
    make_feedback,
    make_lesson,
    make_lesson_skill,
    make_mastery_event,
    make_membership,
    make_question,
    make_question_set,
    make_question_set_item,
    make_response,
    make_session,
    make_session_item,
    make_skill,
    make_skill_mastery,
    make_student_path,
    make_system_setting,
    make_user,
    make_video,
)


class ConstraintTests(TransactionTestCase):
    reset_sequences = False

    def assert_integrity_rejected(self, operation):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                operation()

    def test_text_choice_checks_reject_unknown_values(self):
        user = make_user()
        classroom = make_classroom()
        question = make_question()
        question_set = make_question_set()
        path = make_student_path()
        session = make_session()

        invalid_updates = [
            (User.objects.filter(pk=user.pk), {"role": "unknown"}),
            (Classroom.objects.filter(pk=classroom.pk), {"status": "unknown"}),
            (Question.objects.filter(pk=question.pk), {"difficulty": "unknown"}),
            (Question.objects.filter(pk=question.pk), {"presentation_type": "unknown"}),
            (Question.objects.filter(pk=question.pk), {"cognitive_level": "unknown"}),
            (QuestionSet.objects.filter(pk=question_set.pk), {"set_type": "unknown"}),
            (StudentPath.objects.filter(pk=path.pk), {"status": "unknown"}),
            (StudentPath.objects.filter(pk=path.pk), {"current_stage": "unknown"}),
            (Session.objects.filter(pk=session.pk), {"session_type": "unknown"}),
            (Session.objects.filter(pk=session.pk), {"status": "unknown"}),
        ]
        for queryset, values in invalid_updates:
            with self.subTest(model=queryset.model._meta.label, values=values):
                self.assert_integrity_rejected(lambda q=queryset, v=values: q.update(**v))

        self.assert_integrity_rejected(
            lambda: Decision.objects.create(
                session=make_session(),
                action="unknown",
                reason_code="test",
                policy_version="Q-LEARNING-V1",
                input_snapshot_json={},
            )
        )
        self.assert_integrity_rejected(
            lambda: DecisionTargetSkill.objects.create(
                decision=make_decision(),
                skill=make_skill(),
                target_kind="unknown",
            )
        )
        self.assert_integrity_rejected(
            lambda: SessionFeedback.objects.create(
                session=make_session(),
                feedback_text="Fallback.",
                generation_status="unknown",
            )
        )

    def test_numeric_and_conditional_checks(self):
        skill = make_skill()
        lesson = make_lesson()
        lesson_skill = make_lesson_skill(lesson=lesson, skill=skill)
        video = make_video()
        question = make_question(skill=skill)
        choice = make_choice(question=question)
        question_set_item = make_question_set_item(question=question)
        session = make_session()
        session_item = make_session_item(session=session, question=make_question())
        mastery = make_skill_mastery()
        setting = make_system_setting()

        invalid_updates = [
            (Skill.objects.filter(pk=skill.pk), {"p_l0": Decimal("-0.1")}),
            (Skill.objects.filter(pk=skill.pk), {"p_t": Decimal("1.1")}),
            (Lesson.objects.filter(pk=lesson.pk), {"lesson_order": 0}),
            (Lesson.objects.filter(pk=lesson.pk), {"content_schema_version": 0}),
            (LessonSkill.objects.filter(pk=lesson_skill.pk), {"display_order": 3}),
            (Video.objects.filter(pk=video.pk), {"duration_seconds": 0}),
            (Video.objects.filter(pk=video.pk), {"transcript": ""}),
            (QuestionChoice.objects.filter(pk=choice.pk), {"label": "E"}),
            (QuestionChoice.objects.filter(pk=choice.pk), {"display_order": 5}),
            (QuestionSetItem.objects.filter(pk=question_set_item.pk), {"display_order": 0}),
            (Session.objects.filter(pk=session.pk), {"attempt_number": 0}),
            (SessionItem.objects.filter(pk=session_item.pk), {"display_order": 0}),
            (SkillMastery.objects.filter(pk=mastery.pk), {"p_known": Decimal("1.1")}),
            (SkillMastery.objects.filter(pk=mastery.pk), {"evidence_count": -1}),
            (SystemSetting.objects.filter(pk=setting.pk), {"singleton_key": 2}),
            (SystemSetting.objects.filter(pk=setting.pk), {"revision": -1}),
        ]
        for queryset, values in invalid_updates:
            with self.subTest(model=queryset.model._meta.label, values=values):
                self.assert_integrity_rejected(lambda q=queryset, v=values: q.update(**v))

        self.assert_integrity_rejected(
            lambda: Question.objects.filter(pk=question.pk).update(hint="Not allowed")
        )
        self.assert_integrity_rejected(
            lambda: MasteryEvent.objects.create(
                mastery=make_skill_mastery(),
                response=make_response(),
                p_before=Decimal("-0.1"),
                p_after_observation=None,
                p_after_learning=Decimal("0.5"),
                learning_transition_applied=False,
            )
        )

    def test_question_set_context_check(self):
        lesson = make_lesson()
        skill = make_skill()

        invalid_values = [
            {"set_type": QuestionSet.SetType.REGULAR, "lesson": None, "skill": None},
            {"set_type": QuestionSet.SetType.FOUNDATIONAL, "lesson": None, "skill": None},
            {"set_type": QuestionSet.SetType.PREPOST, "lesson": lesson, "skill": None},
            {"set_type": QuestionSet.SetType.ACTIVITY, "lesson": None, "skill": skill},
        ]
        for values in invalid_values:
            with self.subTest(values=values):
                self.assert_integrity_rejected(
                    lambda v=values: QuestionSet.objects.create(
                        code=f"INVALID-{v['set_type']}-{lesson.pk}",
                        name="Invalid set",
                        **v,
                    )
                )

    def test_partial_and_composite_uniqueness(self):
        classroom = make_classroom()
        student = make_user()
        actor = make_user(User.Role.ADMIN)
        membership = make_membership(
            classroom=classroom,
            student=student,
            added_by=actor,
        )
        self.assert_integrity_rejected(
            lambda: make_membership(
                classroom=classroom,
                student=student,
                added_by=actor,
            )
        )
        membership.left_at = timezone.now()
        membership.save(update_fields=["left_at"])
        make_membership(classroom=classroom, student=student, added_by=actor)

        lesson = make_lesson()
        make_lesson_skill(lesson=lesson, skill=make_skill(), display_order=1)
        self.assert_integrity_rejected(
            lambda: make_lesson_skill(lesson=lesson, skill=make_skill(), display_order=1)
        )

        question = make_question()
        make_choice(question=question, label="A", display_order=1, is_correct=True)
        self.assert_integrity_rejected(
            lambda: make_choice(question=question, label="A", display_order=2, is_correct=False)
        )
        self.assert_integrity_rejected(
            lambda: make_choice(question=question, label="B", display_order=1, is_correct=False)
        )
        self.assert_integrity_rejected(
            lambda: make_choice(question=question, label="B", display_order=2, is_correct=True)
        )

        question_set = make_question_set()
        make_question_set_item(
            question_set=question_set,
            question=question,
            display_order=1,
        )
        self.assert_integrity_rejected(
            lambda: make_question_set_item(
                question_set=question_set,
                question=question,
                display_order=2,
            )
        )
        self.assert_integrity_rejected(
            lambda: make_question_set_item(
                question_set=question_set,
                question=make_question(),
                display_order=1,
            )
        )

        session = make_session()
        session_question = make_question()
        make_session_item(session=session, question=session_question, display_order=1)
        self.assert_integrity_rejected(
            lambda: make_session_item(
                session=session,
                question=session_question,
                display_order=2,
            )
        )
        self.assert_integrity_rejected(
            lambda: make_session_item(
                session=session,
                question=make_question(),
                display_order=1,
            )
        )

    def test_one_to_one_and_mastery_uniqueness(self):
        student = make_user()
        skill = make_skill()
        make_skill_mastery(student=student, skill=skill)
        self.assert_integrity_rejected(
            lambda: make_skill_mastery(student=student, skill=skill)
        )

        response = make_response()
        make_mastery_event(response=response)
        self.assert_integrity_rejected(lambda: make_mastery_event(response=response))

        session = make_session()
        make_decision(session=session)
        self.assert_integrity_rejected(lambda: make_decision(session=session))

        feedback_session = make_session()
        make_feedback(session=feedback_session)
        self.assert_integrity_rejected(lambda: make_feedback(session=feedback_session))
