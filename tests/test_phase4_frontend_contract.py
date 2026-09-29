import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class FrontendContractTests(SimpleTestCase):
    def test_exact_base_partial_and_modal_inventory(self):
        templates = Path(settings.BASE_DIR) / "templates"
        root_bases = list(templates.glob("_base.html"))
        shared_base = templates / "_base.html"
        components = {path.name for path in (templates / "components").glob("*.html")}
        page_templates = [
            path
            for path in (templates / "pages").rglob("*.html")
            if path.name != "_base.html"
        ]
        modals = list((templates / "modals").rglob("*.html"))

        self.assertEqual(root_bases, [shared_base])
        self.assertTrue(shared_base.is_file())
        self.assertFalse((templates / "pages" / "_base.html").exists())
        self.assertFalse((templates / "partials").exists())
        self.assertEqual(
            components,
            {"sidebar.html", "hamburger_menu.html", "breadcrumbs.html", "back_link.html"},
        )
        self.assertEqual(len(page_templates), 17)
        self.assertTrue((templates / "assessment" / "assessment.html").is_file())
        self.assertTrue((templates / "error" / "error.html").is_file())
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
        theme = (root / "static" / "css" / "theme.css").read_text(encoding="utf-8")
        templates = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (root / "templates").rglob("*.html")
        )
        self.assertNotRegex(combined, re.compile(r"#[0-9a-fA-F]{3,8}\b"))
        self.assertNotIn("dark:", combined)
        self.assertNotIn("prefers-color-scheme: dark", combined)
        self.assertIn("var(--color-", theme)
        self.assertIn("var(--color-", templates)

    def test_rendered_base_has_light_meta_and_accessibility_landmarks(self):
        templates = Path(settings.BASE_DIR) / "templates"
        base = (templates / "_base.html").read_text(encoding="utf-8")
        self.assertIn('<meta name="color-scheme" content="only light">', base)
        self.assertIn('href="#main-content"', base)
        self.assertIn('id="main-content"', base)
        pages = [
            path
            for path in (templates / "pages").rglob("*.html")
            if path.name != "_base.html"
        ]
        pages.extend(
            [
                templates / "assessment" / "assessment.html",
                templates / "error" / "error.html",
            ]
        )
        self.assertEqual(len(pages), 19)
        for path in pages:
            with self.subTest(path=path):
                self.assertIn(
                    '{% extends "_base.html" %}',
                    path.read_text(encoding="utf-8"),
                )

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
