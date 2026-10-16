# build_order_must.md

Fix phases for PathGen 3.0. Runs after Phase 14 of build_order.md and before Phase 15 (Deploy to Railway).

Do NOT rebuild from scratch. Do NOT touch the database schema. Do NOT touch BKT, Q-Learning, RAG, orchestrator, or any service logic.

Presentation, template structure, and UI only.

Each Fix phase is one step. Stop after each. Report. Wait.

---

## Fix 1 — Pure CSS + Lucide

**Build:**
- Use pure CSS: `theme.css` holds tokens, base styles, and shared components; `shell.css` holds the four page shells; `modals.css` holds dialog styles; and `static/css/pages/` holds one stylesheet per page.
- Use the reference class names in templates and their page stylesheets.
- CSS files are edited directly and committed; no build step.
- Download Lucide UMD once to static/vendor/lucide/lucide.min.js.
- Include Lucide in pages/_base.html.
- Add window.lucide.createIcons() in static/js/app.js on DOMContentLoaded.
- Replace every icon with <i data-lucide="name"></i>.
- Icons inherit currentColor. No hardcoded stroke or fill.
- Remove the legacy individual-icon directory entirely.

**Do not:** use CDN at runtime. No npm. No per-icon SVGs. No CSS build tools. No Impeccable.

**Exit:** shared and per-page CSS files follow the pure-CSS structure. Lucide renders all icons. No individual icon directory remains. 250 tests pass.

---

## Fix 2 — Template tree + page types + components

**Build new tree:**

templates/
├── components/
│   ├── sidebar.html
│   ├── hamburger_menu.html
│   ├── breadcrumbs.html
│   └── back_link.html
├── pages/
│   ├── _base.html
│   ├── admin/     (5 pages)
│   ├── teacher/   (3 pages)
│   ├── student/   (3 pages)
│   ├── shared/    (4 pages)
│   └── account/   (2 pages)
├── assessment/
│   └── assessment.html
├── error/
│   └── error.html
└── modals/        (24 files, unchanged)

**Base:**
- pages/_base.html holds shared <head>, <body>, meta, scripts, blocks.
- Every page extends _base.html.
- Blocks: {% block shell %}, {% block content %}.

**Page types (rule, not file):**

| Type | The page includes | Pages |
|---|---|---|
| main | sidebar + hamburger_menu | admin_dashboard, user_management, class_management, override, audit_logs, teacher_dashboard, my_class, student_dashboard, my_lesson, content, my_account |
| secondary | breadcrumbs only | class_detail, view_lessons, view_questions, view_student_progress, lesson |
| focus | back_link | assessment, error |
| standalone | nothing shared | login |

**Sidebar per role:**

| Role | MAIN | ACCOUNT |
|---|---|---|
| Admin | Dashboard, Users, Classes, Content, Overrides, Audit Logs | My Account, Logout |
| Teacher | Dashboard, My Classes, Content | My Account, Logout |
| Student | Dashboard, My Lesson | My Account, Logout |

Sidebar: logo top, avatar + name bottom, aria-current="page" on active, Lucide icon per link.

Hamburger: focus trap, Escape to close, focus restore, background inert.

**Lesson rendering (pages/student/lesson.html):**
Not a JSON dump. Designed reading experience:
- Header: lesson number, title, summary, reading progress
- Block treatments:
  - Heading -> h2 with tight leading, negative tracking
  - Paragraph -> max-width 65ch, leading 1.5
  - Bullet list -> Lucide check icon per item
  - Numbered list -> ol
  - Figure -> figure with caption
  - Video -> embedded player with cue pause
  - Worked example -> distinct card, monospace math
  - Common mistake -> warning card with alert-triangle
  - Callout/tip -> info card
- Content column centered, max-width 65ch
- Prev/Next buttons at bottom
- "Ready to practice" CTA linking to regular exercise
- theme.css tokens only. No hardcoded hex. No per-page <style>.

**Do not:** retain legacy base templates, the legacy partial structure, or separate assessment-type templates.

**Exit:** new tree exists. Old paths gone. All 250 tests pass.

---

## Fix 3 — Admin dashboard

Rebuild pages/admin/admin_dashboard.html.

Sections:
- Header: cohort/date filter, "as of" time, reset
- Study Access card (READ-ONLY): state, changed_at, actor, "Manage" link to override
- Post-test Access card (READ-ONLY): same
- KPI row: active students, completed, matched pre/post sample, follow-up needed
- Charts, each with cohort + N + definition + paired table:
  - Matched pre/post gain
  - BKT mastery by skill
  - Q-Learning decisions by lesson (bar)
  - Median elapsed duration by stage
  - RAG reliability
- Follow-up preview table
- Audit preview table (last 10)

Do not: inline toggle. Doughnut for decisions. Remediation outcomes chart. Label duration only as "elapsed session time".

Exit: renders. No toggle. Every chart has paired table.

---

## Fix 4 — Teacher dashboard

Rebuild pages/teacher/teacher_dashboard.html.

Sections:
- Class selector (assigned only). Zero classes -> full empty state.
- KPI row: class size, completed, learning, follow-up needed
- Priority follow-up table BEFORE charts
- Charts with paired tables: BKT distribution, matched pre/post gain, Q-Learning decisions, completion distribution
- Roster preview

Do not: label duration as anything other than "elapsed session time". Line-join pretest and posttest aggregates.

Exit: renders. Empty states distinct from zero.

---

## Fix 5 — Student dashboard

Rebuild pages/student/student_dashboard.html.

Sections:
- Header: name. Class block omitted if no membership.
- Next Step card (dominant): from learning_student_path
- Learning path: 6 stages shown as a stepper. Pretest, Lesson 1, Lesson 2, Lesson 3, Activity, Posttest.
- Lesson count is exactly 3. Total stages is 6.
- Reached/completed state derived from learning_student_path and completed sessions.
- Six-skill progress: Needs Practice, Developing, and Strong bands. "Not enough evidence" not 0%.
- Your Next Focus: latest feedback_session_feedback.feedback_text
- Recent results: own completed sessions

Do not show raw p_known, reason codes, or model names.

Exit: renders. No raw probabilities.

---

## Fix 6 — Override + assessment + videos

Override (pages/admin/override.html):
- Study Access toggle switch
- Post-test Access toggle switch
- Each submit: reason (required) + revision
- Server: SELECT ... FOR UPDATE on core_system_setting. Stale revision -> 409.
- Every change writes one core_audit_event row.
- Post/Redirect/Get.

Assessment (assessment/assessment.html):
- One template for pretest, exercise, activity, posttest
- Render context decides labels, feedback rules, item count
- Pretest/posttest: no correctness until end
- Exercise/activity: immediate correctness
- Foundational: hint button
- Video cue pause wired: seek to segment_start_seconds, play to segment_end_seconds, then pause at video_pause_seconds during assessment.

Remove the four legacy assessment-type templates.

Videos:
- Real YouTube IDs and segment bounds from content_source/media_manifest.json.
- Each video reference carries segment_start_seconds and segment_end_seconds in JSON.
- curriculum_question.video_pause_seconds is the pause point (usually the segment end).
- Embed with youtube-nocookie.com/embed/<youtube_video_id>?start=<segment_start_seconds>&end=<segment_end_seconds>.
- Render title, duration, and a transcript link.
- During assessment, play from segment_start_seconds to segment_end_seconds, then pause and show the question.
- Do not fabricate URLs. Do not embed without a real youtube_video_id.

Figures:
- Lesson, exercise, and activity figures remain 1x1 transparent placeholders.
- Avatars and logo remain real committed files.
- Do not extract or replace lesson, exercise, or activity figures.
- Prompt-level figures only. Never on a choice.

Do not: use buttons for access toggles. Fabricate video URLs.

Exit: one assessment template. Toggles work. Videos embed. 409 on stale revision.

---

## Fix 7 — Login + modals

Login (pages/account/login.html):
- Standalone layout
- pathgen.png at top, ~64px
- Centered card, max-width 400px
- Clear labels
- Primary CTA uses var(--color-primary)
- Error region above form

Modals (24 files):
- Lucide icons
- Token colors
- Focus trap
- Escape closes (except destructive)
- Focus restore on close
- aria-label on each dialog

Exit: login renders with logo. Modals render, trap focus, close.

---

## Fix 8 — Accessibility + acceptance

Run:
- python manage.py test --settings=config.settings.test --noinput
- python manage.py check on local, test, production
- python manage.py makemigrations --check --dry-run

Verify:
- No hardcoded hex in templates
- No dark: utilities
- No prefers-color-scheme: dark
- No Impeccable, Preline, Geist
- No individual SVG icons
- Shared and per-page CSS files use the pure-CSS structure; no build step
- Every canvas has aria-label
- Every chart has paired <table>
- Every icon has aria-hidden="true"
- Keyboard reachable, focus visible, 44px touch targets
- 320px width works
- 200%/400% zoom works
- Full suite 250+ passing

Exit: all checks green. No regressions.

---

## Then Phase 15 — Deploy to Railway

Resume build_order.md Phase 15.

---

## Hard rules across all Fix phases

- No database schema changes. No new models. No migrations (except index-only).
- No changes to services, engines, orchestrator.
- No new Python or JS packages.
- No browser automation. No screenshots.
- No Impeccable. No Preline. No Geist.
- Only frontend_skill/SKILL.md for design.
- Light mode only. var(--color-*) tokens only.
- Pure CSS: shared `theme.css`, `shell.css`, `modals.css`, plus one stylesheet per page under `static/css/pages/`. CSS is edited directly and committed; no build step.
- Every chart paired with table. Empty states distinct from zero.
- Every phase ends with the full test suite passing.
- Stop after each Fix phase. Report. Wait.
