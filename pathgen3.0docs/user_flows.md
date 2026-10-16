# user_flows.md

User flows for PathGen 3.0. Every role, every path.

---

## Authentication and access

```
Login form
    ↓
Valid credentials?
    No  → Generic error (no enumeration)
    Yes → Active account?
              No  → Safe inactive message
              Yes → Student role?
                        No  → Role dashboard
                        Yes → Study Access open?
                                  No  → Access-closed state
                                  Yes → Student dashboard
```

Login rotates session. `next` URL validated. Class membership never checked at login.

Logout is a CSRF-protected POST. Password change rotates sessions per policy.

Deactivation: reason + actor + time + audit + session invalidation. Preserves history.

---

## Admin flow

```
Dashboard → Users / Classes / Overrides / Audit Logs / Content
    ↓
Users: create teacher/student, update, deactivate, reactivate, exceptional delete
Classes: create, assign teacher, add/remove members, archive, reactivate
Overrides: toggle Study Access or Post-test Access (reason + revision check)
Content: read-only Lessons and Questions
Audit: immutable event history
```

**Admin cannot:** create other admins through UI, edit learning evidence, use classes to grant access.

Failure states:
- Duplicate username/code → field error
- Stale override revision → 409 → reload current
- Protected deletion → explains blocking history
- Empty cohorts → $n=0$, not fake data

---

## Teacher flow

```
Teacher dashboard
    ↓
Assigned classes?
    None → Zero-class empty state
    One+ → Select class
              ↓
         Priority follow-up table first
              ↓
         Charts (BKT, matched gain, decisions, completion)
              ↓
         Roster → student progress (read-only)
```

Teacher sees only currently assigned classes and their students. Reassignment removes scope immediately. Guessed IDs disclose nothing.

My Classes and class detail are read-only. Content is shared read-only.

---

## Student top-level flow

```
Pretest
    ↓
Lesson 1
    ↓
Lesson 2
    ↓
Lesson 3
    ↓
Activity
    ↓
Post-test Access open AND path = posttest_ready?
    No  → Locked step in My Lesson
    Yes → Post-test
              ↓
         Completed
```

Dashboard Next Step comes from `learning_student_path`. My Lesson shows completed/current/available/locked states. Completed assessments cannot restart.

Class information shown only when membership exists. Learning works without any class.

---

## Assessment UI flow

```
Overview
    ↓
Eligible start/resume?
    No  → In-page locked state
    Yes → Issue session
              ↓
         One question at a time
              ↓
         Submit A-D choice
              ↓
         Session type?
              Exercise/Activity → Immediate correctness + explanation
              Pretest/Posttest  → Saved, no correctness shown
              ↓
         More items?
              Yes → Next question
              No  → Result
```

Active page shows: progress, optional media, prompt, exactly 4 A-D choices, submit, feedback region, then Next.

Foundational has Hint button (optional, tracked). Others do not.

Exit requires confirmation. Duplicate POST idempotent.

---

## Adaptive branch flow (Q-Learning)

```
Student finishes regular exercise
    ↓
Scoring: 2 of 3 correct per skill
    ↓
BKT bands derived from p_known
    ↓
State = (weakest_band, average_band, pass_result)
    ↓
Q-Learning lookup → one of three actions
    ↓
┌────────────────────────────────────────────┐
│ progress              → next lesson        │
│ additional_exercise   → 6 more questions   │
│ foundational_exercise → 3 per weak skill   │
└────────────────────────────────────────────┘
    ↓
If additional completes → Q-Learning again
    (progress or foundational only)
    ↓
If foundational completes → always progress
    ↓
Unresolved skills → follow_up targets
```

**Safety cap:** 3 fails on same skill → force progress + mark follow_up.

**Fallback:** If `q_table.json` missing or state not found → `progress`.

---

## Pretest, activity, posttest evidence

### Pretest

- 30 protected items, fixed order PP-01 to PP-30
- One at a time, no correctness shown
- Updates BKT **without** learning transition (diagnostic only)
- Then opens Lesson 1

### Activity

- 10 items across all 6 skills
- Distribution: S1=2, S2=2, S3=2, S4=2, S5=1, S6=1
- Immediate feedback
- May include video with cue pause
- Updates BKT with learning transition
- Then sets `posttest_ready`

### Posttest

- Same 30 items as pretest
- Fixed order. 4 A-D text choices. No figures. All prompts preserved exactly except for the documented PP-13 rewrite recorded in manifest.json under prepost_rewrites.
- No correctness until full completion
- **Creates zero BKT events**
- **No RAG feedback**
- Requires Post-test Access AND `posttest_ready`
- Completes the path

Matched gain derived only after both sessions complete.

---

## RAG feedback flow

```
Deterministic session transaction commits
    ↓
Session type eligible? (regular/additional/foundational/activity)
    No  → Skip RAG
    Yes → Build query from session evidence
              ↓
         OpenAI embeds query
              ↓
         In-memory cosine retrieval (top 4, min 0.35)
              ↓
         Groq generates feedback
              ↓
         Valid? (≤180 words, no leaks, matches action)
              Yes → Save as "generated"
              No  → Save as "fallback"
```

Feedback appears on Result view and "Your Next Focus" on the student dashboard.

**RAG cannot change** scores, BKT, Q-Learning decisions, access, or path.

---

## Access lock and recovery

| Scenario | Behavior |
|---|---|
| Study Access closed | Students blocked; teachers/admins unaffected |
| Post-test Access closed | Eligible students see locked step, earlier content still reviewable |
| Inactive account | Sessions invalidated; all requests fail closed |
| Crash between commit and feedback | Recovery saves fallback and marks completed |
| Duplicate answer or final delivery | Idempotent — returns committed state |
| Unauthorized teacher/student object | Non-disclosing denial |
| No class | Student learns normally; teacher sees zero-class state |
| `q_table.json` missing | Fallback to `progress` for every decision |

---

## Admin session reset (optional)

```
Admin opens user → session list → select pretest or posttest
    ↓
Click "Reset session"
    ↓
Confirm modal with required reason
    ↓
Service:
  - Soft-voids session (sets voided_at, voided_by, void_reason)
  - If pretest: recompute mastery, reset path to pretest_required
  - If posttest: reset path to posttest_ready
  - Write audit event
    ↓
New attempt_number issued when student retakes
```

Voided sessions excluded from BKT, scoring, and dashboards. Original preserved.

---

## Accessibility across all flows

- Focus enters error summaries and new feedback predictably
- Focus returns from dialogs to opener
- State uses text + icon, not color alone
- Browser zoom (200%, 400%) doesn't break flow
- Figures have alt text
- Videos have captions + transcript links
- Charts have text/table alternatives
- Destructive confirmations name consequences

---

## Summary — the fixed path

```
Pretest → Lesson 1 → Lesson 2 → Lesson 3 → Activity → Posttest
```

Adaptive branches appear only between regular exercise and next lesson. Every other transition is fixed.

---

**End of reference.**
