# Database Schema — PathGen 3.0

PostgreSQL domain schema for PathGen 3.0.

---

## Purpose

Defines the 22 domain tables, their fields, constraints, and relationships. Uses `varchar` + `CHECK` for enums (Django-native). Three tables are append-only, enforced by DB triggers.

---

## Conventions

- UUID primary keys except singleton and composite/through tables
- Timezone-aware timestamps
- Enums as `varchar` + `CHECK` (Django `TextChoices`)
- Required facts are non-null
- Role-sensitive FKs validated in service layer
- Published curriculum used by a session is immutable
- All multi-table writes go through atomic services
- Concurrency-sensitive transitions use `SELECT ... FOR UPDATE`

---

## Table index

| App | Tables |
|---|---|
| accounts | `accounts_user` |
| classrooms | `classrooms_classroom`, `classrooms_student_membership` |
| curriculum | `curriculum_skill`, `curriculum_lesson`, `curriculum_lesson_skill`, `curriculum_video`, `curriculum_question`, `curriculum_question_choice`, `curriculum_question_set`, `curriculum_question_set_item` |
| learning | `learning_student_path`, `learning_session`, `learning_session_item`, `learning_response` |
| adaptive | `adaptive_skill_mastery`, `adaptive_mastery_event`, `adaptive_decision`, `adaptive_decision_target_skill` |
| feedback | `feedback_session_feedback` |
| core | `core_system_setting`, `core_audit_event` |

---

## 1. `accounts_user`

| Field | Type | Notes |
|---|---|---|
| id | UUID | PK |
| username | varchar | unique, immutable |
| email | varchar | nullable |
| first_name | varchar | |
| last_name | varchar | |
| role | varchar | `admin` / `teacher` / `student` + CHECK |
| password | varchar | Django hash |
| is_active | boolean | |
| deactivated_at | timestamptz | nullable |
| deactivated_by | FK self | nullable, PROTECT |
| deactivation_reason | text | nullable |
| anonymized_at | timestamptz | nullable |
| is_staff | boolean | Django flag |
| is_superuser | boolean | Django flag |
| created_at | timestamptz | |
| updated_at | timestamptz | |

No avatar field. Avatar derived from role at render.

---

## 2. `classrooms_classroom`

| Field | Type | Notes |
|---|---|---|
| id | UUID | PK |
| code | varchar | unique |
| name | varchar | |
| teacher | FK user | nullable |
| status | varchar | `active` / `archived` + CHECK |
| archived_at | timestamptz | nullable |
| archived_by | FK user | nullable |
| archive_reason | text | nullable |
| created_at | timestamptz | |
| updated_at | timestamptz | |

---

## 3. `classrooms_student_membership`

| Field | Type | Notes |
|---|---|---|
| id | UUID | PK |
| classroom | FK classroom | |
| student | FK user | |
| joined_at | timestamptz | |
| left_at | timestamptz | nullable |
| added_by | FK user | |
| removed_by | FK user | nullable |

Partial unique: `(classroom, student)` WHERE `left_at IS NULL`.

---

## 4. `curriculum_skill`

| Field | Type | Notes |
|---|---|---|
| id | UUID | PK |
| code | varchar | unique — S1..S6 |
| name | varchar | |
| description | text | |
| p_l0 | decimal | 0.30 |
| p_t | decimal | 0.09 |
| p_g | decimal | 0.10 |
| p_s | decimal | 0.09 |
| created_at | timestamptz | |
| updated_at | timestamptz | |

All probabilities CHECK in $[0, 1]$.

**Source:** Hawkins et al. (2013). Extending the Assistance Model. *EDM 2013*.

---

## 5. `curriculum_lesson`

| Field | Type | Notes |
|---|---|---|
| id | UUID | PK |
| code | varchar | unique — L1..L3 |
| slug | varchar | unique |
| lesson_order | int | unique, positive |
| title | varchar | |
| summary | text | |
| content_json | JSONB | ordered blocks |
| content_schema_version | int | positive |
| is_published | boolean | |
| created_at | timestamptz | |
| updated_at | timestamptz | |

---

## 6. `curriculum_lesson_skill`

| Field | Type | Notes |
|---|---|---|
| lesson | FK lesson | |
| skill | FK skill | |
| display_order | smallint | 1 or 2 |

Unique on `(lesson, skill)` and `(lesson, display_order)`.

---

## 7. `curriculum_video`

| Field | Type | Notes |
|---|---|---|
| id | UUID | PK |
| code | varchar | unique |
| title | varchar | |
| youtube_video_id | varchar | unique |
| duration_seconds | int | positive |
| transcript | text | non-blank |
| created_at | timestamptz | |
| updated_at | timestamptz | |

---

## 8. `curriculum_question`

| Field | Type | Notes |
|---|---|---|
| id | UUID | PK |
| code | varchar | unique |
| skill | FK skill | required |
| prompt | text | |
| difficulty | varchar | `standard` / `foundational` + CHECK |
| presentation_type | varchar | `text` / `figure` / `video` + CHECK |
| cognitive_level | varchar | remember / understand / apply / analyze / evaluate / create + CHECK |
| solution_steps_json | JSONB | ordered |
| explanation | text | |
| hint | text | nullable (foundational only) |
| feedback_correct | text | |
| feedback_incorrect | text | |
| image_asset | varchar | nullable |
| image_alt | varchar | nullable |
| visual_component | varchar | nullable |
| visual_config_json | JSONB | nullable |
| video | FK video | nullable |
| video_pause_seconds | int | nullable |
| is_published | boolean | |
| created_at | timestamptz | |
| updated_at | timestamptz | |

---

## 9. `curriculum_question_choice`

| Field | Type | Notes |
|---|---|---|
| id | UUID | PK |
| question | FK question | |
| label | varchar | A / B / C / D + CHECK |
| text | text | |
| is_correct | boolean | |
| misconception_code | varchar | nullable |
| display_order | smallint | 1–4 |

Unique on `(question, label)` and `(question, display_order)`.
Partial unique: at most one correct per question.

---

## 10. `curriculum_question_set`

| Field | Type | Notes |
|---|---|---|
| id | UUID | PK |
| code | varchar | unique |
| name | varchar | |
| set_type | varchar | `prepost` / `regular` / `additional` / `foundational` / `activity` + CHECK |
| lesson | FK lesson | nullable |
| skill | FK skill | nullable |
| is_published | boolean | |
| created_at | timestamptz | |
| updated_at | timestamptz | |

Conditional CHECK: regular/additional need lesson; foundational needs skill; prepost/activity need neither.

---

## 11. `curriculum_question_set_item`

| Field | Type | Notes |
|---|---|---|
| question_set | FK set | |
| question | FK question | |
| display_order | int | positive |

Unique on `(question_set, question)` and `(question_set, display_order)`.

---

## 12. `learning_student_path`

| Field | Type | Notes |
|---|---|---|
| student | FK user | PK, one-to-one |
| status | varchar | `pretest_required` / `learning` / `activity_ready` / `posttest_ready` / `completed` + CHECK |
| current_lesson | FK lesson | nullable |
| current_stage | varchar | `pretest` / `lesson` / `regular` / `additional` / `foundational` / `activity` / `posttest` + CHECK |
| created_at | timestamptz | |
| updated_at | timestamptz | |

---

## 13. `learning_session`

| Field | Type | Notes |
|---|---|---|
| id | UUID | PK |
| student | FK user | |
| session_type | varchar | `pretest` / `regular` / `additional` / `foundational` / `activity` / `posttest` + CHECK |
| lesson | FK lesson | nullable |
| status | varchar | `issued` / `in_progress` / `submitted` / `completed` + CHECK |
| attempt_number | int | positive |
| voided_at | timestamptz | nullable |
| voided_by | FK user | nullable |
| void_reason | text | nullable |
| started_at | timestamptz | nullable |
| submitted_at | timestamptz | nullable |
| completed_at | timestamptz | nullable |
| created_at | timestamptz | |
| updated_at | timestamptz | |

Voided sessions excluded from BKT, scoring, and dashboards. Original history preserved.

Scores, counts, percentages — derived, never stored.

---

## 14. `learning_session_item`

| Field | Type | Notes |
|---|---|---|
| id | UUID | PK |
| session | FK session | |
| question | FK question | |
| display_order | int | positive |

Unique on `(session, question)` and `(session, display_order)`.

---

## 15. `learning_response`

| Field | Type | Notes |
|---|---|---|
| id | UUID | PK |
| session_item | FK item | unique |
| selected_choice | FK choice | |
| hint_used | boolean | |
| answered_at | timestamptz | |

Correctness derived from `selected_choice.is_correct`. Never stored.

---

## 16. `adaptive_skill_mastery`

| Field | Type | Notes |
|---|---|---|
| id | UUID | PK |
| student | FK user | |
| skill | FK skill | |
| p_known | decimal | CHECK $[0, 1]$ |
| evidence_count | int | nonnegative |
| created_at | timestamptz | |
| updated_at | timestamptz | |

Unique on `(student, skill)`.

---

## 17. `adaptive_mastery_event`

| Field | Type | Notes |
|---|---|---|
| id | UUID | PK |
| mastery | FK mastery | |
| response | FK response | unique |
| p_before | decimal | CHECK $[0, 1]$ |
| p_after_observation | decimal | nullable, CHECK $[0, 1]$ |
| p_after_learning | decimal | CHECK $[0, 1]$ |
| learning_transition_applied | boolean | |
| created_at | timestamptz | |

Append-only. Immutable. Enforced by DB trigger.

---

## 18. `adaptive_decision`

| Field | Type | Notes |
|---|---|---|
| id | UUID | PK |
| session | FK session | unique |
| action | varchar | `progress` / `additional_exercise` / `foundational_exercise` + CHECK |
| reason_code | varchar | e.g., `q_learning_argmax` |
| policy_version | varchar | `Q-LEARNING-V1` |
| input_snapshot_json | JSONB | state + q_values + chosen_action |
| created_at | timestamptz | |

Append-only. Immutable. Enforced by DB trigger.

---

## 19. `adaptive_decision_target_skill`

| Field | Type | Notes |
|---|---|---|
| decision | FK decision | |
| skill | FK skill | |
| target_kind | varchar | `next_exercise` / `follow_up` + CHECK |

Unique on `(decision, skill, target_kind)`.

---

## 20. `feedback_session_feedback`

| Field | Type | Notes |
|---|---|---|
| id | UUID | PK |
| session | FK session | unique |
| feedback_text | text | |
| generation_status | varchar | `generated` / `fallback` + CHECK |
| model_name | varchar | nullable — `gpt-oss-120b` or null |
| created_at | timestamptz | |

---

## 21. `core_system_setting`

| Field | Type | Notes |
|---|---|---|
| singleton_key | smallint | PK, CHECK = 1 |
| study_access_enabled | boolean | |
| posttest_access_enabled | boolean | |
| changed_by | FK user | admin only |
| changed_at | timestamptz | |
| revision | int | nonnegative |

Row-locked, revision-checked on update.

---

## 22. `core_audit_event`

| Field | Type | Notes |
|---|---|---|
| id | UUID | PK |
| actor | FK user | nullable |
| action | varchar | stable code |
| target_type | varchar | |
| target_id | UUID | |
| target_snapshot_json | JSONB | safe snapshot |
| reason | text | nullable |
| metadata_json | JSONB | small |
| created_at | timestamptz | |

Append-only. Immutable. Enforced by DB trigger.

---

## Append-only enforcement

Three tables are append-only: `adaptive_mastery_event`, `adaptive_decision`, `core_audit_event`.

PostgreSQL trigger rejects any `UPDATE` or `DELETE`. Application code cannot modify history.

```sql
CREATE FUNCTION prevent_modification() RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'This table is append-only';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER no_update_mastery_event
BEFORE UPDATE OR DELETE ON adaptive_mastery_event
FOR EACH ROW EXECUTE FUNCTION prevent_modification();
-- repeat for adaptive_decision, core_audit_event
```

---

## Deletion behavior

| Relationship | Policy |
|---|---|
| Curriculum FKs | PROTECT |
| Learning evidence FKs | PROTECT |
| Unused draft composition | CASCADE (only for inseparable drafts) |
| Actor references | SET_NULL where event must survive |

Deactivation and archival are the normal lifecycle. Permanent deletion is exceptional and rejected when protected history exists.

---

## Row locking

Applied during concurrency-sensitive transitions:

| Table | When |
|---|---|
| `learning_student_path` | Session issuance and transition |
| `learning_session` | Response submission, finalization |
| `adaptive_skill_mastery` | BKT update per (student, skill) |
| `core_system_setting` | Override update (revision check) |

All uses `SELECT ... FOR UPDATE` inside `transaction.atomic()`.

---

## Atomic workflows

| Workflow | Tables involved |
|---|---|
| Session issuance | path lock $\rightarrow$ session + items |
| Response submission | session lock $\rightarrow$ response + mastery event + mastery |
| Session finalization | session lock $\rightarrow$ decision + targets $\rightarrow$ path transition |
| Feedback finalization | session lock $\rightarrow$ feedback row + status |
| Override update | setting lock $\rightarrow$ revision check $\rightarrow$ audit |

Provider calls never occur inside locked transactions.

---

## Permissions

| Role | Access |
|---|---|
| Admin | Non-admin account lifecycle, classes, settings, audit read, research read |
| Teacher | Assigned classes, current students, shared content, read-only |
| Student | Own path, sessions, results, feedback |

Every selector filters by scope before object lookup. Every POST revalidates.

---

## Derived data (never stored)

| Concept | Derived from |
|---|---|
| Scores | `learning_response` + `curriculum_question_choice.is_correct` |
| Pass/fail per skill | Counted responses vs SCORING-V2 |
| BKT bands | `p_known` thresholds |
| Matched gain | Matched pre/post sessions |
| Elapsed duration | $\text{completed\_at} - \text{started\_at}$ |
| RAG reliability | `generation_status` counts |
| Follow-up count | `adaptive_decision_target_skill` with `follow_up` |

---

## V1 policy constants

| Policy | Value |
|---|---|
| `SCORING-V2` | 2 of 3 correct passes a skill |
| Activity distribution | S1=2, S2=2, S3=2, S4=2, S5=1, S6=1 |
| `BKT-V1` | $P(L_0)=0.30$, $P(T)=0.09$, $P(G)=0.10$, $P(S)=0.09$ |
| `Q-LEARNING-V1` | Trained externally, frozen table |
| `RAG-RETRIEVAL-V1` | Top 4, min 0.35, 350/500/50 tokens |

These constants appear in `manifest.json` and application config.

---

## Data volumes

| Item | Count |
|---|---|
| Lessons | 3 |
| Skills | 6 |
| Regular questions | 18 |
| Additional questions | 18 |
| Foundational questions | 18 |
| Activity questions | 10 |
| Pre/post questions | 30 |
| **Total questions** | **94** |

---

## Acceptance checks

- Exactly 22 domain tables
- Every published question has 4 distinct A-D choices and one correct
- Every published lesson has 2 skills
- Pre/post set has 30 items in fixed order PP-01 to PP-30
- Append-only triggers reject `UPDATE` and `DELETE`
- Row locks used for all concurrency-sensitive transitions
- No destructive cascade into protected history
- Posttest creates zero mastery events
- Deletion only permitted for unused inactive records