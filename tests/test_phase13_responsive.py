from pathlib import Path

from django.test import SimpleTestCase


BASE_DIR = Path(__file__).resolve().parents[1]


class Phase13ResponsiveContractTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.input_css = (BASE_DIR / "input.css").read_text(encoding="utf-8")
        cls.app_js = (BASE_DIR / "static" / "js" / "app.js").read_text(
            encoding="utf-8"
        )
        cls.tailwind = (BASE_DIR / "tailwind.config.js").read_text(encoding="utf-8")
        cls.templates = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (BASE_DIR / "templates").rglob("*.html")
        )

    def test_viewport_supports_320px_and_does_not_disable_zoom(self):
        base = (BASE_DIR / "templates" / "pages" / "_base.html").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            'name="viewport" content="width=device-width, initial-scale=1.0"', base
        )
        self.assertNotIn("maximum-scale", base)
        self.assertNotIn("user-scalable=no", base)

    def test_required_breakpoints_are_configured(self):
        for name, size in (
            ("xs", "475px"),
            ("sm", "640px"),
            ("md", "768px"),
            ("lg", "1024px"),
            ("xl", "1280px"),
            ('"2xl"', "1536px"),
        ):
            self.assertIn(f'{name}: "{size}"', self.tailwind)

    def test_tables_progressively_become_labelled_cards_on_narrow_screens(self):
        for utility in (
            "max-sm:[&_thead]:[position:absolute]",
            "max-sm:[&_tbody]:[display:block]",
            "max-sm:[&_tr]:[display:block]",
            "max-sm:[&_td]:[display:grid]",
            "max-sm:[&_td::before]:[content:attr(data-label)]",
        ):
            self.assertIn(f'"{utility}"', self.app_js)
        self.assertIn("table.classList.add(...responsiveTableClasses)", self.app_js)
        self.assertIn("cell.dataset.label", self.app_js)

    def test_filters_use_disclosure_on_base_and_xs(self):
        self.assertIn('data-ui="filter-disclosure"', self.templates)
        self.assertIn("max-sm:[&_>_summary]:[display:flex]", self.templates)
        self.assertIn(
            "max-sm:[&[open]_>_summary]:[margin-bottom:0.75rem]",
            self.templates,
        )
        self.assertIn('window.matchMedia("(max-width: 639px)")', self.app_js)
        self.assertIn(
            'document.querySelectorAll("[data-ui~=\'filter-disclosure\']")',
            self.app_js,
        )
        self.assertIn("details.open = !compactFilterQuery.matches", self.app_js)

    def test_narrow_content_uses_wrapping_and_overflow_guards(self):
        self.assertIn("overflow-x-auto", self.templates)
        self.assertIn("max-sm:[&_td]:[overflow-wrap:anywhere]", self.templates)
        self.assertIn("[&_img]:[max-width:100%]", self.templates)
        for breakpoint in ("sm:", "md:", "lg:", "xl:"):
            self.assertIn(breakpoint, self.templates)
