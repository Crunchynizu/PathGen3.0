# tech_stack.md

Technology stack for PathGen 3.0.

---

## Core stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12 + Django 5.2 |
| Database | PostgreSQL 16 |
| Frontend | HTML + pure CSS + Vanilla JS |
| Font | Inter (Google Fonts) |
| Icons | Lucide self-hosted library, `static/vendor/lucide/lucide.min.js` |
| Charts | Chart.js UMD (self-hosted) |
| Server | Gunicorn |
| Static | WhiteNoise |
| Host | Railway |

No npm. No Node. No bundler. No CDN for JavaScript or CSS libraries. The only allowed remote asset is Google Fonts for Inter.

---

## Backend packages

```text
Django==5.2.17
psycopg[binary]==3.2.4
python-dotenv==1.0.1
dj-database-url==2.3.0
gunicorn==23.0.0
whitenoise==6.8.2
groq==0.15.0
openai==1.60.0
```

**8 packages. Nothing else.**

---

## Database — local to production

| Phase | Database |
|---|---|
| Development | Local PostgreSQL at `127.0.0.1:5432` |
| Production | Railway managed PostgreSQL |

**Switch method:** Change `DATABASE_URL` env variable only.

**Steps:**
1. Create PostgreSQL in Railway
2. Copy its `DATABASE_URL` into Railway app variables
3. Deploy
4. Run `migrate` and `seed_curriculum` on Railway

No code changes. No settings changes. Just the env variable.

No SQLite. Ever. Not even for tests.

---

## Frontend

### CSS

- Pure CSS. `static/css/theme.css` holds tokens, base styles, and shared components.
- `static/css/shell.css` holds main, secondary, focus, and standalone shell layouts.
- `static/css/modals.css` holds dialog styling.
- Each page links its own stylesheet under `static/css/pages/` through `{% block page_css %}`.
- CSS files are edited directly and committed. No build step.

### Breakpoints

| Key | Min width |
|---|---|
| base | < 475px |
| xs | 475px |
| sm | 640px |
| md | 768px |
| lg | 1024px |
| xl | 1280px |
| 2xl | 1536px |

### JavaScript

Vanilla JS only. No React, Vue, Alpine, HTMX.

### Font

Inter via Google Fonts.

Google Fonts for Inter is the only allowed remote asset.

### Icons

Lucide self-hosted library, `static/vendor/lucide/lucide.min.js`.

### Charts

Chart.js UMD, self-hosted in `static/vendor/chartjs/`.

---

## Theme

Light mode only. No dark mode. No switcher.

Every base includes:
```html
<meta name="color-scheme" content="only light">
```

Components use `var(--color-*)` tokens only. Never raw hex.

`#0cc0df` is never body text. Use `#0A8298` for cyan text on white.

---

## Environment

### `.env` (local)

```dotenv
SECRET_KEY=
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost
CSRF_TRUSTED_ORIGINS=http://127.0.0.1:8000,http://localhost:8000

DATABASE_URL=postgresql://pathgen_user:password@127.0.0.1:5432/pathgen

GROQ_API_KEY=
GROQ_MODEL=gpt-oss-120b
OPENAI_API_KEY=
EMBEDDING_MODEL=text-embedding-3-small
```

### Railway variables

Same keys, production values. `DEBUG=False`, real domain, Railway `DATABASE_URL`, real API keys.

Production fails closed if any required value is missing.

---

## Deployment

### Procfile

```text
web: gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 3 --timeout 60
release: python manage.py migrate --noinput
```

No `railway.toml`. `Procfile` is the source of truth.

---

## Storage

All assets committed to `static/`:

| Folder | Content |
|---|---|
| `static/css/` | Shared pure CSS and per-page stylesheets |
| `static/vendor/lucide/` | `lucide.min.js` self-hosted library |
| `static/logo/` | pathgen.png |
| `static/avatar/` | Role-based avatars |
| `static/lesson/` | Lesson figures |
| `static/exercise/` | Exercise figures |
| `static/activity/` | Activity figures |
| `static/vendor/chartjs/` | Chart.js UMD |

No uploads. No AWS. No S3. No media/ folder.

---

## External services

| Service | Purpose | Model |
|---|---|---|
| OpenAI | Embeddings | `text-embedding-3-small` |
| Groq | Generation | `gpt-oss-120b` |

Only used from Phase 10 onward. Both pinned.

---

## Q-Learning training

Trained in a **separate external repo**, not in PathGen.

- Output: `q_table.json` (~50KB)
- Copied to `apps/adaptive/q_table.json`
- PathGen does not train — only loads the frozen table

---

## Local setup

1. Install Python 3.12
2. Install PostgreSQL 16
3. Create local database `pathgen`
4. `python -m venv .venv`
5. `.venv\Scripts\Activate.ps1`
6. `pip install -r requirements.txt`
7. Copy `.env.example` → `.env`, fill in
8. `python manage.py migrate`
9. `python manage.py seed_curriculum`
10. `python manage.py runserver`

No npm. CSS files are edited directly; no build step.

---

## Testing

```bash
python manage.py test --settings=config.settings.test --keepdb
```

Django test runner only. No pytest.

---

## Not used

npm · Node · Tailwind · PostCSS · Vite · Preline · Geist · Impeccable · AWS S3 · Redis · Celery · Pinecone · pgvector · DRF · JWT · React · Vue · Alpine · Bootstrap · jQuery · pytest · numpy (except trainer) · pandas

---

## Summary

| Layer | Choice |
|---|---|
| Backend | Django 5.2 |
| Database | PostgreSQL 16 (local → Railway) |
| Switch method | Change env variable |
| Frontend | HTML + pure CSS + Vanilla JS |
| CSS build | None; edit and commit CSS directly |
| Font | Inter |
| Icons | Lucide self-hosted library |
| Charts | Chart.js UMD |
| Host | Railway |
| Packages | 8 |
| Training | External repo |
| npm | None |
| Uploads | None |
