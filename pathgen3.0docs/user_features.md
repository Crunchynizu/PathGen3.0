# user_features.md

All role capabilities for PathGen 3.0. Three roles: admin, teacher, student. Each with its own scope, capabilities, and boundaries.

---

## Role summary

| Role | Purpose | Scope |
|---|---|---|
| Admin | Lifecycle, classes, settings, oversight, audit | Global, read-only on evidence |
| Teacher | Monitoring assigned classes | Assigned classes only, read-only |
| Student | Learning the course | Own path, own sessions, own feedback |

---

# Admin

## Purpose

Manages accounts, classes, global access settings, audit history, and research oversight. Cannot edit learning evidence.

---

## Capabilities

### Research and system oversight

On `admin_dashboard.html`, admins view derived signals:

- Active students (count of `role=student`, `is_active=true`)
- Completed paths (`learning_student_path.status=completed`)
- Matched pre/post sample (students with both sessions complete)
- Matched gain (post score − pre score, matched pairs only)
- BKT mastery distribution (bands from `adaptive_skill_mastery.p_known`)
- Q-Learning decision distribution (by action)
- Follow-up needed (unresolved `follow_up` targets)
- Median elapsed session duration (never "engagement")
- RAG reliability (generated vs fallback counts)
- Recent audit events

Each chart states cohort, sample size, window, definition. Empty cohorts show $n = 0$, never fabricated trends.

### Account lifecycle

On `pages/admin/user_management.html`:

| Action | Allowed |
|---|---|
| Create teacher/student | Yes |
| Create admin | Never |
| View detail | Yes |
| Update name/email | Yes |
| Deactivate (with reason) | Yes |
| Reactivate | Yes |
| Exceptional delete | Only inactive, unused, no protected history |
| Change username | Never — immutable |
| Change role | Never — immutable |

Every lifecycle event audited. Passwords never displayed or logged.

### Class monitoring structure

On `pages/admin/class_management.html`:

| Action | Notes |
|---|---|
| Create/update class | |
| Assign/unassign teacher | One current teacher per class |
| Add students | Historical membership |
| Remove students | Closes `left_at`, never deletes |
| Archive class | Reversible, with reason |
| Reactivate class | |
| Exceptional delete | Archived + unassigned + unused only |

Class membership never gates learning. Monitoring only.

### Read-only curriculum visibility

`pages/shared/content.html` has exactly two destinations:

| Page | Content |
|---|---|
| Lessons | 3 ordered lessons, validated blocks, 2 skills each |
| Questions | Exercise + activity items only, excludes pre/post |

Read-only. No edit UI.

### Global overrides

`pages/admin/override.html` is the only place to change Study Access and Post-test Access.

Each change requires:
- Reason
- Revision check (stale → 409)
- Row lock
- Audit event

Closing Study Access affects students only. Opening Post-test Access does not make a student eligible — path must be `posttest_ready`.

### Audit and student progress

Admins can:

- Filter and paginate `core_audit_event`
- Open read-only `pages/shared/view_student_progress.html` from any user/class context
- See sessions, results, BKT events, Q-Learning decisions, saved feedback
- Never edit these

### Own account

`pages/account/my_account.html` — own name and password only. Username and role are read-only.

---

## Non-capabilities

| Cannot | Reason |
|---|---|
| Create admins in UI | Bootstrap only |
| Edit submitted answers | Immutable evidence |
| Edit scores, BKT, decisions, feedback | Protected |
| Restart completed assessments | Policy |
| Expose pre/post in Content | Protected set |
| Use classes to grant access | Monitoring only |
| Delete protected history | Blocked |
| Edit audit events | Append-only |

---

## Failure states

| Situation | Behavior |
|---|---|
| Duplicate username/code | Field error |
| Protected deletion | Explains blocking history, no bypass |
| Stale revision | 409, reload current state |
| Empty filter result | Distinct from empty system |
| Missing record | 404, no extra info |

---

## Accessibility

- Keyboard-only operation
- Dialogs trap and restore focus
- Errors summarized and tied to fields
- Charts have text/table alternatives
- Zoom and mobile layouts preserve actions
- No color-only meaning

---

# Teacher

## Purpose

Read-only visibility into assigned classes and students. No mutation of students, classes, curriculum, settings, or learning evidence. Own name and password are self-service through `pages/account/my_account.html`.

---

## Capabilities

### Assigned-class dashboard

`pages/teacher/teacher_dashboard.html`:

| Section | Content |
|---|---|
| Class selector | Only currently assigned classes |
| Priority follow-up table | Before any charts |
| KPI row | Class size, completed, learning, follow-up needed |
| BKT distribution | Bands per skill |
| Matched pre/post gain | Paired cohort only |
| Q-Learning decisions | Counts by action |
| Completion | Path status distribution |
| Roster | Filterable, no edit |

Every chart names class/cohort, sample size, filter scope, definition. Matched gain excludes unmatched tests. Elapsed session time is derived from timestamps, not "engagement."

### My Classes

`pages/teacher/my_class.html`:

- List of currently assigned classes
- Zero classes → explanatory empty state
- No create/edit controls

### Class detail

`pages/teacher/class_detail.html`:

- Class identity, roster, completion, follow-up signals
- Student link opens `pages/shared/view_student_progress.html`
- Unauthorized ID → 404/403 without disclosure

### Read-only Content

Same experience as admins:

- Lessons: 3 ordered, 2 skills each
- Questions: exercise/activity only, pre/post excluded

### Own account

`pages/account/my_account.html` — own name and password only.

---

## Non-capabilities

| Cannot | Reason |
|---|---|
| Create/update/delete users | Admin-only |
| Create/update/archive classes | Admin-only |
| Assign teachers | Admin-only |
| Add/remove students | Admin-only |
| Change global access | Admin-only |
| Edit curriculum | Read-only |
| Edit responses, scores, BKT, decisions, feedback | Protected |
| See students outside assigned classes | Scope |
| Start/submit work for students | Forbidden |

Teachers never grant access through membership.

---

## Empty and error states

| Situation | Behavior |
|---|---|
| Zero assigned classes | Explains that admin assigns classes |
| Empty class | $n = 0$ roster, no fake data |
| No completed evidence | "Not enough data", not zero |
| Filter-no-match | Distinct from no data |
| Reassignment mid-request | Safe denial, return to My Classes |

---

## Scope enforcement

- Assigned classes: `classrooms_classroom.teacher_id = request.user`
- Students: open `classrooms_student_membership` for those classes
- Every nested lookup re-validates scope
- Historical membership does not broaden current access

---

## Accessibility

- Class selector labeled and keyboard operable
- Tables have card/stacked alternatives on mobile
- Focus moves predictably after filtering
- Follow-up status uses text + icon, not color alone
- Charts have data tables
- Alt text and transcripts present

---

# Student

## Purpose

The learner completes a fixed path with adaptive branches. Sees own progress, own feedback, own results only.

---

## Capabilities

### Dashboard

`pages/student/student_dashboard.html`:

| Section | Content |
|---|---|
| Next Step card | Dominant, from `learning_student_path` |
| Learning path | 3 lessons with reached/completed state |
| Six-skill progress | BKT bands with "not enough evidence" fallback |
| Your Next Focus | Latest saved RAG or fallback feedback |
| Recent results | Own completed sessions |
| Class info | Only if membership exists |

No class → learning still works normally.

### My Lesson

`pages/student/my_lesson.html`:

Vertical stepper:

```
Pretest → Lesson 1 → Lesson 2 → Lesson 3 → Activity → Posttest
```

Each step shows text + icon: `completed` / `current` / `available` / `locked`.

Reached lessons expand to show:
- Lesson Content
- Regular Exercise
- Additional Exercise (only if assigned)
- Foundational Exercise (only if assigned)

Optional branches absent when unassigned. Locked Post-test shows reason — not error page.

### Lesson content

`pages/student/lesson.html`:

- Validated lesson blocks
- Accessible figures with alt text
- Video with captions + transcript link
- Link to regular exercise when eligible

### Assessments

Overview → Assessment → Result.

| Type | Items | Feedback |
|---|---|---|
| Pretest | 30 | Delayed until end |
| Regular | 6 | Immediate |
| Additional | 6 | Immediate |
| Foundational | 3 per weak skill | Immediate, with hint button |
| Activity | 10 | Immediate |
| Posttest | 30 | Delayed until end |

Every item:
- One at a time
- Exactly 4 A-D choices
- Submit locked
- Idempotent on duplicate POST

### Results

Derived score + per-skill counts. Applicable sessions show saved RAG or fallback feedback.

Pre/post show approved explanations and matched results only after full completion.

### Own account

`pages/account/my_account.html` — own name and password only. Username and role read-only.

---

## The adaptive experience

| Situation | What happens |
|---|---|
| Pass regular exercise | Q-Learning decides: progress, additional_exercise, or foundational_exercise |
| Fail regular | Q-Learning decides: progress, additional_exercise, or foundational_exercise |
| Fail additional | Q-Learning decides: progress or foundational_exercise |
| Fail foundational | Always progress + follow_up |
| 3 fails on same skill | Force progress + follow_up |

Hints are optional in foundational. Use is recorded.

---

## Non-capabilities

| Cannot | Reason |
|---|---|
| Change username, role | Immutable |
| Change class membership | Admin-only |
| Change global access | Admin-only |
| Bypass locked Post-test | Requires access + eligibility |
| Restart completed assessment | Policy |
| View another student | Scope |
| Edit submitted answers | Locked |
| Change scores, BKT, decisions, feedback | Protected |

---

## Empty and locked states

| State | Behavior |
|---|---|
| New student | Pretest as Next Step |
| No class | Learning works normally |
| No mastery evidence | "Not enough evidence", not zero |
| Closed Study Access | Policy explanation, not broken account |
| Locked Post-test | Reason shown inside My Lesson |
| Optional branch unassigned | Hidden, not disabled |

---

## Accessibility

- Stepper, accordions, radio groups keyboard-operable
- Focus visible and predictable
- No color-only state
- Browser zoom safe
- Figures have alt text
- Videos have captions + transcript
- Charts have text alternatives
- Feedback uses supportive, non-diagnostic language

---

# Cross-role reference

## Shared capabilities

| Capability | Admin | Teacher | Student |
|---|---|---|---|
| Login / logout | Yes | Yes | Yes |
| Change own name | Yes | Yes | Yes |
| Change own password | Yes | Yes | Yes |
| View own account | Yes | Yes | Yes |
| Read Content (Lessons) | Yes | Yes | Own reached |
| Read Content (Questions) | Yes | Yes | No |

## Data boundaries

| Data | Admin | Teacher | Student |
|---|---|---|---|
| Own account | Allowed fields | Allowed fields | Allowed fields |
| Other accounts | Lifecycle only | Read assigned | None |
| Classes | Full lifecycle | Read assigned | None |
| Settings | Full (override page) | None | None |
| Curriculum | Read | Read | Read own reached |
| Sessions | Read all | Read assigned | Read own |
| Responses | Read all, never edit | Read assigned, never edit | Read own, locked |
| BKT mastery | Read all | Read assigned | Read own |
| Q-Learning decisions | Read all | Read assigned | Own result only |
| Feedback | Read all | Read assigned | Read own |
| Audit events | Read all | None | None |

## Common rules

- CSRF-protected POST for every mutation
- Session rotation on login
- Object scope enforced before every read
- Errors are non-disclosing
- Sensitive actions audited
- No role can edit learning evidence
- No role can bypass access gates
- No role can restart completed assessments. Admins may soft-void a pretest or posttest session with reason, as documented in orchestrator_engine.md. A void is not a restart; a new attempt_number is issued.
- Every page accessible, keyboard-operable, zoom-safe
- Light mode only

## Failure behavior across roles

| Situation | Behavior |
|---|---|
| Unauthorized object | 404/403 without disclosure |
| Empty data | Distinct state, not fake values |
| Locked step | In-page reason, not error page |
| Stale override revision | 409 with current state |
| Missing q_table.json | Fallback to `progress` |
| RAG failure | Deterministic fallback text |

## Summary

| | Admin | Teacher | Student |
|---|---|---|---|
| Primary role | Operations + oversight | Monitoring | Learning |
| Write scope | Lifecycle + settings | None | Own name/password |
| Read scope | Global | Assigned classes | Own path |
| Evidence | Read-only | Read-only | Read-only own |
| Restart assessments | No | No | No |
| Change access | Yes (only place) | No | No |
| Q-Learning | Consumes decisions | Observes decisions | Experiences routing |

---

**End of reference.**
