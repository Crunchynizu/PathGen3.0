# revamp_baby.md

Finish the PathGen UI revamp under pure CSS. Replaces the Tailwind-based
approach used in R1–R6 and abandoned before completion. Runs before
Phase 15.

---

## Purpose

`revamp_ui.md` planned the revamp with Tailwind utilities. The reference
`frontend/` files are pure CSS with `<style>` blocks. Translating custom
CSS values into Tailwind's scale rounds every number and loses fidelity.
The rendered output does not match the reference.

`revamp_baby.md` switches to pure CSS. Every page links its own `.css`
file, copied nearly verbatim from the corresponding `frontend/` file.
Class names in the template match class names in the reference. Shared
components live in `theme.css`, shell layout in `shell.css`, and dialog
styling in `modals.css`.

The visual outcome is a per-page CSS file that reproduces the reference
exactly, plus a template that uses the reference's own class names.

---

## What changes

- **Tailwind removed entirely.** No `input.css`, no `tailwind.config.js`,
  no `tools/tailwindcss.exe`, no `app.css`, no build step.
- **`theme.css`** holds design tokens, base element styles, and shared
  component classes (`.card`, `.badge`, `.btn`, `.table`, `.chip`,
  `.stat`, `.empty`, `.filter-bar`, `.pagination`, etc.).
- **`shell.css`** holds the four shell layouts: main (sidebar +
  hamburger), secondary (breadcrumbs), focus (back link), standalone.
- **`modals.css`** holds all dialog styling. Every modal links the same
  file.
- **Per-page CSS.** Each HTML page links its own `.css` file from
  `static/css/pages/`.
- **Reference class names used verbatim.** If the reference says
  `.sidebar`, `.nav-item`, `.lesson-card`, the template uses those
  exact names. No renaming, no mapping.
- **No build step.** CSS files are edited directly and committed.

---

## File structure

```
static/css/
├── theme.css                    tokens, base, shared components
├── shell.css                    sidebar, hamburger, breadcrumbs, back_link
├── modals.css                   all dialog CSS
└── pages/
    ├── admin_dashboard.css
    ├── user_management.css
    ├── class_management.css
    ├── student_list.css
    ├── override.css
    ├── audit_logs.css
    ├── teacher_dashboard.css
    ├── my_class.css
    ├── student_dashboard.css
    ├── my_lesson.css
    ├── lesson.css
    ├── content.css
    ├── view_class_detail.css
    ├── view_lesson.css
    ├── view_lesson.detail.css
    ├── view_questions.css
    ├── view_student_progress_detail.css
    ├── my_account.css
    ├── login.css
    ├── assessment.css
    └── error.css
```

**Total CSS files: 25** (theme + shell + modals + 21 page files).

---

## How each page loads CSS

`_base.html` loads `theme.css` and `shell.css` globally, plus a
per-page CSS block:

```html
{% load static %}
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="only light">
  <title>{% block title %}PathGen{% endblock %}</title>

  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:opsz,wght@14..32,400;500;600;700&display=swap">

  <link rel="stylesheet" href="{% static 'css/theme.css' %}">
  <link rel="stylesheet" href="{% static 'css/shell.css' %}">
  {% block page_css %}{% endblock %}
</head>
<body data-role="{{ user.role }}">
  {% block shell %}{% endblock %}
  {% block content %}{% endblock %}
</body>
</html>
```

Each page:

```html
{% extends "_base.html" %}
{% load static %}

{% block page_css %}
<link rel="stylesheet" href="{% static 'css/pages/admin_dashboard.css' %}">
{% endblock %}
```

---

## Styling rules

### Breakpoints

Use this exact mobile-first set in every CSS file. No custom widths
unless a specific reference requires one, in which case it is documented
and flagged.

```css
/* base — under 475px */
/* xs */
/* @media (min-width: 475px) {} */

/* sm */
/* @media (min-width: 640px) {} */

/* md */
/* @media (min-width: 768px) {} */

/* lg */
/* @media (min-width: 1024px) {} */

/* xl */
/* @media (min-width: 1280px) {} */

/* 2xl */
/* @media (min-width: 1536px) {} */
```

### Colors

Every color comes from `theme.css` as a CSS variable. No hardcoded hex
in page files, `shell.css`, or `modals.css`. If a page needs a value
that is not yet a token, add the token to `theme.css` first — do not
inline the hex.

### Class names

Reference names used verbatim. If the reference calls it
`.lesson-card`, the template and CSS use `.lesson-card`. No renaming.

### Icon approach

Lucide self-hosted. No individual SVG files. Use:

```html
<i data-lucide="icon-name" aria-hidden="true"></i>
```

Call `lucide.createIcons()` after DOM ready.

### Charts

Chart.js self-hosted UMD. Every canvas has `aria-label` and a paired
server-rendered `<table>` with the same data. Chart color values that
are not tokens are set via CSS variables read in the chart options, not
hardcoded in JS.

### Light mode only

`<meta name="color-scheme" content="only light">` in `_base.html`. No
`.dark` class. No `dark:` variants. No `prefers-color-scheme: dark`.

---

## Rolling back R1–R6

Two options. Decide at RB0 before any code is written.

### Option A — Targeted rollback (recommended)

Keep the architecture work. Revert only the visual layers written with
Tailwind.

**Keep:**
- R1 tokens in `theme.css` (design tokens are architecture-neutral)
- R2 `_base.html` move and shell block definitions
- R4 moves and renames (view_class_detail, view_lesson, view_student_progress_detail)
- R5 routes, views, sidebar Students item

**Revert:**
- R3 components rewritten in pure CSS (`shell.css`)
- R5 `student_list.html` visual layer rewritten
- R6 admin page visual layer abandoned

**Delete:**
- `input.css`
- `tailwind.config.js`
- `tools/tailwindcss.exe`
- `static/css/app.css`

### Option B — Full rollback

Reset the repo to the state before R1. Redo every phase in pure CSS.

**Cost:** everything R1–R5 accomplished is lost — tokens, base move,
moves/renames, new pages, sidebar fix.

**Benefit:** no Tailwind residue anywhere, cleaner diff history.

**Recommendation:** Option A. The R1 tokens are valid under pure CSS.
R2's `_base.html` is architecture, not Tailwind. R4's moves/renames are
pure path changes. Only R3 and R6's visual work is Tailwind-bound.

---

## Phases

Each phase is one reviewable change set. Stop and report after each.
Each exit includes the full Django suite passing. Do not start any
phase until the prior one is complete and reviewed.

### RB0 — Rollback decision

- Confirm Option A or Option B.
- If B, reset the branch to the pre-R1 commit.
- If A, proceed to RB1 with the current tree.

**Exit:** decision recorded in the commit message or a note.

### RB1 — Docs revision (no code)

Remove every Tailwind reference from the specs. Update:

- `tech_stack.md` — remove Tailwind, input.css, tailwind.config.js,
  tools/tailwindcss.exe, app.css. Add: pure CSS, per-page files,
  shell.css, modals.css. Remove the "standalone Tailwind CLI" line.
- `build_order_must.md` — Fix 1 ("input.css is 3 lines") is void.
  Rewrite. Remove the Tailwind CLI rebuild step from every Fix phase.
- `overview.md` — remove "Tailwind via standalone CLI" from the stack
  table and any other mention.
- `folder_structure.md` — update `static/css/` to the new tree.
- `AGENTS.md` — remove Tailwind from allowed and forbidden lists.
- `pages.md` — add the per-page CSS block pattern.
- `revamp_ui.md` — add a "Strategy override" note pointing here.
- `sidebar.md` — update icon description from Tailwind utilities to CSS.
- `dashboard.md`, `user_features.md`, `user_flows.md`,
  `authentication.md` — scan and remove any Tailwind mention.

**Exit:** `grep -ri tailwind ../pathgen3.0docs/` returns zero matches
in the ten docs above. Full suite green (docs changes do not affect
tests).

### RB2 — Tailwind removal and base swap

- Delete `input.css`, `tailwind.config.js`, `tools/tailwindcss.exe`,
  `static/css/app.css`.
- Update `_base.html`:
  - Load `theme.css` and `shell.css` globally.
  - Add `{% block page_css %}`.
  - Remove `app.css` link.
- Update every page template: add `{% block page_css %}` with its own
  CSS path.
- Update tests that assert on `app.css` or Tailwind class names.

**Exit:** no reference to Tailwind or `app.css` in any file. Every page
renders with `theme.css` and `shell.css` only. Full suite green.

### RB3 — Components in pure CSS

Extract CSS from `frontend/main.html`, `secondary.html`, `focus.html`,
`standalone.html` into `shell.css`. Rewrite the four components
(`sidebar.html`, `hamburger_menu.html`, `breadcrumbs.html`,
`back_link.html`) to use the reference class names.

**Reference:** `frontend/main.html`, `secondary.html`, `focus.html`,
`standalone.html`.

**Exit:** shell components match their reference at all breakpoints.
`app.js` still handles drawer, focus trap, breadcrumb scroll, back-link
Escape. Full suite green.

### RB4 — New pages in pure CSS

Rewrite `student_list.html` and `view_lesson.detail.html` with pure CSS
and reference class names. Extract their CSS from
`frontend/student_list.html` and `frontend/view_lesson_details.html`.

**Reference:** `frontend/student_list.html`,
`frontend/view_lesson_details.html`.

**Exit:** both pages match their references. Routes, views, and scope
unchanged. Full suite green.

### RB5 — Admin pages

Extract CSS from the five `frontend/` admin files into their
`static/css/pages/*.css` counterparts. Rewrite the templates to use
reference class names.

**Reference:** `frontend/admin_dashboard.html`,
`frontend/user_management.html`, `frontend/class_management.html`,
`frontend/overrides.html`, `frontend/audit_logs.html`.

**Also fix:** lesson index link from `view_lesson.html` to each lesson
detail page.

**Exit:** all five admin pages match their references. Every dynamic
value comes from Django context — zero hardcoded demo values. Outer
padding unified across main-shell pages. Per-page max-widths preserved.
Full suite green.

### RB6 — Teacher pages

**Reference:** `frontend/teacher_dashboard.html`,
`frontend/my_classes.html`.

**Exit:** both pages match their references. Assigned-class scoping and
empty states unchanged. Full suite green.

### RB7 — Student pages

**Reference:** `frontend/student_dashboard.html`,
`frontend/my_lessons.html`, `frontend/lesson.html`.

**Exit:** all three pages match their references. Six stages, three
lessons, locked states correct. No raw p_known exposed. Full suite
green.

### RB8 — Assessment

**Reference:** `frontend/assessment.html`, `frontend/focus.html`.

**Exit:** assessment matches reference at every state. Pre/post secrecy,
immediate exercise feedback, hint states, media states, submitted lock
all unchanged. Full suite green.

### RB9 — Login and error

**Reference:** `frontend/login.html`, `frontend/error.html`.

**Exit:** both pages match their references. Generic auth errors, safe
error links, no remote prototype image, background asset verified
before login parity is marked complete. Full suite green.

### RB10 — Modals

Extract dialog CSS from `frontend/modals.html` into `modals.css`.
Rewrite every modal template to use reference class names.

**Before editing:** reconcile the inventory.

- Current tree has **24 modal files.**
- `frontend/modals.html` shows **25 dialog examples.**
- The delta is 3 reference-only dialogs (reset_password,
  reset_sessions, unassign_teacher) and 2 app-only files
  (user_detail, delete_class_confirm).

Do not invent a 25th file. Do not rename existing files. Report the
delta and await authorization before adding any new dialog, route, or
service.

**Exit:** every existing modal matches `frontend/modals.html` anatomy.
Inventory reconciled and reported. Focus trap, focus restore, CSRF,
destructive behavior all verified. Full suite green.

### RB11 — Final check

- Full Django test suite.
- `manage.py check` on local, test, production.
- `makemigrations --check --dry-run` — no drift.
- Static scan for hardcoded hex outside `theme.css`, for any Tailwind
  class remnants, for CDN references, for inline `<style>`.
- Path scan for old template paths.
- Doc re-verification — no stale Tailwind language.
- User-led browser QA on every page against its `frontend/` reference
  at every breakpoint.

**Exit:** all checks pass. User accepts visual parity. Stop before
Phase 15.

---

## Hard rules

- No Tailwind. No `input.css`. No `tailwind.config.js`. No
  `tools/tailwindcss.exe`. No `app.css`. No build step.
- Reference class names used verbatim.
- Colors come from `theme.css` tokens. No hardcoded hex outside
  `theme.css`.
- Breakpoints: base, xs 475, sm 640, md 768, lg 1024, xl 1280,
  2xl 1536. Only these unless a specific reference proves otherwise.
- Lucide self-hosted. No individual SVG files.
- Chart.js self-hosted UMD. Every canvas has a paired table.
- Light mode only.
- No CDN for JS or CSS. Only permitted remote asset is Inter via
  Google Fonts.
- No new models, migrations, services, or engines in any RB phase.
- No hardcoded demo values in templates. Every dynamic value comes
  from Django context.
- Every phase stops and reports. Nothing rolls forward unattended.

---

## What not to do

- Do not re-add Tailwind in any form.
- Do not use `@tailwind` directives.
- Do not rebuild `app.css`.
- Do not use arbitrary-value class names (`p-[16px]` etc.) — that was
  the Tailwind workaround. In pure CSS, write the exact value.
- Do not rename reference class names to something "cleaner."
- Do not skip a phase or merge two phases.
- Do not start Phase 15 until RB11 passes and the user accepts visual
  parity.

---

## After RB11

Resume `build_order.md` Phase 15 — Deploy to Railway.

---

**End of revamp_baby.md.**
