import re
from html.parser import HTMLParser
from pathlib import Path

from django.http import HttpResponse
from django.template.loader import render_to_string
from django.test import SimpleTestCase

from apps.accounts.forms import AccountNameForm


BASE_DIR = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = BASE_DIR / "templates"


def template_sources():
    return {
        path.relative_to(TEMPLATE_DIR).as_posix(): path.read_text(encoding="utf-8")
        for path in TEMPLATE_DIR.rglob("*.html")
    }


class ControlLabelParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.label_depth = 0
        self.label_for = set()
        self.controls = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "label":
            self.label_depth += 1
            if attrs.get("for"):
                self.label_for.add(attrs["for"])
        elif tag in {"input", "select", "textarea"}:
            if attrs.get("type", "").lower() == "hidden":
                return
            self.controls.append((attrs, self.label_depth > 0))

    def handle_endtag(self, tag):
        if tag == "label" and self.label_depth:
            self.label_depth -= 1


class Phase13AccessibilityTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.templates = template_sources()
        cls.all_templates = "\n".join(cls.templates.values())
        cls.app_js = (BASE_DIR / "static" / "js" / "app.js").read_text(
            encoding="utf-8"
        )

    def test_01_every_base_template_declares_light_color_scheme(self):
        base = self.templates["pages/_base.html"]
        self.assertIn('<meta name="color-scheme" content="only light">', base)
        page_templates = {
            name: source
            for name, source in self.templates.items()
            if name.startswith("pages/") and name != "pages/_base.html"
        }
        page_templates["assessment/assessment.html"] = self.templates[
            "assessment/assessment.html"
        ]
        page_templates["error/error.html"] = self.templates["error/error.html"]
        self.assertEqual(len(page_templates), 19)
        for name, source in page_templates.items():
            with self.subTest(template=name):
                self.assertIn('{% extends "pages/_base.html" %}', source)

    def test_02_every_base_has_skip_to_content(self):
        base = self.templates["pages/_base.html"]
        self.assertRegex(
            base,
            re.compile(
                r'<a\b[^>]*href="#main-content"[^>]*>\s*Skip to content\s*</a>',
                re.I,
            ),
        )
        self.assertIn('id="main-content"', base)

    def test_03_no_div_is_used_as_an_onclick_control(self):
        self.assertIsNone(
            re.search(r"<div\b[^>]*\bonclick\s*=", self.all_templates, re.I)
        )

    def test_04_every_canvas_has_an_accessible_name(self):
        canvases = re.findall(r"<canvas\b[^>]*>", self.all_templates, re.I)
        self.assertTrue(canvases)
        for canvas in canvases:
            self.assertRegex(canvas, r'aria-label="[^"]+"')

    def test_05_every_chart_has_a_table_or_text_alternative(self):
        for template_name in (
            "pages/admin/admin_dashboard.html",
            "pages/teacher/teacher_dashboard.html",
        ):
            with self.subTest(template=template_name):
                source = self.templates[template_name]
                self.assertIn("data-chart-block", source)
                self.assertIn("<table", source)
                self.assertIn('role="status"', source)
                self.assertIn("Not enough evidence for this chart", source)

    def test_06_every_form_control_has_a_label_or_aria_label(self):
        failures = []
        for name, source in self.templates.items():
            parser = ControlLabelParser()
            parser.feed(source)
            for attrs, nested in parser.controls:
                labelled = (
                    nested
                    or bool(attrs.get("aria-label"))
                    or bool(attrs.get("aria-labelledby"))
                    or attrs.get("id") in parser.label_for
                )
                if not labelled:
                    failures.append((name, attrs.get("name") or attrs.get("id")))
        login = self.templates["pages/account/login.html"]
        self.assertIn('for="{{ field.id_for_label }}"', login)
        self.assertFalse(failures, failures)

    def test_07_field_errors_are_tied_with_aria_describedby(self):
        form = AccountNameForm(data={"first_name": "", "last_name": ""})
        self.assertFalse(form.is_valid())
        rendered = render_to_string(
            "modals/account/update_name.html", {"name_form": form}
        )
        self.assertIn('aria-describedby="id_first_name_error"', rendered)
        self.assertIn('id="id_first_name_error"', rendered)

    def test_08_status_is_never_conveyed_by_color_alone(self):
        dashboard = self.templates["pages/student/student_dashboard.html"]
        self.assertIn("{{ skill.band }}", dashboard)
        self.assertIn("{{ skill.evidence }}", dashboard)
        rendered = render_to_string(
            "pages/student/student_dashboard.html",
            {
                "request": {
                    "user": {
                        "role": "student",
                        "username": "test-student",
                        "get_full_name": "Test Student",
                        "get_role_display": "Student",
                    },
                    "resolver_match": {"url_name": "student_dashboard"},
                },
                "student_name": "Test Student",
                "next_step": {"label": "Review", "description": "Keep learning."},
                "skill_rows": [
                    {
                        "code": "S1",
                        "name": "Skill one",
                        "state": "np",
                        "band": "Not proficient yet",
                        "evidence": "1 evidence item",
                    },
                    {
                        "code": "S2",
                        "name": "Skill two",
                        "state": "dev",
                        "band": "Developing",
                        "evidence": "2 evidence items",
                    },
                    {
                        "code": "S3",
                        "name": "Skill three",
                        "state": "strong",
                        "band": "Strong",
                        "evidence": "3 evidence items",
                    },
                ],
            },
        )
        response = HttpResponse(rendered)
        for visible_text in (
            "Not proficient yet",
            "Developing",
            "Strong",
            "1 evidence item",
            "2 evidence items",
            "3 evidence items",
        ):
            self.assertContains(response, visible_text)

    def test_09_templates_have_no_hardcoded_hex_colors(self):
        hex_color = re.compile(r"#[0-9a-fA-F]{3,8}\b")
        failures = [name for name, source in self.templates.items() if hex_color.search(source)]
        self.assertFalse(failures, failures)

    def test_10_templates_have_no_dark_utilities(self):
        failures = [name for name, source in self.templates.items() if "dark:" in source]
        self.assertFalse(failures, failures)

    def test_11_css_has_no_dark_color_scheme_media_query(self):
        css = "\n".join(
            path.read_text(encoding="utf-8")
            for path in [BASE_DIR / "input.css", BASE_DIR / "static" / "css" / "theme.css"]
        )
        self.assertNotIn("prefers-color-scheme: dark", css.lower())

    def test_12_every_dialog_has_an_accessible_name(self):
        dialogs = re.findall(r"<dialog\b[^>]*>", self.all_templates, re.I | re.S)
        self.assertTrue(dialogs)
        for dialog in dialogs:
            self.assertTrue(
                'aria-label="' in dialog or 'aria-labelledby="' in dialog,
                dialog,
            )

    def test_13_modal_focus_is_trapped(self):
        self.assertIn("function trapFocus", self.app_js)
        self.assertIn('document.addEventListener("keydown", trapFocus)', self.app_js)
        self.assertIn("activateLayer(dialog, button)", self.app_js)

    def test_14_modal_focus_returns_to_the_opener(self):
        self.assertIn("const returnTarget = opener", self.app_js)
        self.assertIn("returnTarget.focus()", self.app_js)
        self.assertIn('dialog.addEventListener("close", deactivateLayer)', self.app_js)

    def test_15_mobile_drawer_traps_focus_and_restores_on_escape(self):
        self.assertIn("activateLayer(drawerElement, drawerOpener)", self.app_js)
        self.assertIn('event.key === "Escape"', self.app_js)
        self.assertIn("closeDrawer()", self.app_js)
        self.assertIn("deactivateLayer()", self.app_js)

    def test_16_assessment_progress_is_announced(self):
        progress = self.templates["assessment/assessment.html"]
        self.assertIn('role="status"', progress)
        self.assertIn('aria-live="polite"', progress)
        self.assertIn("<progress", progress)

    def test_17_every_video_has_captions_and_transcript_links(self):
        video = "\n".join(
            (
                self.templates["assessment/assessment.html"],
                self.templates["pages/student/lesson.html"],
            )
        )
        self.assertIn("cc_load_policy=1", video)
        self.assertIn("Open video with captions", video)
        self.assertIn("Open transcript", video)

    def test_18_every_figure_has_alt_text_or_is_hidden(self):
        images = re.findall(r"<img\b[^>]*>", self.all_templates, re.I | re.S)
        self.assertTrue(images)
        for image in images:
            self.assertTrue('alt="' in image or 'aria-hidden="true"' in image, image)
