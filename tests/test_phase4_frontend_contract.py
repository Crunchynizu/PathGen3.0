import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class FrontendContractTests(SimpleTestCase):
    def test_exact_base_partial_and_modal_inventory(self):
        templates = Path(settings.BASE_DIR) / "templates"
        bases = {path.name for path in templates.glob("base*.html")}
        partials = list((templates / "partials").glob("*.html"))
        modals = list((templates / "modals").rglob("*.html"))

        self.assertEqual(
            bases,
            {"base.html", "base_main.html", "base_secondary.html", "base_assessment.html"},
        )
        self.assertEqual(len(partials), 20)
        self.assertEqual(len(modals), 24)
        for modal in modals:
            with self.subTest(modal=modal):
                self.assertIn(
                    'aria-label="',
                    modal.read_text(encoding="utf-8"),
                )

    def test_light_mode_tokens_and_no_raw_component_hex(self):
        root = Path(settings.BASE_DIR)
        source_files = [root / "input.css", root / "static" / "js" / "app.js"]
        source_files.extend((root / "templates").rglob("*.html"))
        combined = "\n".join(path.read_text(encoding="utf-8") for path in source_files)
        self.assertNotRegex(combined, re.compile(r"#[0-9a-fA-F]{3,8}\b"))
        self.assertNotIn("dark:", combined)
        self.assertNotIn("prefers-color-scheme: dark", combined)
        self.assertIn("var(--color-", (root / "input.css").read_text(encoding="utf-8"))

    def test_rendered_base_has_light_meta_and_accessibility_landmarks(self):
        for template_name in ("base.html", "base_main.html", "base_secondary.html", "base_assessment.html"):
            source = (Path(settings.BASE_DIR) / "templates" / template_name).read_text(
                encoding="utf-8"
            )
            if template_name == "base.html":
                self.assertIn('<meta name="color-scheme" content="only light">', source)
            else:
                self.assertIn('{% extends "base', source)

    def test_mobile_drawer_implements_focus_contract(self):
        script = (Path(settings.BASE_DIR) / "static" / "js" / "app.js").read_text(
            encoding="utf-8"
        )
        for requirement in ("Tab", "Escape", ".inert", "returnTarget.focus()", "aria-expanded"):
            self.assertIn(requirement, script)

    def test_every_post_form_contains_csrf_token(self):
        templates = Path(settings.BASE_DIR) / "templates"
        for path in templates.rglob("*.html"):
            source = path.read_text(encoding="utf-8")
            if 'method="post"' in source:
                with self.subTest(path=path):
                    self.assertIn("{% csrf_token %}", source)
