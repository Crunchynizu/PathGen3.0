# BKT — General

## What is BKT?

Bayesian Knowledge Tracing (BKT) is a probabilistic model that estimates whether a student knows a specific skill based on their historical response data.

Each skill is assigned a probability value from $0$ to $1$. Every response updates this estimate dynamically.

## Purpose

- Track mastery per skill over time.
- Predict future student performance.
- Feed adaptive educational systems that require real-time estimates of student proficiency.

## How It Works

Four parameters govern the model:

| Symbol | Meaning |
| :--- | :--- |
| $P(L_0)$ | **Prior** — probability the student knows the skill before any practice |
| $P(T)$ | **Learn Rate** — probability of learning the skill after one practice opportunity |
| $P(G)$ | **Guess** — probability of answering correctly while not knowing the skill |
| $P(S)$ | **Slip** — probability of answering incorrectly while knowing the skill |

Three primary equations update the mastery estimate $p$:

**Correct Answer (Observation Update):**
$$p_{\text{posterior}} = \frac{p \cdot (1 - P_S)}{p \cdot (1 - P_S) + (1 - p) \cdot P_G}$$

**Incorrect Answer (Observation Update):**
$$p_{\text{posterior}} = \frac{p \cdot P_S}{p \cdot P_S + (1 - p) \cdot (1 - P_G)}$$

**Learning Transition Update:**
$$p_{\text{new}} = p_{\text{posterior}} + (1 - p_{\text{posterior}}) \cdot P_T$$

For each response: compute $p_{\text{posterior}}$, apply the learning transition, and store $p_{\text{new}}$.

## Pseudocode

```text
function update_mastery(p, is_correct, P_T, P_G, P_S):
    if is_correct:
        posterior = (p * (1 - P_S)) / (p * (1 - P_S) + (1 - p) * P_G)
    else:
        posterior = (p * P_S) / (p * P_S + (1 - p) * (1 - P_G))

    new_p = posterior + (1 - posterior) * P_T
    return new_p
```

## Python Implementation

```python
def update_bkt(p: float, is_correct: bool, p_t: float, p_g: float, p_s: float) -> float:
    if is_correct:
        posterior = (p * (1 - p_s)) / (p * (1 - p_s) + (1 - p) * p_g)
    else:
        posterior = (p * p_s) / (p * p_s + (1 - p) * (1 - p_g))

    new_p = posterior + (1 - posterior) * p_t
    return new_p
```

---

# BKT in PathGen

## What is BKT in PathGen?

The engine that tracks mastery probability for each of the 6 core skills per student.

Each student maintains 6 independent mastery state records (skills $S_1$ through $S_6$). Every row updates independently whenever a student answers an item mapped to that skill.

## Purpose

| Purpose | Description / Why |
| :--- | :--- |
| **Per-skill tracking** | Evaluates 6 independent skill estimates rather than a single aggregate score. |
| **Feed Q-Learning** | Maps numeric probabilities into discrete bands (`np`, `dev`, `strong`) for routing decisions. |
| **Audit trail** | Persists every state transition as an immutable ledger event. |
| **Research evidence** | Captures fine-grained mastery trajectories across students and skills. |
| **Deterministic** | Guarantees identical sequence of inputs yields identical outputs. |

Without BKT, the system cannot distinguish between a student struggling with integers ($S_1$) versus number lines ($S_5$).

## Pseudocode in PathGen

```text
function process_response(student, skill, response):
    if session_type == "posttest":
        return  # No event, no update

    lock mastery_row(student, skill)
    if event_exists(response):
        return  # Idempotency check

    p = mastery_row.p_known
    p_before = p

    if session_type == "foundational" and hint_used:
        p_after_obs = null
        p_after = p + (1 - p) * P_T
    else:
        if response.is_correct:
            p_after_obs = (p * (1 - P_S)) / (p * (1 - P_S) + (1 - p) * P_G)
        else:
            p_after_obs = (p * P_S) / (p * P_S + (1 - p) * (1 - P_G))

        if session_type == "pretest":
            p_after = p_after_obs
        else:
            p_after = p_after_obs + (1 - p_after_obs) * P_T

    if p_after not in [0, 1]:
        raise error

    insert mastery_event(response, p_before, p_after_obs, p_after)
    update mastery_row.p_known = p_after
    update mastery_row.evidence_count += 1
```

## How BKT Works in PathGen

```text
Student answers a question
    ↓
Response locked, correctness derived from selected choice
    ↓
BKT called with (student, skill, is_correct, session_type, hint_used, response_id)
    ↓
Row lock on adaptive_skill_mastery for (student, skill)
    ↓
Check idempotency (one event per response)
    ↓
Compute posterior using P(G) and P(S)
    ↓
Apply learning transition using P(T) if applicable
    ↓
Validate within bounds [0, 1]
    ↓
Write adaptive_mastery_event (immutable)
    ↓
Update adaptive_skill_mastery.p_known
    ↓
Commit transaction
```

### Phase Rules in PathGen

| Session Type | Posterior Calculation | $P(T)$ Applied |
| :--- | :--- | :--- |
| **Pretest** | Yes | No (diagnostic evaluation only) |
| **Regular** | Yes | Yes |
| **Additional** | Yes | Yes |
| **Foundational (no hint)** | Yes | Yes |
| **Foundational (hint used)** | No | Yes (Transition only) |
| **Activity** | Yes | Yes |
| **Posttest** | *Skipped entirely* | *Skipped entirely* |

### Bands Output to Q-Learning

- **`np` (Needs Practice):** $p_{\text{known}} < 0.50$
- **`dev` (Developing):** $0.50 \le p_{\text{known}} < 0.80$
- **`strong` (Strong):** $p_{\text{known}} \ge 0.80$

> **Note:** Q-Learning utilizes these discrete bands exclusively and never reads raw $p_{\text{known}}$ or raw BKT parameters.

## Folder and File Structure in PathGen

```text
apps/adaptive/
├── __init__.py
├── apps.py
├── admin.py
├── models.py           # SkillMastery, MasteryEvent models
├── bkt.py              # Pure BKT engine logic (~50 LOC)
├── q_learning.py       # Q-Learning engine logic
├── services.py         # Workflow orchestration
├── selectors.py        # Read-only queries
├── validators.py       # Input domain validation
└── migrations/
```

### Database Schema

`adaptive_skill_mastery` — current mastery state per $(\text{student}, \text{skill})$:

| Field | Type | Description |
| :--- | :--- | :--- |
| `student` | Foreign Key | Reference to Student |
| `skill` | Foreign Key | Reference to Skill |
| `p_known` | Decimal | Current probability of mastery |
| `evidence_count` | Integer | Total count of updates processed |
| `updated_at` | Timestamp | Last update time |

*Unique constraint on `(student, skill)`.*

`adaptive_mastery_event` — append-only audit history:

| Field | Type | Description |
| :--- | :--- | :--- |
| `mastery` | Foreign Key | Reference to `adaptive_skill_mastery` |
| `response` | Foreign Key (Unique) | Reference to Response |
| `p_before` | Decimal | Mastery prior to update |
| `p_after_observation` | Decimal (Nullable) | Posterior after observation update |
| `p_after_learning` | Decimal | Final state after learning update |
| `learning_transition_applied` | Boolean | Whether $P(T)$ was applied |
| `created_at` | Timestamp | Time of event record |

*Unique constraint on `response`. Read-only/Immutable.*

### Default Skill Parameters

Configured on `curriculum_skill`:

| Parameter | Value |
| :--- | :--- |
| $P(L_0)$ | $0.30$ |
| $P(T)$ | $0.09$ |
| $P(G)$ | $0.10$ |
| $P(S)$ | $0.09$ |

*Source:* Hawkins, W. J., Heffernan, N. T., Wang, Y., & Baker, R. S. (2013). Extending the Assistance Model. *EDM 2013*, 59–66.

---

## Summary

| Dimension | Specification |
| :--- | :--- |
| **Concept** | Probabilistic Bayesian mastery estimate per $(\text{student}, \text{skill})$. |
| **Purpose** | Track fine-grained mastery, supply input bands to Q-Learning. |
| **Parameters** | $P(L_0)=0.30$, $P(T)=0.09$, $P(G)=0.10$, $P(S)=0.09$. |
| **Equations** | 3 (Correct observation, Incorrect observation, Learning transition). |
| **Location** | `apps/adaptive/bkt.py` |
| **Tables** | `adaptive_skill_mastery`, `adaptive_mastery_event` |
| **Execution Trigger** | Every eligible response submission. |
| **Bypass Trigger** | Posttest responses. |
| **Output** | Updated $p_{\text{known}}$ per skill and corresponding Q-Learning band classification. |