# pages.md

1 shared base, 19 pages, 4 components, 24 modals. Total: 48 templates.

---

## Folder structure

```text
templates/
|-- _base.html              (1 shared base)
|-- components/             (4 components)
|-- pages/
|   |-- admin/              (5 pages)
|   |-- teacher/            (3 pages)
|   |-- student/            (3 pages)
|   |-- shared/             (4 pages)
|   `-- account/            (2 pages)
|-- assessment/             (1 page)
|-- error/                  (1 page)
`-- modals/                 (24 dialogs)
```

## Base (1)

| Template | Purpose |
|---|---|
| `_base.html` | Shared `<head>`, `<body>`, meta, scripts, blocks. Every page extends this. |

`_base.html` includes:

- `<meta name="color-scheme" content="only light">` before CSS
- Semantic landmarks
- Skip-to-content link
- Visible focus ring
- Lucide library script
- Chart.js UMD script (only on pages that need it)
- `theme.css` and `shell.css` loaded globally
- Blocks: `{% block page_css %}`, `{% block shell %}`, `{% block content %}`

## Per-page CSS

Every page loads its own stylesheet from `static/css/pages/` through the base template's `{% block page_css %}`. Shared dialog styling lives in `modals.css`.

```html
{% extends "_base.html" %}
{% load static %}

{% block page_css %}
<link rel="stylesheet" href="{% static 'css/pages/admin_dashboard.css' %}">
{% endblock %}
```

The base template loads the shared stylesheets before that block:

```html
<link rel="stylesheet" href="{% static 'css/theme.css' %}">
<link rel="stylesheet" href="{% static 'css/shell.css' %}">
{% block page_css %}{% endblock %}
```

## Page types (rule, not file)

Four page types. A page type is a rule, not a file.

| Type | The page includes |
|---|---|
| main | `components/sidebar.html` + `components/hamburger_menu.html` |
| secondary | `components/breadcrumbs.html` only |
| focus | `components/back_link.html` |
| standalone | nothing shared |

Assignment:

| Type | Pages |
|---|---|
| main | `admin_dashboard`, `user_management`, `class_management`, `override`, `audit_logs`, `teacher_dashboard`, `my_class`, `student_dashboard`, `my_lesson`, `content`, `my_account` |
| secondary | `class_detail`, `view_lessons`, `view_questions`, `view_student_progress`, `lesson` |
| focus | `assessment`, `error` |
| standalone | `login` |

## Pages

### Admin (5)

| Page | Purpose |
|---|---|
| `pages/admin/admin_dashboard.html` | KPIs, research charts, follow-up preview, audit preview |
| `pages/admin/user_management.html` | Search, filter, create/update/deactivate users |
| `pages/admin/class_management.html` | Classes, teacher assignment, memberships |
| `pages/admin/override.html` | Only place to change Study Access and Post-test Access |
| `pages/admin/audit_logs.html` | Immutable audit history, read-only |

### Teacher (3)

| Page | Purpose |
|---|---|
| `pages/teacher/teacher_dashboard.html` | Class selector, priority follow-up table, charts |
| `pages/teacher/my_class.html` | List of assigned classes |
| `pages/teacher/class_detail.html` | One class roster and signals |

### Student (3)

| Page | Purpose |
|---|---|
| `pages/student/student_dashboard.html` | Next Step card, path, skills, feedback, results |
| `pages/student/my_lesson.html` | Vertical stepper through the whole course |
| `pages/student/lesson.html` | One lesson content page rendered as a designed reading experience |

### Shared (4)

| Page | Purpose |
|---|---|
| `pages/shared/content.html` | Read-only landing: Lessons, Questions |
| `pages/shared/view_lessons.html` | Browse 3 lessons, read-only |
| `pages/shared/view_questions.html` | Browse exercise/activity, excludes pre/post |
| `pages/shared/view_student_progress.html` | One student's full learning trail |

### Account (2)

| Page | Purpose |
|---|---|
| `pages/account/login.html` | Login form, generic errors |
| `pages/account/my_account.html` | Own name/password changes only |

### Assessment (1)

| Page | Purpose |
|---|---|
| `assessment/assessment.html` | One template for pretest, exercise, activity, posttest. Render context decides labels, feedback rules, item count. |

### Error (1)

| Page | Purpose |
|---|---|
| `error/error.html` | 400, 403, 404, 409, 500 safe page |

## Components (4)

| Component | Purpose |
|---|---|
| `components/sidebar.html` | Role-aware navigation. Logo top. Avatar + name bottom. |
| `components/hamburger_menu.html` | Mobile drawer with focus trap. |
| `components/breadcrumbs.html` | Home > Section > Page trail. |
| `components/back_link.html` | Back to parent link. |

Rule: only create a component if it is used 2+ times.

## Modals (24)

The existing 24 modal files and their directory structure remain unchanged.

| Group | Count | Purpose |
|---|---:|---|
| Shared | 1 | Generic confirmation |
| Users | 6 | User lifecycle |
| Classes | 8 | Class lifecycle and membership |
| Account | 2 | Own name and password |
| Audit | 1 | Read-only event detail |
| Auth | 1 | Logout confirmation |
| Assessment | 1 | Exit confirmation |
| Overrides | 4 | Access-setting confirmations |

Rule: consequential actions end `_confirm.html`. Never `ok.html` or `confirm.html`.

## Responsive behavior

| Key | Min width |
|---|---|
| base | < 475px |
| xs | 475px |
| sm | 640px |
| md | 768px |
| lg | 1024px |
| xl | 1280px |
| 2xl | 1536px |

| Size | Layout |
|---|---|
| base | Single column. Filters behind disclosure. Tables become cards. |
| sm | Two-column KPIs. Priority table stays first. |
| md | Charts beside tables. |
| lg+ | Multi-column grid. Content width bounded. |

Test at 320px width and at 200% and 400% zoom.

## Light mode and accessibility

- Every page extends `_base.html`.
- No `.dark` class, `dark:` utilities, `prefers-color-scheme: dark`, or theme switcher.
- Components use `var(--color-*)` tokens. Never raw hex.
- Use semantic landmarks, a skip link, visible focus, and 44px minimum touch targets.
- Status is never color-only. Every chart has a paired table.
- Figures have alt text. Videos have captions and transcript links.
- Dialogs have an accessible name, trap focus, restore focus, and make the background inert.
- Escape closes dialogs except destructive confirmations.

## Summary

| Category | Count |
|---|---:|
| Base | 1 |
| Pages | 19 |
| Components | 4 |
| Modals | 24 |
| Total | 48 |
