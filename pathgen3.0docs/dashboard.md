# dashboard.md

Dashboards for PathGen 3.0 — admin, teacher, student.

---

## Purpose

Three role-based dashboards. Server-rendered Django. Chart.js enhancement. Read-only on all learning evidence.

---

## Shared contract

| Rule | Detail |
|---|---|
| Server-rendered | Django templates |
| Charts | Chart.js, progressively enhanced |
| Metrics | Derived in `core/metrics.py`, not stored |
| Cohort, N, definition | Every chart states all three |
| Accessible tables | Every chart has a paired data table |
| Empty state | $n=0$ when valid; "Unavailable" when not |
| Duration | Elapsed session time, never "engagement" |
| No causation | Descriptive only |
| No writes | Dashboards never write evidence, mastery, routing, or feedback |

---

# Admin dashboard

**Route:** `pages/admin/admin_dashboard.html`  
**Permission:** authenticated admin only.

## Header

- PathGen identity
- Cohort/date filter (GET params, validated)
- Data "as of" time
- Reset filter

## Access status cards

Two read-only cards:

| Card | Source |
|---|---|
| Student Study Access | `core_system_setting.study_access_enabled` |
| Post-test Access | `core_system_setting.posttest_access_enabled` |

Both show `changed_at` and actor. Both link to `pages/admin/override.html`. No inline toggle.

Admin dashboard access cards are **read-only**.

- Show current state, `changed_at`, actor.
- Include a **Manage** link to `pages/admin/override.html`.
- No switch. No toggle. No POST.
- Any change to Study Access or Post-test Access happens only on `pages/admin/override.html`.

## Override page

`pages/admin/override.html` uses toggle switches, not buttons.

- Each toggle submits a POST with reason (required) and revision.
- A stale revision returns 409.
- Each change writes one `core_audit_event` row.
- Use Post/Redirect/Get on success.

## KPI row

| KPI | Definition |
|---|---|
| Active students | Count of `role=student`, `is_active=true` |
| Completed | Count of `learning_student_path.status=completed` |
| Matched pre/post sample | Distinct students with both sessions complete |
| Follow-up needed | Distinct students with unresolved `follow_up` targets |

## Research charts

| Section | Source | Notes |
|---|---|---|
| Matched pre/post gain | Responses → choice correctness, paired by student | Show N, definition, non-causal wording |
| BKT mastery by skill | `adaptive_skill_mastery.p_known` bands | State band version, N |
| Q-Learning decisions by lesson | `adaptive_decision.action` joined to lesson | Denominator + count |
| Median elapsed duration by stage | $\text{completed\_at} - \text{started\_at}$ | Label "elapsed", not active |
| RAG reliability | `generation_status` counts | Generated vs fallback, N |

## Follow-up preview

Derived from `adaptive_decision_target_skill` where `target_kind=follow_up`. Shows:
- Student
- Skill
- Latest decision
- Current BKT estimate
- Current stage
- Last activity

Row links to `pages/shared/view_student_progress.html`.

## Audit preview

Recent `core_audit_event` rows. Safe actor, action, target summary, reason, time. Row opens `modals/audit/audit_detail.html`. Read-only.

## Admin states

| State | Behavior |
|---|---|
| No students | System-empty message, hide research claims |
| No matched tests | Widget-specific insufficient-data state |
| Filter-no-match | Distinct from system-empty |
| Widget failure | Non-sensitive reference, reload option |
| Unauthorized | Standard 403/404 |

---

# Teacher dashboard

**Route:** `pages/teacher/teacher_dashboard.html`  
**Permission:** authenticated teacher, assigned classes only.

## Class selector

- Only classes where `teacher_id = request.user`
- Zero classes → complete empty state
- Empty class → empty roster, no fake data

## KPI row

| KPI | Definition |
|---|---|
| Class size | Open memberships for selected class |
| Completed | Members whose path is completed |
| Currently learning | Active path state (excluding completed, not-started) |
| Follow-up needed | Members with unresolved follow-up targets |

## Priority follow-up table (before charts)

Columns: Student, Target skill, BKT estimate, Latest decision, Current stage, Last activity, Action.

Sources:
- Current membership
- `adaptive_decision_target_skill` (follow_up)
- `adaptive_skill_mastery.p_known`
- Latest `adaptive_decision.action`
- `learning_student_path.current_stage`
- Latest session timestamp

Missing mastery → "Not enough evidence", not zero.

## Teacher charts

| Section | Notes |
|---|---|
| BKT distribution | Bands per skill, N visible |
| Matched pre/post gain | Paired cohort only |
| Q-Learning decisions | Counts by action, optional by lesson |
| Completion | Path status distribution |

**No line joining pretest and posttest aggregates.** Use matched paired-change or side-by-side with stated N.

## Roster preview

Filterable. Shows identity, path state, latest activity, follow-up status. No edit controls.

## Teacher states

| State | Behavior |
|---|---|
| Zero classes | Explains admin assigns classes |
| Empty class | Empty roster, $n=0$ |
| No filter matches | Distinct from no data |
| Insufficient research data | Widget-specific message |
| Assignment revoked mid-request | Safe denial, return to My Classes |

---

# Student dashboard

**Route:** `pages/student/student_dashboard.html`  
**Permission:** authenticated active student, self only, subject to Study Access.

## Header

- Own display name
- Class info only when current membership exists
- No class → class block omitted

## Next Step card (dominant)

Source: single `learning_student_path` row.

Maps to one authorized action:
- Begin/resume pretest
- Review lesson
- Continue regular exercise
- Continue assigned branch
- Begin activity
- Wait for Post-test Access
- Begin eligible posttest
- Review completion

Client never invents the next step.

## Learning path

Exactly 3 lessons from published `curriculum_lesson.lesson_order`. Each shows reached/completed state from path + sessions.

- Future steps: locked/available only
- Never fabricated scores, feedback, or dates
- Link to `pages/student/my_lesson.html`

## Six-skill progress

Displays 6 skills with BKT bands derived from `adaptive_skill_mastery.p_known`. Raw probabilities are never shown to students.

Bands (`MASTERY-BANDS-V1`):

| Band | Range |
|---|---|
| Needs Practice | $< 0.50$ |
| Developing | $0.50 \le p\_known < 0.80$ |
| Strong | $\ge 0.80$ |

"Not enough evidence" replaces false zero. Each bar has numeric/text label. No color-only meaning.

## Your Next Focus

Latest applicable `feedback_session_feedback.feedback_text`. `generation_status` used only for honest fallback handling — no raw provider internals.

With no feedback → supportive empty state tied to next action.

## Recent completed results

Own completed sessions. Labels: `regular`, `additional`, `foundational`, `activity`. Pre/post may appear when complete.

Correct/total derived from items + responses. Submitted responses remain locked.

## Student states

| State | Behavior |
|---|---|
| New student | Pretest next step |
| Closed Study Access | Policy explanation |
| Locked posttest | Explains access + eligibility |
| No class | Learning unaffected |
| No mastery/feedback/results | Supportive empty state |

No raw probabilities, no internal reason codes, no model names, no threshold math in student view.

---

## Stored vs derived data

| Concept | Source | Treatment |
|---|---|---|
| Identity/role | `accounts_user` | Display + scope |
| Class membership | `classrooms_student_membership` | Current roster, monitoring only |
| Global access | `core_system_setting` | Read-only status |
| Workflow state | `learning_student_path` | Stored pointer, derived CTA |
| Sessions + responses | `learning_session`, `learning_response` | Evidence; scores derived |
| Correctness | `curriculum_question_choice.is_correct` | Derived per response |
| BKT mastery | `adaptive_skill_mastery` | Stored; bands derived |
| Q-Learning decisions | `adaptive_decision`, targets | Stored; counts derived |
| Feedback | `feedback_session_feedback` | Stored; reliability derived |
| Audit events | `core_audit_event` | Immutable; recent subset |
| Matched gain | — | Derived only |
| Elapsed duration | Session timestamps | Derived; never "active" |

---

## Responsive behavior

Breakpoints: base $<475$, xs $475$, sm $640$, md $768$, lg $1024$, xl $1280$, 2xl $1536$.

| Size | Layout |
|---|---|
| base/xs | Single column, filters behind disclosure, tables become cards |
| sm/md | Two-column KPIs, teacher priority table stays first |
| lg+ | Measured grid, no more columns than data supports |
| xl/2xl | Constrain width, don't stretch |

Tested at 200% and 400% zoom.

---

## Loading, empty, error, denial

| State | Behavior |
|---|---|
| Initial HTML | Includes context + definitions + data or message |
| Enhanced fragments | `aria-busy`, stable dimensions, no fake numbers |
| Empty | Distinguish no-records, no-class, empty-class, no-evidence, no-match |
| Error | No stack trace, no cross-role identity leak |
| Denial | Enforced before aggregation |

---

## Implementation checklist

- Centralized authorized selectors
- Versioned metric definitions
- Scope enforced before every query
- Derived values only (no stored scores/gains)
- Cohort, N, definition on every chart
- Insufficient-data state distinct from zero
- Non-causal wording
- Chart.js canvas always paired with text/table
- `json_script` for safe data injection
- Access cards read-only, teacher follow-up first, student Next Step dominant
- Tested at all breakpoints + 200/400% zoom
- Keyboard, screen-reader, non-color status verified

---

**End of reference.**
