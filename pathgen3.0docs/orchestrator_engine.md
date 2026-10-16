# orchestrator_engine.md

Coordinates sessions, responses, BKT, Q-Learning, path transitions, and feedback finalization for PathGen 3.0.

---

## Purpose

Owns sequencing and transaction boundaries. Calls BKT and Q-Learning but does not contain their logic. Ensures atomicity, idempotency, and crash recovery.

---

## Invariants

| Invariant | Detail |
|---|---|
| Path is authoritative | `learning_student_path` locked during transitions |
| One response per item | Unique constraint, locked after write |
| One BKT event per response | Post-test creates none |
| One Q-Learning decision per eligible session | Unique on session |
| One feedback row per session | Unique on session |
| RAG never changes learning | Cannot touch scores, BKT, decisions, path |
| No external calls in locks | Providers called after commit |

---

## Session issuance

In one database transaction:

1. Authenticate + authorize active student
2. Require Student Study Access
3. Lock `learning_student_path`
4. Check requested stage matches
5. For post-test: require Post-test Access + `posttest_ready`
6. Return existing issued/in-progress session if resumable
7. Select correct question set from `curriculum_question_set`
8. Validate counts, skill distribution, difficulty, media
9. Create `learning_session` + ordered `learning_session_item` rows
10. Update path state

**Set sizes:**

| Session type | Items |
|---|---|
| Pretest | 30 protected |
| Regular | 6 |
| Additional | 6 |
| Foundational | 3 per weak skill |
| Activity | 10 |
| Posttest | 30 protected (same as pretest) |

Once issued, items never change.

---

## One-question response transaction

For each submitted question:

1. Lock session and current ordered item
2. Reject completed, out-of-order, or foreign data
3. Verify choice belongs to current question
4. Validate hint possible only for foundational
5. Persist trusted `hint_used` state
6. Create unique `learning_response` (locked)
7. Derive correctness from `selected_choice.is_correct`
8. Call BKT in the same transaction (except post-test)
9. Commit
10. Return permitted UI state

| Session type | Feedback to student |
|---|---|
| Regular / Additional / Foundational / Activity | Immediate correctness + explanation |
| Pretest / Posttest | Saved, no correctness until end |

Duplicate delivery returns committed state without a second event.

---

## BKT integration

Called inside the response transaction.

| Phase rule | Behavior |
|---|---|
| Pretest | Posterior applied, no $P(T)$ |
| Regular / Additional / Activity | Posterior $+ P(T)$ |
| Foundational (no hint) | Posterior $+ P(T)$ |
| Foundational (hint used) | Skip posterior, apply $P(T)$ only |
| Posttest | No BKT call at all |

BKT writes two tables:

- `adaptive_skill_mastery` (current state)
- `adaptive_mastery_event` (append-only, immutable)

Row lock on mastery per (student, skill).

---

## Final-answer deterministic transaction

When the final response is committed:

1. Lock session + path
2. Verify every issued item has one valid response
3. Derive total and per-skill counts
4. Verify eligible BKT events exist; post-test has none
5. For regular and additional:
   - Derive pass/fail per skill (2 of 3 correct)
   - Compute state: $(\text{weakest\_band}, \text{average\_band}, \text{pass\_result})$
   - Call Q-Learning `decide()`
   - Persist `adaptive_decision` + targets + snapshot
   - Apply safety cap if 3 fails on same skill
   - Set path transition
6. For foundational:
   - Always transition to `progress`
   - Persist `adaptive_decision` with `action='progress'`, `reason_code='foundational_fixed'`
   - Mark unresolved skills as `follow_up` targets
   - Apply safety cap if 3 fails on same skill
   - Set path transition
7. For pretest:
   - Move to Lesson 1
8. For activity:
   - Move to `posttest_ready`
9. For posttest:
   - Move to `completed`, no BKT, no RAG
10. Set `submitted_at`
11. For RAG-eligible sessions: leave `submitted` for feedback finalization
12. For non-RAG sessions: mark `completed`

No external call inside this transaction.

---

## Q-Learning integration

Called inside the final-answer transaction.

### State

$$\text{state} = (\text{weakest\_band}, \text{average\_band}, \text{pass\_result})$$

Bands from $p_{\text{known}}$:

```
np:     < 0.50
dev:    0.50 – 0.80
strong: ≥ 0.80
```

### Action space per context

| Context | Allowed |
|---|---|
| After regular | progress, additional_exercise, foundational_exercise |
| After additional | progress, foundational_exercise |
| After foundational | Always progress (fixed) |
| After activity | Always posttest_ready (fixed) |

### Decision flow

1. Look up `q_table.json` (loaded at startup, cached)
2. Get row for state
3. Mask unavailable actions
4. Return argmax
5. If table missing, state not found, or invalid → fallback to `progress`
6. Persist `adaptive_decision` with state + q_values + policy_version
7. Persist targets (next_exercise, follow_up)

### Persistence

`adaptive_decision`:

| Field | Value |
|---|---|
| session | FK, unique |
| action | progress / additional_exercise / foundational_exercise |
| reason_code | `q_learning_argmax` or `q_learning_missing_fallback` |
| policy_version | `Q-LEARNING-V1` |
| input_snapshot_json | state + q_values + chosen_action + available_actions |

Append-only, immutable.

---

## Safety cap

Outside Q-Learning:

| Rule | Effect |
|---|---|
| 3 fails on same skill | Force `progress`, mark `follow_up` |
| Foundational always progresses | Fixed transition |

Q-Learning decides. The cap prevents infinite loops.

---

## Feedback finalization

After deterministic commit for an applicable session:

1. Build query from session evidence
2. OpenAI `text-embedding-3-small` embeds query
3. In-memory cosine retrieval: top 4, min $0.35$
4. Groq `gpt-oss-120b` generates response (bounded prompt)
5. Validate output ($\le 180$ words, no leaks, matches action)
6. Save `feedback_session_feedback` as `generated` or `fallback`
7. Mark session `completed` with `completed_at`

If any step fails → save deterministic fallback. Session still completes.

### RAG-eligible sessions

- Regular
- Additional
- Foundational
- Activity

### RAG-ineligible sessions

- Pretest
- Posttest

---

## Fixed and adaptive transitions

```
Pretest completed → Lesson 1
Lesson content completed → Regular exercise
Regular completed → Q-Learning decides
Additional completed → Q-Learning decides
Foundational completed → Progress + follow_up targets
Lesson 1 progress → Lesson 2
Lesson 2 progress → Lesson 3
Lesson 3 progress → Activity
Activity completed → posttest_ready
Eligible Posttest completed → completed
```

Assigned branches visible only when backed by stored decision rows.

---

## Failure and recovery matrix

| Failure point | Required result |
|---|---|
| Validation/permission before write | No write; safe error |
| Response transaction | Full rollback for that answer; earlier committed answers preserved |
| BKT error | Rollback response; no partial event |
| Q-Learning error | Rollback final transaction; session recoverable |
| Final transaction | No partial decision or path transition |
| OpenAI embedding | Use fallback; no learning rollback |
| Index stale or missing | Use fallback |
| Groq timeout or invalid output | Save fallback, complete session |
| Feedback finalization conflict | Re-read row; return committed result |
| Duplicate submission | Row locks + unique constraints return same result |
| Stale access or path | Deny before issuance or submission |

Provider calls use bounded timeouts. Logs correlate session/decision/feedback IDs. No secrets, no full answer payloads.

---

## Crash recovery

**Scenario:** Deterministic commit succeeded. Server crashes before feedback saved.

**Recovery:**

1. Health check or next request finds `submitted` session with no feedback
2. Saves deterministic fallback feedback
3. Marks session completed
4. No BKT, Q-Learning, or path recomputation

```python
def finalize_pending_sessions():
    for session in Session.objects.filter(
        status="submitted",
        feedback__isnull=True,
        session_type__in=["regular", "additional", "foundational", "activity"]
    ):
        save_fallback_feedback(session)
        mark_completed(session)
```

---

## Session reset (admin only)

Admins can soft-void a pretest or posttest:

1. Reason required
2. Set `voided_at`, `voided_by`, `void_reason`
3. If pretest: recompute mastery, reset path to `pretest_required`
4. If posttest: reset path to `posttest_ready`
5. Write audit event

Voided sessions excluded from BKT, scoring, and dashboards. Original preserved.

---

## Permissions

| Action | Who |
|---|---|
| Submit responses | Owning active student only |
| Issue session | Orchestrator service, on student's behalf |
| Reset session | Admin only |
| Read decisions | Role-scoped |
| Edit evidence | Nobody |

Teachers and admins never invoke mutation services on behalf of students.

---

## Tests and acceptance

| Test | Checks |
|---|---|
| Full flows | Pretest → L1 → L2 → L3 → activity → posttest |
| Adaptive branches | Both additional and foundational |
| Per-question duplicate | One response, one event |
| Final duplicate | One decision, one feedback, one path transition |
| Immediate vs delayed feedback | Matches session type |
| Posttest no BKT | Zero events, verified |
| Provider/index failures | Fallback without state change |
| Crash between commit and feedback | Fallback saved, session completed |
| Access closure mid-session | Fails safely, no leak |
| Concurrent tabs | Serialized by locks |

---

## Transaction boundaries summary

| Stage | Locked? | External calls? |
|---|---|---|
| Session issuance | Yes — path | No |
| Response submission | Yes — session, item, mastery | No |
| Final transaction | Yes — session, path, mastery | No |
| Feedback generation | No | Yes — OpenAI, Groq |
| Feedback finalization | Yes — session, feedback | No |

No provider call ever occurs while a row is locked.

---

**End of reference.**
