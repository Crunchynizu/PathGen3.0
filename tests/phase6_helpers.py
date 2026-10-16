from django.core.management import call_command
from django.test import TestCase

from apps.accounts.models import User
from apps.core.models import SystemSetting
from apps.curriculum.models import Lesson, QuestionSet, Skill
from apps.learning.models import Session, SessionItem, StudentPath
from tests.factories import make_user


class Phase6SeededTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_curriculum", verbosity=0)
        cls.admin = make_user(User.Role.ADMIN)
        cls.student = make_user(User.Role.STUDENT)
        cls.setting = SystemSetting.objects.create(
            singleton_key=1,
            study_access_enabled=True,
            posttest_access_enabled=False,
            changed_by=cls.admin,
            revision=1,
        )
        cls.path = StudentPath.objects.create(
            student=cls.student,
            status=StudentPath.Status.PRETEST_REQUIRED,
            current_stage=StudentPath.Stage.PRETEST,
        )

    def set_path(self, *, status, stage, lesson=None):
        self.path.status = status
        self.path.current_stage = stage
        self.path.current_lesson = lesson
        self.path.save()

    def lesson(self, order):
        return Lesson.objects.get(lesson_order=order)

    def lessons(self):
        """Every published lesson record in path order (Lesson 2 is three parts)."""
        return list(Lesson.objects.filter(is_published=True).order_by("lesson_order"))

    def skill(self, code):
        return Skill.objects.get(code=code)

    def make_session_from_set(self, *, session_type, question_set, lesson=None, limit=None):
        session = Session.objects.create(
            student=self.student,
            session_type=session_type,
            lesson=lesson,
            status=Session.Status.ISSUED,
            attempt_number=1,
        )
        rows = question_set.items.select_related("question").order_by("display_order")
        if limit is not None:
            rows = rows[:limit]
        SessionItem.objects.bulk_create(
            [
                SessionItem(
                    session=session,
                    question=row.question,
                    display_order=index,
                )
                for index, row in enumerate(rows, start=1)
            ]
        )
        return session

    def question_set(self, set_type, *, lesson=None, skill=None):
        return QuestionSet.objects.get(
            set_type=set_type,
            lesson=lesson,
            skill=skill,
            is_published=True,
        )
