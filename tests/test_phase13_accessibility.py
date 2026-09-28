import re
from html.parser import HTMLParser
from pathlib import Path

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
        base = self.templates["base.html"]
        self.assertIn('<meta name="color-scheme" content="only light">', base)
        self.assertIn('{% extends "base.html" %}', self.templates["base_main.html"])
        self.assertIn('{% extends "base.html" %}', self.templates["base_assessment.html"])
        self.assertIn(
            '{% extends "base_main.html" %}', self.templates["base_secondary.html"]
        )

    def test_02_every_base_has_skip_to_content(self):
        base = self.templates["base.html"]
        self.assertIn('class="skip-link"', base)
        self.assertIn('href="#main-content"', base)
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
        chart_partial = self.templates["partials/chart_with_table.html"]
        self.assertIn("<table", chart_partial)
        self.assertIn('class="chart-empty" role="status"', chart_partial)

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
        form_field = self.templates["partials/form_field.html"]
        self.assertIn('for="{{ field.id_for_label }}"', form_field)
        self.assertFalse(failures, failures)

    def test_07_field_errors_are_tied_with_aria_describedby(self):
        form = AccountNameForm(data={"first_name": "", "last_name": ""})
        self.assertFalse(form.is_valid())
        rendered = render_to_string(
            "partials/form_field.html", {"field": form["first_name"]}
        )
        self.assertIn('aria-describedby="id_first_name_error"', rendered)
        self.assertIn('id="id_first_name_error"', rendered)

    def test_08_status_is_never_conveyed_by_color_alone(self):
        self.assertIn(
            "{{ label|default:status|title }}",
            self.templates["partials/status_badge.html"],
        )
        self.assertIn("{{ band|default:", self.templates["partials/skill_band_badge.html"])
        self.assertIn('class="band-label"', self.templates["student/student_dashboard.html"])
        self.assertIn('class="evidence-label"', self.templates["student/student_dashboard.html"])

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
        progress = self.templates["partials/assessment_progress.html"]
        self.assertIn('role="status"', progress)
        self.assertIn('aria-live="polite"', progress)
        self.assertIn("<progress", progress)

    def test_17_every_video_has_captions_and_transcript_links(self):
        video = self.templates["partials/video_player.html"]
        self.assertIn("cc_load_policy=1", video)
        self.assertIn("Open video with captions", video)
        self.assertIn("Open transcript", video)

    def test_18_every_figure_has_alt_text_or_is_hidden(self):
        images = re.findall(r"<img\b[^>]*>", self.all_templates, re.I | re.S)
        self.assertTrue(images)
        for image in images:
            self.assertTrue('alt="' in image or 'aria-hidden="true"' in image, image)
