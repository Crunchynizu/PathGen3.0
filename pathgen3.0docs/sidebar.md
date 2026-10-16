# sidebar.md

Navigation for PathGen 3.0. All roles, all destinations.

---

## Purpose

Defines the sidebar structure and secondary navigation for each role. Every destination, every scope.

---

## Shared behavior

Sidebar is `components/sidebar.html`. Icons are Lucide. Active link uses `aria-current='page'` and `var(--color-primary)`.

Navigation uses the reference `.sidebar` and `.nav-item` class names. `shell.css` styles the Lucide icons through `.nav-item svg`; templates use `<i data-lucide="name" aria-hidden="true"></i>`.

| Rule | Detail |
|---|---|
| Sidebar groups | MAIN and ACCOUNT |
| Desktop | Persistent or collapsible sidebar |
| Mobile | Focus-managed drawer |
| Current page | `aria-current="page"` |
| Icons | Decorative, with visible text labels |
| Keyboard order | Matches visual order |
| Escape | Closes drawer |
| Focus return | Returns to drawer opener |
| Zoom | Works at 320px+ width |
| Active assessment | Sidebar suppressed, replaced by focused nav |
| Logout | Confirms via modal, CSRF-protected POST |

Authorization is enforced on routes, not by hiding links.

---

## Admin

### MAIN

| Label | Destination | Scope |
|---|---|---|
| Dashboard | `pages/admin/admin_dashboard.html` | KPIs, research charts, follow-up, audit preview |
| Users | `pages/admin/user_management.html` | Account lifecycle for teachers + students |
| Classes | `pages/admin/class_management.html` | Classes, teacher assignment, memberships |
| Students | `pages/admin/student_list.html` | Search and filter students, open scoped progress |
| Content | `pages/shared/content.html` | Read-only Lessons and Questions |
| Overrides | `pages/admin/override.html` | Study Access, Post-test Access |
| Audit Logs | `pages/admin/audit_logs.html` | Immutable event history |

### Content secondary pages

| Page | Purpose |
|---|---|
| `pages/shared/view_lessons.html` | 3 lessons, ordered, 2 skills each |
| `pages/shared/view_questions.html` | Exercise + activity, pre/post excluded |

### Contextual links

| Link | Opens |
|---|---|
| Dashboard row → student | `pages/shared/view_student_progress.html` |
| User row → progress | `pages/shared/view_student_progress.html` |
| Class row → student | `pages/shared/view_student_progress.html` |

Not in sidebar. Reached through rows.

### ACCOUNT

| Label | Destination |
|---|---|
| My Account | `pages/account/my_account.html` |
| Logout | `modals/auth/logout_confirm.html` |

---

## Teacher

### MAIN

| Label | Destination | Scope |
|---|---|---|
| Dashboard | `pages/teacher/teacher_dashboard.html` | Class selector, follow-up first, then charts |
| My Classes | `pages/teacher/my_class.html` | List of assigned classes |
| Content | `pages/shared/content.html` | Read-only Lessons and Questions |

### Contextual links

| Link | Opens |
|---|---|
| Class → detail | `pages/teacher/class_detail.html` |
| Student → progress | `pages/shared/view_student_progress.html` |

Not in sidebar.

### ACCOUNT

| Label | Destination |
|---|---|
| My Account | `pages/account/my_account.html` |
| Logout | `modals/auth/logout_confirm.html` |

Teachers cannot mutate users, classes, or settings.

---

## Student

### MAIN

| Label | Destination | Scope |
|---|---|---|
| Dashboard | `pages/student/student_dashboard.html` | Next Step, path, skills, feedback, results |
| My Lesson | `pages/student/my_lesson.html` | Vertical stepper through the course |

### Reached from My Lesson

| Link | Opens |
|---|---|
| Lesson Content | `pages/student/lesson.html` |
| Regular Exercise | `assessment/assessment.html` |
| Additional Exercise | `assessment/assessment.html` (only if assigned) |
| Foundational Exercise | `assessment/assessment.html` (only if assigned) |
| Pretest | `assessment/assessment.html` |
| Activity | `assessment/assessment.html` |
| Post-test | `assessment/assessment.html` |

### ACCOUNT

| Label | Destination |
|---|---|
| My Account | `pages/account/my_account.html` |
| Logout | `modals/auth/logout_confirm.html` |

Locked Post-test stays in My Lesson as an unavailable step. Never routed to error page.

---

## Standalone pages (no sidebar)

| Page | Why |
|---|---|
| `pages/account/login.html` | Pre-auth |
| `error/error.html` | Exceptional failure |
| `assessment/assessment.html` | Focused shell replaces sidebar for all assessment types |

Assessment pages show: PathGen identity, question number/progress, exit action. No navigation links.

---

## Role comparison

| Destination | Admin | Teacher | Student |
|---|---|---|---|
| Dashboard | ✅ | ✅ | ✅ |
| Users | ✅ | ❌ | ❌ |
| Classes | ✅ | ❌ | ❌ |
| Students | ✅ | ❌ | ❌ |
| My Classes | ❌ | ✅ | ❌ |
| My Lesson | ❌ | ❌ | ✅ |
| Content | ✅ | ✅ | ❌ |
| Overrides | ✅ | ❌ | ❌ |
| Audit Logs | ✅ | ❌ | ❌ |
| My Account | ✅ | ✅ | ✅ |
| Logout | ✅ | ✅ | ✅ |

---

## Sidebar visual pattern

```
┌─────────────────────────┐
│  [PathGen logo + name]  │
│                         │
│  MAIN                   │
│  • Dashboard            │
│  • Users / My Classes   │
│  • ...                  │
│                         │
│  ACCOUNT                │
│  • My Account           │
│  • Logout               │
│                         │
│  [user avatar + name]   │
└─────────────────────────┘
```

Width: 240px on desktop. Collapses on smaller screens into a drawer.

---

## Mobile behavior

| Screen | Behavior |
|---|---|
| < 1024px | Sidebar hidden, hamburger button opens drawer |
| Drawer open | Focus trapped, background inert |
| Escape | Closes drawer |
| Tap outside | Closes drawer |
| Focus on close | Returns to hamburger button |
| Assessment pages | No drawer at all |

---

## Accessibility

- Every link keyboard reachable
- Visible focus ring on every link
- `aria-current="page"` on active page
- Icons have `aria-hidden="true"`
- Text labels always visible (not icon-only)
- Drawer traps focus while open
- Escape closes drawer
- Focus returns to opener after close
- Works at 320px width
- Works at 200% and 400% zoom

---

## Summary

| Role | MAIN items | Account items |
|---|---|---|
| Admin | 7 | 2 |
| Teacher | 3 | 2 |
| Student | 2 | 2 |

Every role has a Dashboard and My Account. Everything else is role-specific.

---

**End of reference.**
