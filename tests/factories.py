import itertools
import uuid
from decimal import Decimal

from django.utils import timezone

from apps.accounts.models import User
from apps.adaptive.models import (
    Decision,
    DecisionTargetSkill,
    MasteryEvent,
    SkillMastery,
)
from apps.classrooms.models import Classroom, StudentMembership
from apps.core.models import AuditEvent, SystemSetting
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
from apps.learning.models import Response, Session, SessionItem, StudentPath


_sequence = itertools.count(1)


def next_value(prefix):
    return f"{prefix}-{next(_sequence)}"


def make_user(role=User.Role.STUDENT, **overrides):
    values = {
        "username": next_value("user"),
        "role": role,
        "first_name": "Test",
        "last_name": "User",
    }
    values.update(overrides)
    user = User(**values)
    user.set_unusable_password()
    user.save()
    return user


def make_classroom(**overrides):
    values = {
        "code": next_value("CLASS"),
        "name": "Test Classroom",
        "status": Classroom.Status.ACTIVE,
    }
    values.update(overrides)
    return Classroom.objects.create(**values)


def make_membership(classroom=None, student=None, added_by=None, **overrides):
    values = {
        "classroom": classroom or make_classroom(),
        "student": student or make_user(),
        "added_by": added_by or make_user(User.Role.ADMIN),
    }
    values.update(overrides)
    return StudentMembership.objects.create(**values)


def make_skill(**overrides):
    values = {
        "code": next_value("S"),
        "name": "Integer Skill",
        "description": "A test skill.",
        "p_l0": Decimal("0.300000"),
        "p_t": Decimal("0.090000"),
        "p_g": Decimal("0.100000"),
        "p_s": Decimal("0.090000"),
    }
    values.update(overrides)
    return Skill.objects.create(**values)


def make_lesson(**overrides):
    sequence = next(_sequence)
    values = {
        "code": f"L-{sequence}",
        "slug": f"lesson-{sequence}",
        "lesson_order": sequence,
        "unit_number": sequence,
        "unit_title": "Integer Lesson",
        "title": "Integer Lesson",
        "summary": "A test lesson.",
        "content_json": [],
        "content_schema_version": 1,
        "is_published": False,
    }
    values.update(overrides)
    return Lesson.objects.create(**values)


def make_lesson_skill(lesson=None, skill=None, **overrides):
    values = {
        "lesson": lesson or make_lesson(),
        "skill": skill or make_skill(),
        "display_order": 1,
    }
    values.update(overrides)
    return LessonSkill.objects.create(**values)


def make_video(**overrides):
    values = {
        "code": next_value("VID"),
        "title": "Integer Video",
        "youtube_video_id": next_value("youtube"),
        "duration_seconds": 60,
        "transcript": "A complete transcript.",
    }
    values.update(overrides)
    return Video.objects.create(**values)


def make_question(skill=None, **overrides):
    values = {
        "code": next_value("Q"),
        "skill": skill or make_skill(),
        "prompt": "What is the answer?",
        "difficulty": Question.Difficulty.STANDARD,
        "presentation_type": Question.PresentationType.TEXT,
        "cognitive_level": Question.CognitiveLevel.APPLY,
        "solution_steps_json": ["Solve the problem."],
        "explanation": "A test explanation.",
        "feedback_correct": "Correct.",
        "feedback_incorrect": "Try again.",
        "is_published": False,
    }
    values.update(overrides)
    return Question.objects.create(**values)


def make_choice(question=None, **overrides):
    values = {
        "question": question or make_question(),
        "label": QuestionChoice.Label.A,
        "text": "Choice text",
        "is_correct": True,
        "display_order": 1,
    }
    values.update(overrides)
    return QuestionChoice.objects.create(**values)


def make_question_set(**overrides):
    values = {
        "code": next_value("SET"),
        "name": "Test Set",
        "set_type": QuestionSet.SetType.PREPOST,
        "lesson": None,
        "skill": None,
        "is_published": False,
    }
    values.update(overrides)
    return QuestionSet.objects.create(**values)


def make_question_set_item(question_set=None, question=None, **overrides):
    values = {
        "question_set": question_set or make_question_set(),
        "question": question or make_question(),
        "display_order": 1,
    }
    values.update(overrides)
    return QuestionSetItem.objects.create(**values)


def make_student_path(student=None, **overrides):
    values = {
        "student": student or make_user(),
        "status": StudentPath.Status.PRETEST_REQUIRED,
        "current_stage": StudentPath.Stage.PRETEST,
    }
    values.update(overrides)
    return StudentPath.objects.create(**values)


def make_session(student=None, **overrides):
    values = {
        "student": student or make_user(),
        "session_type": Session.SessionType.PRETEST,
        "status": Session.Status.ISSUED,
        "attempt_number": 1,
    }
    values.update(overrides)
    return Session.objects.create(**values)


def make_session_item(session=None, question=None, **overrides):
    values = {
        "session": session or make_session(),
        "question": question or make_question(),
        "display_order": 1,
    }
    values.update(overrides)
    return SessionItem.objects.create(**values)


def make_response(session_item=None, selected_choice=None, **overrides):
    if session_item is None:
        question = make_question()
        session_item = make_session_item(question=question)
    if selected_choice is None:
        selected_choice = make_choice(question=session_item.question)
    values = {
        "session_item": session_item,
        "selected_choice": selected_choice,
        "hint_used": False,
        "answered_at": timezone.now(),
    }
    values.update(overrides)
    return Response.objects.create(**values)


def make_skill_mastery(student=None, skill=None, **overrides):
    values = {
        "student": student or make_user(),
        "skill": skill or make_skill(),
        "p_known": Decimal("0.300000"),
        "evidence_count": 0,
    }
    values.update(overrides)
    return SkillMastery.objects.create(**values)


def make_mastery_event(mastery=None, response=None, **overrides):
    values = {
        "mastery": mastery or make_skill_mastery(),
        "response": response or make_response(),
        "p_before": Decimal("0.300000"),
        "p_after_observation": Decimal("0.500000"),
        "p_after_learning": Decimal("0.545000"),
        "learning_transition_applied": True,
    }
    values.update(overrides)
    return MasteryEvent.objects.create(**values)


def make_decision(session=None, **overrides):
    values = {
        "session": session or make_session(),
        "action": Decision.Action.PROGRESS,
        "reason_code": "test_decision",
        "policy_version": "Q-LEARNING-V1",
        "input_snapshot_json": {"state": "test"},
    }
    values.update(overrides)
    return Decision.objects.create(**values)


def make_decision_target(decision=None, skill=None, **overrides):
    values = {
        "decision": decision or make_decision(),
        "skill": skill or make_skill(),
        "target_kind": DecisionTargetSkill.TargetKind.NEXT_EXERCISE,
    }
    values.update(overrides)
    return DecisionTargetSkill.objects.create(**values)


def make_feedback(session=None, **overrides):
    values = {
        "session": session or make_session(),
        "feedback_text": "Test feedback.",
        "generation_status": SessionFeedback.GenerationStatus.FALLBACK,
    }
    values.update(overrides)
    return SessionFeedback.objects.create(**values)


def make_system_setting(changed_by=None, **overrides):
    values = {
        "singleton_key": 1,
        "study_access_enabled": False,
        "posttest_access_enabled": False,
        "changed_by": changed_by or make_user(User.Role.ADMIN),
        "revision": 0,
    }
    values.update(overrides)
    return SystemSetting.objects.create(**values)


def make_audit_event(actor=None, **overrides):
    values = {
        "actor": actor,
        "action": "test.event",
        "target_type": "test",
        "target_id": uuid.uuid4(),
        "target_snapshot_json": {},
        "metadata_json": {},
    }
    values.update(overrides)
    return AuditEvent.objects.create(**values)
