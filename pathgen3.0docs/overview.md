# PathGen 3.0 — Overview

## 1. Purpose

PathGen 3.0 is a research-oriented adaptive-learning system for Grade 7 Philippine DepEd mathematics. It delivers a fixed integer curriculum, adapts practice per student using Bayesian Knowledge Tracing and a deterministic Q-Learning decider, and produces matched pre-test/post-test learning-gain data suitable for thesis evaluation.

The system is a Django monolith. It is server-rendered, PostgreSQL-backed, and deployed on Railway. It uses pure CSS, Inter, the self-hosted Lucide library, Chart.js UMD, and vanilla JavaScript. It is permanently light-mode.

## 2. Research Objective

The primary outcome is matched learning gain:

```text
learning_gain = posttest_score - pretest_score
```

The same protected 30-item assessment is used for both pre-test and post-test. Scores are derived from stored responses. The system never asks students or teachers to enter scores manually.

Research displays must state cohort, sample size, window, definition, and limitations. The system must never imply that matched gain proves causation.

## 3. Fixed Learning Journey

Every student follows the same macro path:

```text
Pre-test → Lesson 1 → Lesson 2 → Lesson 3 → Activity → Post-test
```

Within lessons, the path adapts through regular, additional, and foundational practice. The macro sequence never changes.

## 4. Scope and Content

- Grade 7 integers only.
- 3 lessons.
- 6 skills.
- 94 unique questions total.
- Sets:
  - 30 protected pre/post items.
  - 18 regular exercise questions.
  - 18 additional exercise questions.
  - 18 foundational exercise questions.
  - 10 activity questions.
- Regular and additional exercises contain 6 questions: 3 per lesson skill.
- Foundational work contains 3 questions per targeted skill.
- Activity distribution: S1=2, S2=2, S3=2, S4=2, S5=1, S6=1.
- Bloom labels are metadata only. They never affect scoring, BKT, routing, selection, or access.

## 5. Roles

### Admin

Manages teacher and student accounts, classes, access settings, audits, and monitoring. Admin cannot create other admins through the normal UI. Admin cannot modify research evidence.

### Teacher

Has read-only access to assigned classes, students, content, and progress. Teachers monitor but do not change scores, mastery, routing, or published content.

### Student

Accesses only their own path, sessions, results, feedback, and reached lessons. Class membership supports teacher monitoring and never gates learning.

## 6. Technology Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12 + Django 5.2 |
| Database | PostgreSQL 16 |
| Frontend | HTML + pure CSS + Vanilla JS |
| Font | Inter |
| Icons | Lucide self-hosted library |
| Charts | Chart.js UMD, self-hosted |
| Server | Gunicorn |
| Static | WhiteNoise |
| Host | Railway |

No npm. No Node. No bundler. No CDN for JavaScript or CSS libraries. The only allowed remote asset is Google Fonts for Inter.

Packages: Django, psycopg, python-dotenv, dj-database-url, gunicorn, whitenoise, groq, openai. Nothing else.

## 7. Architecture and Domain Apps

- Django monolith.
- PostgreSQL only. Never SQLite, not even for tests.
- Server-rendered templates.
- Pure CSS in shared and per-page stylesheets; no build step.
- Vanilla JavaScript only.
- No React, Vue, Alpine, HTMX, DRF, JWT, Celery, Redis, or external vector DB.

Domain apps:

- `accounts`
- `classrooms`
- `curriculum`
- `learning`
- `adaptive`
- `feedback`
- `core`

## 8. Database

Exactly 22 domain tables. Defined in `database_schema.md`.

Key rules:

- UUID primary keys except singleton and composite/through tables.
- Timezone-aware timestamps.
- Enums as `varchar` + `CHECK`.
- Required facts are non-null.
- Published curriculum used by a session is immutable.
- Submitted responses, BKT events, decisions, feedback, settings history, and audits are preserved.
- Scores, percentages, learning gain, mastery bands, elapsed duration, and dashboard totals are derived.
- Seed imports are transactional, idempotent, and keyed by stable codes.
- Runtime editing of scores, responses, mastery, routing decisions, or published content is forbidden.

Append-only tables:

- `adaptive_mastery_event`
- `adaptive_decision`
- `core_audit_event`

Enforced by PostgreSQL trigger. Application code cannot modify history.

## 9. Adaptive Engines

Scoring, BKT, Q-Learning, orchestration, and RAG are separate. RAG cannot change scores, BKT, Q-Learning decisions, access settings, or `learning_student_path`.

### 9.1 Scoring

`SCORING-V2`: a skill passes with at least 2 correct answers out of 3.

### 9.2 BKT

`BKT-V1` parameters:

| Parameter | Value |
|---|---|
| P(L0) | 0.30 |
| P(T) | 0.09 |
| P(G) | 0.10 |
| P(S) | 0.09 |

Phase rules:

| Session type | Posterior applied | P(T) applied |
|---|---|---|
| Pretest | Yes | No |
| Regular | Yes | Yes |
| Additional | Yes | Yes |
| Foundational (no hint) | Yes | Yes |
| Foundational (hint used) | No | Yes |
| Activity | Yes | Yes |
| Posttest | No | No |

Bands:

- `np` Needs Practice: p_known < 0.50
- `dev` Developing: 0.50 ≤ p_known < 0.80
- `strong` Strong: p_known ≥ 0.80

Post-test creates zero BKT events. Always.

### 9.3 Q-Learning

`Q-LEARNING-V1`. Trained externally. Consumed as a frozen artifact: `apps/adaptive/q_table.json`.

State:

```text
(weakest_band, average_band, pass_result)
```

Actions:

| Context | Allowed actions |
|---|---|
| After regular | progress, additional_exercise, foundational_exercise |
| After additional | progress, foundational_exercise |
| After foundational | Always progress (fixed) |
| After activity | Always posttest_ready (fixed) |

Fallback: if table missing, state absent, or invalid → `progress`. Deterministic. Never crashes.

Safety cap: 3 fails on same skill → force `progress` + mark `follow_up`.

### 9.4 Orchestrator

Owns transaction boundaries. Calls BKT and Q-Learning but does not contain their logic.

Invariants:

- Path is authoritative.
- One response per item.
- One BKT event per response.
- One Q-Learning decision per eligible session.
- One feedback row per session.
- RAG never changes learning.
- No external calls inside database locks.

### 9.5 RAG

`RAG-RETRIEVAL-V1`.

| Parameter | Value |
|---|---|
| Embedding model | `text-embedding-3-small` |
| Generation model | `gpt-oss-120b` via Groq |
| Chunking | 350 target, 500 max, 50 overlap |
| Retrieval | top 4, minimum similarity 0.35 |
| Prompt max | 12,000 characters |
| Feedback max | 180 words |

Eligible sessions: regular, additional, foundational, activity.

Ineligible sessions: pretest, posttest.

RAG writes exactly one row in `feedback_session_feedback`, populating `feedback_text`, `generation_status`, and optionally `model_name`. It writes no other table. It cannot grade, update BKT, route students, or grant access. Provider failure uses deterministic fallback.

## 10. Frontend and Navigation

- 1 shared base template.
- 19 pages.
- 4 components.
- 24 modals.
- 48 templates total.

Every page extends `pages/_base.html`. Main, secondary, focus, and standalone are page-type rules, not separate base files. Shared UI is limited to `components/sidebar.html`, `components/hamburger_menu.html`, `components/breadcrumbs.html`, and `components/back_link.html`.

Sidebar groups: MAIN and ACCOUNT. Every role has Dashboard and My Account. Everything else is role-specific.

Breakpoints:

| Key | Min width |
|---|---|
| base | < 475px |
| xs | 475px |
| sm | 640px |
| md | 768px |
| lg | 1024px |
| xl | 1280px |
| 2xl | 1536px |

Light mode only. Every base includes:

```html
<meta name="color-scheme" content="only light">
```

No `.dark` class. No `dark:` utilities. No `prefers-color-scheme`. No theme switcher.

## 11. Authentication and Authorization

- Django session authentication.
- CSRF protection.
- Server-side role and object checks.
- Hidden controls are not security.
- Unauthorized requests → non-disclosing 403 or 404.
- Class membership never checked at login.
- Student Study Access and Post-test Access are global settings.
- Post-test requires both global access and `posttest_ready` path.

Roles:

| Role | Scope |
|---|---|
| Admin | Global, read-only on evidence |
| Teacher | Assigned classes and their students, read-only |
| Student | Own path, sessions, results, feedback |

## 12. Build Order

| Phase | Focus |
|---|---|
| 0 | Baseline frozen |
| 1 | Bootstrap |
| 2 | Schema (22 tables) |
| 3 | Auth + RBAC |
| 4 | Settings + classes + shell |
| 5 | Content source and assets |
| 6 | Sessions + assessment UI |
| 7 | BKT engine |
| 8 | Q-Learning engine |
| 9 | Orchestrator |
| 10 | RAG ingestion |
| 11 | RAG generation |
| 12 | Dashboards |
| 13 | Hardening |
| 14 | End-to-end acceptance |
| 15 | Deploy to Railway |

16 phases total (0–15).

Phase 14 flows into `build_order_must.md` Fix 1 through 8. Phase 15 begins only after Fix 8 passes.

## 13. Document Index

| File | Purpose |
|---|---|
| `overview.md` | This file. Entry point. |
| `authentication.md` | Login, sessions, roles, permissions, access gates |
| `bayesian_knowledge_tracing.md` | BKT theory and PathGen implementation |
| `build_order.md` | Phase-by-phase implementation sequence |
| `dashboard.md` | Admin, teacher, student dashboards |
| `database_schema.md` | 22 domain tables, constraints, triggers, locking |
| `folder_structure.md` | Complete app tree |
| `orchestrator_engine.md` | Transaction boundaries and workflow coordination |
| `pages.md` | 1 shared base, 19 pages, 4 components, 24 modals |
| `q_learning.md` | Q-Learning theory, artifact, runtime decider |
| `rag.md` | Retrieval-Augmented Generation pipeline |
| `sidebar.md` | Role-based navigation |
| `tech_stack.md` | Stack, packages, environment, deployment |
| `user_features.md` | All role capabilities and boundaries |
| `user_flows.md` | Every role flow and fixed journey |

Additional canonical specs may exist for admin, teacher, student, modals, estimator, decider, and RAG. They are read alongside these.

## 14. V1 Policy Constants

| Policy | Value |
|---|---|
| `SCORING-V2` | 2 of 3 correct passes a skill |
| Activity distribution | S1=2, S2=2, S3=2, S4=2, S5=1, S6=1 |
| `BKT-V1` | P(L0)=0.30, P(T)=0.09, P(G)=0.10, P(S)=0.09 |
| `Q-LEARNING-V1` | Trained externally, frozen table |
| `RAG-RETRIEVAL-V1` | Top 4, min 0.35, 350/500/50 tokens |

These constants appear in `manifest.json` and application config.

## 15. Hard Rules and Invariants

- PostgreSQL only. Never SQLite, not even for tests.
- Custom user model `accounts.User` must be set before first migrate.
- Never commit `.env`, secrets, API keys, `static/dist`, `staticfiles`, or database dumps.
- Light mode only.
- Exact breakpoints: base <475, xs 475, sm 640, md 768, lg 1024, xl 1280, 2xl 1536.
- RAG cannot change scores, BKT, Q-Learning decisions, access, or path.
- Post-test creates zero BKT events.
- Groq model: `gpt-oss-120b`.
- OpenAI embedding model: `text-embedding-3-small`.
- Do not rewrite or renumber the protected 30-item pre/post set, except for the documented PP-13 rewrite recorded in manifest.json under prepost_rewrites.
- Do not expose the pre/post set in Content.
- Do not invent BKT parameters, Q-Learning cutoff, mastery bands, RAG bounds, or scoring policy.
- All 22 domain tables must match `database_schema.md` exactly.
- Row locks belong in services, never in views.
- External provider calls never occur inside a database transaction.
- All mutations are CSRF-protected POST with Post/Redirect/Get.
- Accessibility: WCAG 2.2 AA. Keyboard, focus, zoom, non-color status, chart alternatives, figure alt text, video captions/transcripts.
- Icons are the self-hosted Lucide library. No individual SVG files.
- No browser automation.
- No Impeccable, Preline, or Geist.
- Videos use real YouTube IDs. Figures are placeholders until replaced.
- CSS is edited directly: shared `theme.css`, `shell.css`, `modals.css`, and one stylesheet per page under `static/css/pages/`. No build step.

## 16. Acceptance Summary

- All 18 specs consistent with implementation.
- All V1 policy constants match manifest.
- No protected history destructively cascaded.
- BKT, Q-Learning, RAG boundaries enforced in code and tests.
- Role scope, class optionality, settings gates, and post-test no-BKT all pass end-to-end.
- Every decision carries `policy_version`.
- External trainer produces `q_table.json` matching the contract.
- All figures present at their expected paths, real or placeholder.
- `validate_curriculum` passes.
- `seed_curriculum` imports all rows.
- Counts match `manifest.json`.
- Pre/post set excluded from Content.
- Avatars and logo present in `static/`.
- Full path from login through matched post-test results works.
- Every chart states cohort, sample size, definition.
- Empty states distinct from zero.
- Keyboard, screen-reader, zoom, reduced-motion checks pass.
