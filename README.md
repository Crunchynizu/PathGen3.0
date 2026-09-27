# PathGen 3.0

PathGen 3.0 is a PostgreSQL-backed Django monolith for a fixed Grade 7 integer-learning journey.

## Local setup

1. Install Python 3.12 and PostgreSQL 16.
2. Create a virtual environment: `python -m venv .venv`.
3. Install dependencies: `python -m pip install -r requirements.txt`.
4. Copy `.env.example` to `.env` and set local values.
5. Run checks: `python manage.py check --settings=config.settings.local`.
6. Run tests: `python manage.py test --settings=config.settings.test --keepdb`.

Build CSS with the committed standalone Tailwind executable:

```powershell
tools/tailwindcss.exe -i input.css -o static/css/app.css --minify
```
