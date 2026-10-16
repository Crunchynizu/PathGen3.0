from pathlib import Path

from django.test import SimpleTestCase


BASE_DIR = Path(__file__).resolve().parents[1]


class Phase13ResponsiveContractTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.app_js = (BASE_DIR / "static" / "js" / "app.js").read_text(
            encoding="utf-8"
        )
        cls.templates = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (BASE_DIR / "templates").rglob("*.html")
        )

    def test_viewport_supports_320px_and_does_not_disable_zoom(self):
        base = (BASE_DIR / "templates" / "_base.html").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            'name="viewport" content="width=device-width, initial-scale=1.0"', base
        )
        self.assertNotIn("maximum-scale", base)
        self.assertNotIn("user-scalable=no", base)

    def test_mobile_filter_boundary_is_below_sm(self):
        self.assertIn('window.matchMedia("(max-width: 639px)")', self.app_js)

    def test_tables_progressively_become_labelled_cards_on_narrow_screens(self):
        self.assertIn("table.classList.add(...responsiveTableClasses)", self.app_js)
        self.assertIn("cell.dataset.label", self.app_js)

    def test_filters_use_disclosure_on_base_and_xs(self):
        self.assertIn('data-ui="filter-disclosure"', self.templates)
        self.assertIn("<summary", self.templates)
        self.assertIn('window.matchMedia("(max-width: 639px)")', self.app_js)
        self.assertIn(
            'document.querySelectorAll("[data-ui~=\'filter-disclosure\']")',
            self.app_js,
        )
        self.assertIn("details.open = !compactFilterQuery.matches", self.app_js)

    def test_narrow_content_uses_wrapping_and_overflow_guards(self):
        self.assertIn('data-ui="table-wrap"', self.templates)
        self.assertIn('data-ui="filter-disclosure"', self.templates)
        self.assertIn("cell.dataset.label", self.app_js)
