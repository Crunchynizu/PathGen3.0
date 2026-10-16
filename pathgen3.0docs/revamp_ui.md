# PathGen UI revamp plan — before Phase 15

## Strategy override

The Tailwind approach in this plan is superseded by the pure-CSS approach in `revamp_baby.md`. Follow that spec for RB0–RB11; the existing plan below remains historical context.

**Status:** analysis and plan only. No revamp phase has begun. `../pathgen3.0docs/frontend/` is the **final look**. Every rendered PathGen page must be visually indistinguishable from its corresponding detailed `frontend/` page, including responsive states and interactions. Static example content becomes real Django data and links; implementation uses the approved stack.

## Evidence read and precedence

- All **25 files** under `frontend/` were inventoried and analyzed; there are no nested files or directories: `admin_dashboard.html`, `assessment.html`, `audit_logs.html`, `class_detail.html`, `class_management.html`, `content.html`, `error.html`, `focus.html`, `lesson.html`, `login.html`, `main.html`, `modals.html`, `my_account.html`, `my_classes.html`, `my_lessons.html`, `overrides.html`, `secondary.html`, `standalone.html`, `student_dashboard.html`, `student_list.html`, `teacher_dashboard.html`, `user_management.html`, `view_lesson_details.html`, `view_lesson.html`, `view_questions.html`.
- Read `build_order_must.md`, `pages.md`, `sidebar.md`, `folder_structure.md`, `dashboard.md`, `user_features.md`, `user_flows.md`, `authentication.md`, `tech_stack.md`, `overview.md`, app `AGENTS.md`, and `frontend_skill/SKILL.md`.
- Read and inventoried every current `templates/` file, plus `static/css/theme.css`, generated `static/css/app.css`, `static/js/app.js`, `static/js/lesson.js`, `input.css`, and `tailwind.config.js`. The docs asset `assets/css/theme.css` currently has the same hash as the app `theme.css`.
- **Missing at the requested reference path:** `content/logo/login_background.jpg` does not exist in either the workspace docs tree or the sibling docs copy checked. The docs logo directory contains only `pathgen.png`. A **pre-existing, untracked** app file exists at `pathgen3.0app/static/logo/login_background.jpg`; it was inspected read-only and depicts students raising hands in a classroom, with a chalkboard on the left and brighter windows on the right. It may be the intended photo, but its provenance relative to the missing docs source is unverified. `frontend/login.html` displays a remote Picsum placeholder and comments about another replacement path. Verify that the app image is the approved target before claiming image-specific login parity; do not use Picsum in PathGen.
- The five generic files (`main`, `secondary`, `focus`, `standalone`, `modals`) establish shell and component behavior. The **20 detailed page examples** control their corresponding page composition when they differ from a generic sample. `tech_stack.md` controls implementation method; the detailed `frontend/` file controls visual result. Static prototype controls and fake URLs are not product requirements.

## 1. Modal inventory and discrepancy

The current app has **24 modal template files**, not 25. This is a direct filesystem count. `pages.md` and `build_order_must.md` also document 24, with groups totaling 24. No existing file can be identified as the claimed new or renamed twenty-fifth modal. Preserve these exact existing filenames:

| Group | Count | Current files under `templates/modals/` |
|---|---:|---|
| Account | 2 | `account/update_name.html`, `account/update_password.html` |
| Assessment | 1 | `assessment/exit_assessment_confirm.html` |
| Audit | 1 | `audit/audit_detail.html` |
| Auth | 1 | `auth/logout_confirm.html` |
| Classes | 8 | `classes/add_student_class.html`, `classes/archive_class_confirm.html`, `classes/assign_teacher_class.html`, `classes/create_class.html`, `classes/delete_class_confirm.html`, `classes/reactivate_class_confirm.html`, `classes/remove_student_class_confirm.html`, `classes/update_class.html` |
| Overrides | 4 | `overrides/close_study_access_confirm.html`, `overrides/lock_posttest_confirm.html`, `overrides/open_study_access_confirm.html`, `overrides/unlock_posttest_confirm.html` |
| Shared | 1 | `shared/generic_confirm.html` |
| Users | 6 | `users/create_user.html`, `users/deactivate_user_confirm.html`, `users/delete_user_confirm.html`, `users/reactivate_user_confirm.html`, `users/update_user.html`, `users/user_detail.html` |

`frontend/modals.html` contains **25 actual `<dialog>` examples**, including seven user dialogs. The reference adds **Reset password** (`users/reset_password_confirm.html` in its launcher label: an admin sets a new password and invalidates sessions) and **Reset active sessions** (`users/reset_sessions_confirm.html`: invalidate sessions without changing the password). Its class examples include **Unassign teacher** (`classes/unassign_teacher_confirm.html`). Conversely, the app has `users/user_detail.html` and `classes/delete_class_confirm.html`, which are not among those 25 reference launcher labels. The launcher labels are prototype names and differ from several real filenames, so they cannot establish a reliable rename map. The existing `assign_teacher` view can already clear a teacher through its service, but no separate unassign modal file exists; reset-password and reset-sessions routes/services are not present. Consequently, **there is no evidence for one specific “new or renamed” current file**. Treat “25 files, names unchanged” as an unresolved input conflict, not permission to invent a file, route, service, or destructive action. Before R11, reconcile the expected inventory and purpose with the owner, then update the plan and inventory assertion to the verified count. R11 must cover every actual file and all applicable reference dialog states.

## 2. Visual target

### Shared visual language and exact measurements

- Light, cool near-white system. White canvas `#ffffff`; subtle surface `#f8fafb`; thin cool-gray borders `#dfe4e8` / stronger `#c7cfd6`; near-black headings `#15181b`; secondary text `#57626d`; muted text `#74808d`. Cyan `#0cc0df` is decoration and large icon fill. Interactive cyan is `#0a9db8`, hover `#087b90`, active `#0a5f6f`; small cyan text uses `#0A8298`. Success, warning, and danger use the exact current theme bases (`#1fa860`, `#e6a319`, `#e0403f`) and their pale backgrounds (`#e5f7ee`, `#fdf3df`, `#fbe7e6`). Status text is darker than its icon/fill.
- Inter throughout. Reference root type scale: 12, 14, 16, 18, 20, 24, 32 px (`--text-xs` through `--text-3xl`); detailed pages also use 11–13 px for chart metadata/table density, 36 px secondary desktop titles, and 40–48 px login image headline. Typical weights are 400 body, 500 navigation/form labels, 600 card titles/buttons, 700 page and hero headings. Body leading 1.5; reading text up to 1.7; large headings 1.2 or 1.1. Page headings track about `-0.02em`; smaller card headings about `-0.005` to `-0.015em`; uppercase section labels track `0.05`–`0.08em`. Do not apply one tracking value globally.
- Repeated geometry: 4/8/12 px radii (`--radius-sm/md/lg`), 1 px borders, very light `--shadow-sm` (`0 1px 2px rgba(21,24,27,.06)`) and `--shadow-md` (`0 4px 10px rgba(21,24,27,.08)`). Common gap rhythm is 4, 6, 8, 10, 12, 14, 16, 18, 20, 24, 28, 32 px, with 40/48/56/64/80/96/120 px used for page spacing. Use each detailed page’s measurements; these are observed values, not a license to normalize unlike pages.
- Main shell: fixed **240 px** sidebar at `lg` and above; off-canvas mobile sidebar with 44×44 px fixed hamburger at top/left 16 px. Mobile drawer has translucent white (`rgba(255,255,255,.7)`) and a dark scrim; desktop sidebar is opaque `--color-bg-subtle`. Sidebar header padding **16px 12px 12px 16px**, nav padding **4px 10px 10px**, footer **10px**. Brand mark 28 px, nav icons 16 px, avatar 32 px. Nav items have 8×10 px padding, 8 px radius, 14 px/500 text, subtle hover, pale-cyan active fill and darker-cyan text, with `aria-current="page"`. MAIN and ACCOUNT headings are small uppercase labels. Brand stays top and avatar/name/role footer stays bottom.
- Main content is centered within the remaining viewport; generic sample is max 720 px, but detailed pages intentionally vary: admin/teacher dashboard and class detail **1160**, class management and student list **1100**, my classes **1000**, user management **960**, audit **900**, questions **860**, content/student dashboard **780**, overrides **760**, my lesson/my account **720** px. Typical mobile main padding is **80px 20px 96px**, dropping to about **48px 32px 96px** beside the desktop sidebar. No blanket max-width should erase page-specific widths.
- Secondary shell: no sidebar. Sticky translucent breadcrumb bar, horizontal nonwrapping trail, Lucide 12 px chevrons, soft scroll-edge divider only when scrolled. Generic breadcrumb/content max **720 px**; detailed pages use 720/780/860/1160 px to align with their content. Content generally has **40px 20px 96px** mobile padding and **56px 32px 120px** desktop in the generic example. Detailed lesson reader is narrower (about 65 characters) within its page column.
- Focus shell: only a compact back/exit control in a sticky, translucent top bar. Question content max about **720 px**, centered, with progress track, prompt, choices and right-aligned action row. No sidebar or breadcrumbs. Error page uses the same focus structure with centered icon, status code, explanatory text, and two actions.
- Standalone shell: no shared navigation. The generic `standalone.html` has a centered, 400 px login card, but detailed `login.html` takes precedence: a full-height split layout at `md`, image left and form right. The image is absent on narrow screens and the brand shifts above the form. If the inspected classroom photo is approved, use `object-fit: cover` and crop it so raised hands/chalkboard remain legible under the `--primary-900` vertical overlay; verify the focal crop at each login breakpoint.
- Cards have white fill, cool-gray hairline border, 12 px radius, light shadow and usually 16–24 px internal padding. Dense chart cards use 16×18 px headers/body. Tables use restrained row dividers, small uppercase heads, left-aligned labels, tabular numbers and responsive overflow/card treatment. Chart.js canvases require paired server-rendered data tables and explicit empty/error states; a zero is not an empty state.
- Native `<dialog>` reference: width `min(440px, 100vw - 32px)`, max-height `100dvh - 32px`, 12 px radius, two-layer shadow `0 24px 64px rgba(21,24,27,.18), 0 4px 16px rgba(21,24,27,.08)`. Backdrop is `rgba(21,24,27,.4)` with 4 px blur. Header padding **20px 20px 12px**, fields **8px 20px 16px** with 14 px gap, and pale-gray bordered action row **12px 20px** with 8 px gap. Titles 18 px/600, descriptions 14 px/1.5. Open enters over 280 ms from +8 px / 0.97 scale; close exits over 160 ms toward +4 px / 0.98 scale. Inputs show a pale cyan 3 px focus halo. Destructive dialogs use pale red warning blocks and danger action; they reject casual Escape/backdrop close. Restore focus, trap focus, preserve form/CSRF behavior, honor reduced motion.
- Interactions have immediate pressed feedback, subtle hover elevation/tint, visible keyboard focus, pointer cancellation, reduced-motion and reduced-transparency variants. Mobile drawer drag/edge-swipe behavior and dialog animation may use small vanilla JS helpers in `app.js` where needed. Reproduce the observed interaction, not the prototype’s inline JS verbatim.

### Detailed reference-to-template map

| Reference | Target template(s) and distinguishing visual features |
|---|---|
| `main.html` | Shared main shell: persistent/sidebar drawer, groups, brand, user footer, hamburger, panels, active/hover states. Prototype role switcher is omitted. |
| `secondary.html` | Shared secondary shell: sticky breadcrumb strip, 720 px reading example, soft scroll edge. |
| `focus.html` | Shared focus shell: sole back/exit link, progress, large prompt and stacked answer choices. |
| `standalone.html` | Generic standalone principles; `login.html` provides actual login layout. |
| `modals.html` | Native dialog geometry, fields, warnings, action rows, animations and 25 example states; launcher page is omitted. |
| `admin_dashboard.html` | Admin dashboard: access-state cards, KPI row, five research chart sections and paired tables, follow-up and audit previews, cohort/date controls; 1160 px content. |
| `user_management.html` | Admin user list: search and filters, responsive dense rows, lifecycle badges/actions and user dialogs; 960 px content. |
| `class_management.html` | Admin classes: search/filter, class rows, membership/teacher controls and confirmation dialogs; 1100 px content. |
| `student_list.html` | New admin-wide student page: filter/search bar, student avatar rows, status/skill chips, actions, empty state and pagination; 1100 px content. |
| `overrides.html` | Two access-setting cards with warning notice, state dot, actor/timestamp metadata, switch-like control and reason/revision confirmations; 760 px content. |
| `audit_logs.html` | Read-only event rows, filter panel, state icons and details dialog; 900 px content. |
| `teacher_dashboard.html` | Assigned-class selector, priority follow-up table before KPI/charts, paired tables, roster preview and distinct zero-class state; 1160 px content. |
| `my_classes.html` | Teacher class list: bordered row cards, role/status chips and generous full empty state; 1000 px content. |
| `class_detail.html` | Shared class detail for admin/teacher: breadcrumbs, class metadata, expandable analysis/charts with tables, roster card and scoped links; 1160 px content. |
| `student_dashboard.html` | Student hero next-step card, six-stage path, six skill bands, next-focus feedback, recent results, closed-access policy banner; 780 px content. |
| `my_lessons.html` | Vertical six-stage learning rail with completed/current/available/locked nodes, cards, substeps and lock reasons; 720 px content. |
| `lesson.html` | Student lesson reader: breadcrumbs and reading progress, objectives, 65ch prose, check/numbered lists, math, figure/video, worked-example and mistake cards, ready-to-practice CTA. |
| `content.html` | Read-only content landing: two destination cards for Lessons and Questions and their counts; 780 px content. |
| `view_lesson.html` | Shared three-lesson index: number/skill chips, objectives and CTA cards; 780 px secondary content. |
| `view_lesson_details.html` | New shared full lesson reader: detailed objectives, rich lesson sections, linked question sets and prev/next; 780 px secondary content. |
| `view_questions.html` | Shared question-set browser: filters, code/skill/type/Bloom metadata, prompts, media references, four choices, explanations/hints and empty state; 860 px content. Protected pre/post items remain excluded. |
| `assessment.html` | Focus assessment: one-at-a-time question, progress bar, optional media/hint, answer locking, immediate feedback where permitted, exit dialog and completion states. |
| `my_account.html` | Main account page: identity/avatar card, account and security rows, update-name/password dialogs; 720 px content. |
| `login.html` | Actual standalone login: photo/brand/caption left, plain form right, generic error above fields and password visibility control. |
| `error.html` | Focus failure page for 400/403/404/409/500: icon, code, message, context-safe actions; preview switcher and fake reference generator are omitted. |

`frontend/` has no separate `view_student_progress_detail.html` visual file. Use its secondary shell and the closest detailed research/skill patterns from `class_detail.html`, `student_dashboard.html`, and dashboard examples while retaining its documented data and authorization. This is the one page without a direct one-to-one detailed prototype; record its final manual parity decision explicitly.

### Responsive and accessibility behavior

| Width/state | Reference behavior to reproduce |
|---|---|
| Base below 475 px, including 320 px | One column, fixed hamburger, off-canvas drawer, 20–24 px content gutters, stacked filters/cards, full-width CTAs as needed, rows/table alternatives that do not force viewport scrolling. Dialog width is viewport minus 32 px. |
| `xs` 475 px | Reserved in many references (empty rule); do not force a new layout where none exists. Preserve fluid spacing. |
| `sm` 640 px | Two-column KPIs/filter fields or more generous card padding where shown; mobile row cards can become denser. Priority/follow-up stays ahead of charts. |
| `md` 768 px | More two-column chart/table layouts where specified; login changes to 1:1 image/form split. Sidebar remains mobile drawer until `lg`. |
| `lg` 1024 px | Fixed 240 px sidebar and no hamburger; main top padding shrinks, secondary/focus gutters widen; login image/form ratio becomes 1.1:1. |
| `xl` 1280 px | Page-specific wider grids; login image padding 64×72 px and form max width 420 px. |
| `2xl` 1536 px | Bounded content remains centered; many references intentionally make no additional layout change. |
| Other media/zoom | A few prototypes contain local 400/480/520/900 px rules. `tech_stack.md` lists the seven canonical Tailwind breakpoints. Recreate these local reflows with fluid sizing or approved utilities without adding a new global breakpoint. Verify 320 px, 200% and 400% zoom, keyboard, visible focus, 44 px targets, reduced motion/transparency and high contrast. |

### Current implementation gap

The current base gives all templates broad global typography/table rules and most pages use a different app-frame/utility treatment. The sidebar uses a padded white desktop area and a full mobile top bar; the final reference uses a 240 px fixed cool-gray desktop rail and a floating hamburger/drawer. Current cards are often more rounded, table and section density differs, and page widths are not aligned with their detailed prototypes. Current login is a centered 400 px logo card; final detailed login is the split image/form page. Current assessment/student lesson/account/modal styling and animation are not reference-faithful. Existing application data, roles, permissions, server-rendered chart tables, and protected assessment behavior remain authoritative while their visual presentation changes.

## 3. `theme.css` token plan

Do not change the existing core palette merely for novelty. The reference root definitions already match the current `theme.css` for primary 50–900, gray 50–900, success/warning/danger fills, surface/text aliases, Inter, 12–32 px base type, 4/8/12 px radius and two light shadows. **Keep** their exact values; keep `--color-primary:#0a9db8`, `--color-accent:#0cc0df`, `--color-text-cyan:#0A8298`, `--color-focus-ring:#087b90`, `--surface-translucent-bg:rgba(255,255,255,.7)` and blur 20 px. Keep `color-scheme: only light`.

Add only semantic aliases needed by repeated detailed reference colors/behaviors, after comparing each use: `--color-success-text:#0f5132`, `--color-warning-text:#7a5500`, `--color-danger-text:#7a1f1f`, `--color-danger-hover:#c93736`, `--color-violet-bg:#efe7ff`, `--color-violet-text:#4b2a8a`, `--color-overlay:rgba(21,24,27,.4)`, and `--shadow-dialog:0 24px 64px rgba(21,24,27,.18), 0 4px 16px rgba(21,24,27,.08)`. Add darker/lighter variants only where a specific reference state proves necessary; for example `#5a3f00`, `#a15700` and `#fef3e7` occur in detailed lesson/alert treatments, but they should be mapped to a clearly named role before adding separate tokens. Reuse `--primary-900` with alpha for the login overlay (`.55` at top, `.15` middle, `.85` bottom), and existing gray/text tokens with alpha for hover/scrim; put any necessary literal RGB fallback in `theme.css` only. Structural measurements (240 px sidebar, widths, gutters) belong in Tailwind utilities or a minimal theme-level shared variable where repeatedly used, never in `input.css` or inline `<style>` blocks. Rebuild `app.css` through the standalone Tailwind executable after template changes. No hardcoded hex in templates, JS, or generated design source outside `theme.css`.

## 4. Template migration and breaking references

### Full before tree

```text
templates/
├── assessment/assessment.html
├── components/{sidebar,hamburger_menu,breadcrumbs,back_link}.html
├── error/error.html
├── modals/ (24 files, exact paths in inventory above)
└── pages/
    ├── _base.html
    ├── account/{login,my_account}.html
    ├── admin/{admin_dashboard,user_management,class_management,override,audit_logs}.html
    ├── shared/{content,view_lessons,view_questions,view_student_progress}.html
    ├── student/{student_dashboard,my_lesson,lesson}.html
    └── teacher/{teacher_dashboard,my_class,class_detail}.html
```

### Intended after tree

```text
templates/
├── _base.html
├── components/{sidebar,hamburger_menu,breadcrumbs,back_link}.html
├── pages/
│   ├── admin/{admin_dashboard,user_management,class_management,student_list,override,audit_logs}.html
│   ├── teacher/{teacher_dashboard,my_class}.html
│   ├── student/{student_dashboard,my_lesson,lesson}.html
│   ├── shared/{content,view_class_detail,view_lesson,view_lesson.detail,view_questions,view_student_progress_detail}.html
│   └── account/{my_account,login}.html
├── error/error.html
├── assessment/assessment.html
└── modals/ (all 24 verified files unchanged by name; target says 25, pending reconciliation)
```

Moves: `pages/_base.html` → `_base.html`; `pages/teacher/class_detail.html` → `pages/shared/view_class_detail.html`. Renames: `pages/shared/view_lessons.html` → `pages/shared/view_lesson.html`; `pages/shared/view_student_progress.html` → `pages/shared/view_student_progress_detail.html`. New: `pages/admin/student_list.html`; `pages/shared/view_lesson.detail.html`. The target has **21 page files** (19 old + 2 new), one base and four components; template total is 50 with the current 24 modals, or 51 only after a verified twenty-fifth modal exists.

Page types are rules in `_base.html`, not extra base files: **main** = sidebar + hamburger (`admin_dashboard`, `user_management`, `class_management`, `student_list`, `override`, `audit_logs`, `teacher_dashboard`, `my_class`, `student_dashboard`, `my_lesson`, `content`, `my_account`); **secondary** = breadcrumbs (`view_class_detail`, `view_lesson`, `view_lesson.detail`, `view_questions`, `view_student_progress_detail`, and `student/lesson`); **focus** = back link (`assessment`, `error`); **standalone** = none (`login`). The requested assignment list accidentally omitted `student/lesson`; its current template and `frontend/lesson.html` both use breadcrumbs, so secondary is the evidence-based assignment. `login_background.jpg` is for `pages/account/login.html` only.

### View, URL, and test update map

| Change | Required code/test references in future phase |
|---|---|
| Base move | Change every `{% extends "pages/_base.html" %}` in page, assessment, error and `modals/auth/logout_confirm.html`; update `tests/test_phase13_accessibility.py`, `tests/test_phase4_frontend_contract.py`, and `tests/test_phase5_curriculum.py` base-path assertions. The latter two also assert old page counts/root-base absence. |
| Class-detail move + shared admin access | `apps/classrooms/views.py::class_detail` currently renders `pages/teacher/class_detail.html` and has teacher-only decorator; update to shared path, authorize admin and scoped teacher via existing selector, and set role-appropriate breadcrumbs/back links. Keep the existing teacher URL usable and add an admin detail route only if needed. Update `tests/test_phase4_pages.py`; extend security/scope checks in `test_phase4_classrooms.py`, `test_phase13_security.py`, `test_qa_smoke.py` as applicable. |
| Lesson index rename | `apps/curriculum/views.py::view_lessons` render path, all template links/extends/includes that name it, `tests/test_phase5_curriculum.py` template assertion. URL name `curriculum:view_lessons` may remain for compatibility; the path name change is a template change, not an automatic URL rename. |
| Progress-detail rename | `apps/core/views.py::student_progress` render path, `tests/test_phase12_accessibility.py` file paths, links/includes and any template assertions. Preserve scoped admin/teacher access. |
| New full lesson detail | Add a read-only admin/teacher view and URL in `apps/curriculum/views.py`/`urls.py`, scoped to published lesson, with real content, breadcrumbs and linked question sets; add route, permission and template tests. Do not expose protected pre/post content. |
| New student list | Add admin-only list view and URL in `apps/accounts/views.py` or `apps/core/views.py` with server-side search/filter/pagination; link from authorized admin navigation/context and link rows to existing scoped progress page. Add role/scope, empty/filter/pagination and render assertions. Keep user-management actions intact. |
| Inventory/count changes | `tests/test_phase4_frontend_contract.py` asserts 17 pages/19 total pages/24 modals and root-base absence; `tests/test_phase13_accessibility.py` asserts 19 pages; `tests/test_qa_smoke.py` asserts 24 modals. Update only to the actual reconciled count. |

Existing named routes and tests that use `portal:class_detail`, `portal:student_progress`, or `curriculum:view_lessons` need not break if their URL names remain stable. All hard-coded **template paths** above will break if their corresponding view/assertion is not changed in the same standalone phase. Scan all app templates, views, tests and docs again immediately before each move, as later changes may add references.

## 5. Standalone revamp phases

Each phase is one reviewable change set; stop and report after it. Each exit includes the full Django suite passing (plus focused tests for that phase), without weakening assertions merely to hide failures. Do not start any phase from this plan task.

| Phase | Work, visual comparison and exit criteria |
|---|---|
| **R1 — Tokens** | Align `theme.css` to the token plan, preserving established colors; no template move. Compare palette/type/radius/shadow across `main.html`, `secondary.html`, `focus.html`, `standalone.html`, `modals.html` and detailed pages. Exit: token audit, no raw hex outside `theme.css`, full suite green. |
| **R2 — Base and shells** | Move `_base.html`; establish exact main/secondary/focus/standalone shell blocks, stylesheet/script loading and per-page width hooks. Update every extends and base/path/count test atomically. Compare `main.html`, `secondary.html`, `focus.html`, `standalone.html`. Exit: all pages render, correct shell and light meta, full suite green. |
| **R3 — Four components** | Match sidebar, floating hamburger/drawer, sticky breadcrumbs and focus back link; preserve role links, keyboard/focus and reduced-motion behavior. Compare `main.html`, `secondary.html`, `focus.html` plus detailed shell copies. Exit: mobile/desktop nav and active state structurally correct, full suite green. |
| **R4 — Shared secondary migration** | Move class detail, rename lesson index/progress detail, update their views/tests/links. Match `class_detail.html`, `view_lesson.html`, `view_questions.html` and `secondary.html` for progress detail. Exit: teacher and admin scope correct, no old template paths, paired chart tables remain, full suite green. |
| **R5 — Two new pages** | Build admin-only `student_list` and published `view_lesson.detail`, with routes, real data and tests. Match `student_list.html` and `view_lesson_details.html`. Exit: role/object checks, pagination/empty state, links and full suite green. |
| **R6 — Admin pages** | Revamp dashboard, user management, class management, overrides and audit logs without changing services. Match the five same-purpose `frontend/` files. Exit: action forms/CSRF and research definitions intact, charts paired with tables, full suite green. |
| **R7 — Teacher pages** | Revamp teacher dashboard and `my_class`. Match `teacher_dashboard.html` and `my_classes.html`; class detail was handled in R4. Exit: assigned-class scoping, empty state and chart alternatives correct, full suite green. |
| **R8 — Student pages** | Revamp dashboard, `my_lesson` and `student/lesson`; preserve path lock rules and rich content rendering. Match `student_dashboard.html`, `my_lessons.html`, `lesson.html`. Exit: six stages, three lessons, no exposed raw model values, correct locked state and full suite green. |
| **R9 — Assessment** | Revamp one assessment template and only needed `lesson.js`/`app.js` interactions. Match `assessment.html` and `focus.html`. Exit: pre/post secrecy, immediate exercise feedback, hint/media states, submitted lock and full suite green. |
| **R10 — Login and error** | Revamp standalone login and focus error page. Match `login.html`, `error.html`, with `standalone.html`/`focus.html` shell cues. Exit: generic auth errors and safe error links, no remote prototype image, approved background provenance/crop verified and full suite green. Login visual-parity exit remains open until the untracked app JPEG is confirmed as the intended missing docs reference or the correct source is supplied. |
| **R11 — Modals** | Reconcile 24-vs-25 inventory first, then revamp **every verified modal file** to `modals.html` anatomy and states without renaming existing files. Any truly new action requires explicit product authorization and real route/service support; do not fake a functional action. Exit: inventory resolved, accessible native dialogs/focus/CSRF/destructive behavior, full suite green. |
| **R12 — Docs alignment** | Update only the listed docs (`pages.md`, `sidebar.md`, `folder_structure.md`, `overview.md`, `dashboard.md`, `user_features.md`, `user_flows.md`, `authentication.md`, `tech_stack.md`, `AGENTS.md`) and any applicable build-order source once authorized by that phase; reconcile path, count, page type and Lucide language. Match all five shell references as documented authority. Exit: no stale path/count/icon statements; full suite still green. |
| **R13 — Final check** | Run full tests/checks, static/path/doc scans and user-led side-by-side parity for every detailed page/state. Match **all 25** `frontend/` files. Exit: all checks pass, any asset/inventory gaps resolved, user accepts visual QA; then stop before Phase 15. |

## 6. Final verification plan

1. Run the full Django test suite with PostgreSQL test settings (`python manage.py test --settings=config.settings.test --noinput`), Django `check` under local/test/production settings, and `makemigrations --check --dry-run`; verify no model or migration changes. Add focused render/role/permission tests for the two new pages and admin class-detail access. Rebuild Tailwind with `tools/tailwindcss.exe -i input.css -o static/css/app.css --minify` whenever templates or utilities change; keep `input.css` at exactly three directives.
2. Static scan templates and JS for raw `#[0-9a-fA-F]{3,8}` colors, `dark:`, `.dark`, dark color-scheme queries, inline `<style>`, remote CDN/JS/CSS/image URLs, individual SVG icons, and forbidden library names. Confirm Lucide comes from `static/vendor/lucide/lucide.min.js`, Chart.js from the self-hosted UMD file, and Inter is the sole permitted external font. Confirm every icon has a text alternative or `aria-hidden` as appropriate.
3. Search template paths across views, tests, templates and the ten docs for old names: `pages/_base.html`, `pages/teacher/class_detail.html`, `pages/shared/view_lessons.html`, `pages/shared/view_student_progress.html`; also scan page-type and modal counts. Verify intended routes, 21 pages, four components, one base and the **verified** modal inventory. Do not assert 25 files while only 24 exist.
4. Verify every chart’s visible canvas has an accessible label and a server-rendered paired table/empty/error alternative; research claims retain cohort, N, time window, definitions and limits. Check student path locks and post-test eligibility separately from visuals.
5. **Manual visual parity:** render every revamped page beside its mapped `frontend/` counterpart at 320, 474, 475, 639, 640, 767, 768, 1023, 1024, 1279, 1280 and 1536 px; compare shell, text wrapping, spacing, borders, radius, shadows, icons, table density, chart/tables and the first fold. Repeat at 200%/400% zoom and with representative empty, error, locked, loading/disabled, hover, pressed, focus and modal-open states. User conducts browser visual QA because `AGENTS.md` forbids agent browser automation and screenshots; automated checks can assert Django output/structure only.
6. Manual QA checklist for the user: admin/teacher/student role navigation; student list only for admin; class detail for scoped admin/teacher; lesson index/detail/question links; responsive drawer open/close/drag/focus; every modal’s open/close/escape/backdrop/focus restoration; password visibility; login image focal crop/overlay and contrast; assessment exit/answer lock/hint/media; charts plus tables; keyboard order, focus and reduced motion; no horizontal overflow at 320 px. Record any visible mismatch and iterate in the relevant phase before approving R13.

## 7. What not to do

- Do not edit any code, template, CSS, JS, test or other doc during this analysis task; do not run tests, build assets or start R1/Phase 15.
- Do not treat `frontend/` as inspiration or copy its prototype source, inline styles, CDN links, Picsum image, fake values, role switcher, modal launcher, or preview controls into Django.
- Do not add npm, Node, packages, models, migrations, services, engines, external UI libraries, Preline, Geist, Impeccable, dark mode or runtime CDN JS/CSS.
- Do not hardcode hex outside `theme.css`, use individual SVG files or `<img>` as icons, or load Chart.js/Lucide remotely.
- Do not remove server-side authorization, CSRF, audit/research safeguards, chart table alternatives, protected pre/post secrecy or real functional state for the sake of pixel matching.
- Do not claim a twenty-fifth modal filename or login-background visual parity while the corresponding source is absent. Do not rename the 24 existing modal files to mimic prototype launcher labels.

**Planning result:** the reference UI is the final visual target. The present blockers are the missing JPEG **at its specified docs path** (with an untracked app candidate), the actual 24-file/25-dialog modal mismatch, and one omitted page-type assignment (`student/lesson`, resolved here as secondary from source evidence). No application code or reference file was changed; no tests were run; no revamp phase or Phase 15 was started.
