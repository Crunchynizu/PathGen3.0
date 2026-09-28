import re
from pathlib import Path

from django.test import SimpleTestCase


BASE_DIR = Path(__file__).resolve().parents[1]
DASHBOARD_TEMPLATES = [
    BASE_DIR / "templates" / "admin" / "admin_dashboard.html",
    BASE_DIR / "templates" / "teacher" / "teacher_dashboard.html",
    BASE_DIR / "templates" / "student" / "student_dashboard.html",
    BASE_DIR / "templates" / "shared" / "view_student_progress.html",
    BASE_DIR / "templates" / "partials" / "chart_with_table.html",
]


class Phase12AccessibilityTests(SimpleTestCase):
    def test_15_every_canvas_has_an_aria_label(self):
        source = (BASE_DIR / "templates" / "partials" / "chart_with_table.html").read_text()
        canvases = re.findall(r"<canvas\b[^>]*>", source, flags=re.IGNORECASE)
        self.assertTrue(canvases)
        self.assertTrue(all("aria-label=" in canvas for canvas in canvases))

    def test_16_chart_partial_has_table_and_text_alternative(self):
        source = (BASE_DIR / "templates" / "partials" / "chart_with_table.html").read_text()
        self.assertIn("<table>", source)
        self.assertIn("chart-empty", source)
        self.assertIn("<caption", source)

    def test_17_status_indicators_always_include_text(self):
        student_source = (BASE_DIR / "templates" / "student" / "student_dashboard.html").read_text()
        progress_source = (BASE_DIR / "templates" / "shared" / "view_student_progress.html").read_text()
        for source in [student_source, progress_source]:
            self.assertIn("{{ skill.band }}", source)
            self.assertIn("{{ skill.evidence }}", source)

    def test_18_dashboard_templates_have_no_hardcoded_hex(self):
        hex_pattern = re.compile(r"#[0-9a-fA-F]{3,8}\b")
        for path in DASHBOARD_TEMPLATES:
            self.assertIsNone(hex_pattern.search(path.read_text()), path)

    def test_19_dashboard_templates_have_no_dark_utilities(self):
        for path in DASHBOARD_TEMPLATES:
            source = path.read_text()
            self.assertNotIn("dark:", source, path)
            self.assertNotIn('class="dark', source, path)
