from apps.curriculum.models import QuestionSet
from apps.learning.models import Session, StudentPath
from apps.learning.services.responses import submit_response
from tests.phase6_helpers import Phase6SeededTestCase


class Phase9SeededTestCase(Phase6SeededTestCase):
    def exercise_session(self, session_type, *, lesson=None, skill_code=None):
        lesson = lesson or self.lesson(1)
        set_type = {
            Session.SessionType.REGULAR: QuestionSet.SetType.REGULAR,
            Session.SessionType.ADDITIONAL: QuestionSet.SetType.ADDITIONAL,
            Session.SessionType.FOUNDATIONAL: QuestionSet.SetType.FOUNDATIONAL,
        }[session_type]
        skill = self.skill(skill_code) if skill_code else None
        self.set_path(
            status=StudentPath.Status.LEARNING,
            stage=session_type,
            lesson=lesson,
        )
        return self.make_session_from_set(
            session_type=session_type,
            question_set=self.question_set(
                set_type,
                lesson=lesson if skill is None else None,
                skill=skill,
            ),
            lesson=lesson,
        )

    def submit_item(self, session, item, *, fail=False):
        choices = item.question.choices.order_by("display_order")
        choice = (
            choices.filter(is_correct=False).first()
            if fail
            else choices.get(is_correct=True)
        )
        return submit_response(
            actor=self.student,
            session_id=session.pk,
            session_item_id=item.pk,
            selected_choice_id=choice.pk,
        )

    def submit_all(self, session, *, failing_skill_codes=()):
        result = None
        for item in session.items.select_related("question").order_by("display_order"):
            result = self.submit_item(
                session,
                item,
                fail=item.question.skill.code in failing_skill_codes,
            )
        return result

    def submit_before_last(self, session, *, failing_skill_codes=()):
        items = list(
            session.items.select_related("question").order_by("display_order")
        )
        for item in items[:-1]:
            self.submit_item(
                session,
                item,
                fail=item.question.skill.code in failing_skill_codes,
            )
        return items[-1]
