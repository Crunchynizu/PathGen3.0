import json
from pathlib import Path

from django.conf import settings
from django.urls import reverse

from apps.curriculum.models import Lesson
from apps.learning.models import StudentPath
from apps.learning.views import LESSON_FIGURE_WIDGETS
from tests.phase6_helpers import Phase6SeededTestCase


class LessonWidgetTests(Phase6SeededTestCase):
    def test_every_lesson_figure_has_an_interactive_widget(self):
        source = Path(settings.BASE_DIR) / "content_source" / "lessons"
        for lesson_file in sorted(source.glob("lesson_*.json")):
            blocks = json.loads(lesson_file.read_text(encoding="utf-8"))["lesson"]["content"]["blocks"]
            for block in blocks:
                if block["type"] == "figure":
                    with self.subTest(figure=block["image_asset"]):
                        self.assertIn(Path(block["image_asset"]).stem, LESSON_FIGURE_WIDGETS)

    def test_lesson_pages_render_widgets_reveals_and_mistake_quiz(self):
        expected = {
            "L1": {"numberline"},
            "L2-1": {"chips"},
            "L2-2": {"signs"},
            "L2-3": {"signs"},
            "L3": {"order", "thermometer"},
        }
        self.client.force_login(self.student)
        for order, kinds in expected.items():
            lesson = Lesson.objects.get(code=order)
            self.set_path(status=StudentPath.Status.LEARNING, stage=StudentPath.Stage.LESSON, lesson=lesson)
            response = self.client.get(reverse("learning:lesson", args=[lesson.slug]))
            with self.subTest(lesson=order):
                self.assertEqual(response.status_code, 200)
                for kind in kinds:
                    self.assertContains(response, f'data-widget="{kind}"')
                self.assertContains(response, "data-reveal-group")
                self.assertContains(response, "data-spot-mistake")
                self.assertNotContains(response, "Picture coming soon")
