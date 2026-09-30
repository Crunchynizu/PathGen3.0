# PathGen 3.0

PathGen 3.0 is a PostgreSQL-backed Django monolith for a fixed Grade 7 integer-learning journey.

## Local setup

1. Install Python 3.12 and PostgreSQL 16.
2. Create a virtual environment: `python -m venv .venv`.
3. Install dependencies: `python -m pip install -r requirements.txt`.
4. Copy `.env.example` to `.env` and set local values.
5. Run checks: `python manage.py check --settings=config.settings.local`.
6. Run tests: `python manage.py test --settings=config.settings.test --keepdb`.

## CSS

`static/css/theme.css` holds tokens and shared component classes. `static/css/shell.css` styles the sidebar, hamburger, breadcrumbs, and back link. `static/css/modals.css` styles all dialogs. Each page has a stylesheet under `static/css/pages/`.

There is no build step. Edit and commit CSS files directly.
