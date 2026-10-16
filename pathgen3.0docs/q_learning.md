# Q-Learning — General

## What is Q-Learning?

A reinforcement learning algorithm. An agent learns which action to take in each state by trying actions and learning from rewards.

It builds a table: for every state, which action gives the best long-term reward.

## Purpose

Learn a policy — a rule that says "in this situation, do this." The agent discovers the policy by trial and error.

## How it works

Four elements define the problem:

| Element | Meaning |
|---|---|
| State ($s$) | The situation the agent is in |
| Action ($a$) | What the agent can do |
| Reward ($r$) | Feedback after taking an action |
| Next state ($s'$) | The situation after the action |

The Bellman update is the core formula:

$$Q(s, a) \leftarrow Q(s, a) + \alpha \cdot [r + \gamma \cdot \max Q(s', a') - Q(s, a)]$$

| Symbol | Meaning |
|---|---|
| $\alpha$ | Learning rate — how much new info overrides old |
| $\gamma$ | Discount factor — how much future rewards matter |
| $\max Q(s', a')$ | Best possible value in the next state |

The agent repeats this for many episodes until the Q-table stabilizes.

## Pseudocode

```text
function train_q_learning():
    initialize Q(s, a) = 0 for all states and actions

    for episode in range(episodes):
        observe initial state s

        repeat until terminal:
            choose action a from s using ε-greedy
            take action a, observe reward r and next state s'

            Q(s, a) = Q(s, a) + α · [r + γ · max Q(s', a') − Q(s, a)]

            s = s'

    return Q
```

## Python code (training)

```python
def train_q_learning(episodes, alpha, gamma, epsilon_start, epsilon_end):
    Q = defaultdict(lambda: {a: 0.0 for a in ACTIONS})

    for episode in range(episodes):
        epsilon = max(epsilon_end, epsilon_start - episode / (episodes / 2))
        state = initial_state()

        while not terminal(state):
            if random.random() < epsilon:
                action = random.choice(ACTIONS)
            else:
                action = max(Q[state], key=Q[state].get)

            reward, next_state = step(state, action)
            best_next = max(Q[next_state].values())

            Q[state][action] += alpha * (reward + gamma * best_next - Q[state][action])
            state = next_state

    return Q
```

## Python code (runtime)

```python
def decide(state_key, allowed_actions):
    try:
        row = Q_TABLE.get(state_key)
        if not row:
            return "progress"

        filtered = {a: row[a] for a in allowed_actions if a in row}
        if not filtered:
            return "progress"

        return max(filtered, key=filtered.get)
    except:
        return "progress"
```

That is the entire engine.

---

# Q-Learning in PathGen

Q-Learning engine for PathGen 3.0. Trained externally, consumed as a frozen artifact.

---

## Purpose

Decides which route a student takes after an exercise. One of three actions: `progress`, `additional_exercise`, `foundational_exercise`. Feeds the orchestrator's path transitions. Never updates BKT, scores, or feedback.

---

## Location

```
apps/adaptive/
├── q_learning.py             loader + decide
├── q_table.json              frozen artifact
├── services.py               persistence
├── models.py                 Decision, Target tables
└── selectors.py              read-only queries
```

Two tables: `adaptive_decision`, `adaptive_decision_target_skill`.

Training happens outside the app. PathGen only consumes the artifact.

---

## Two systems

| System | Location | Purpose |
|---|---|---|
| Trainer | External repo | Generate 10,000 synthetic students, produce `q_table.json` |
| PathGen | `apps/adaptive/` | Load frozen table, decide routes |

Only `q_table.json` crosses the boundary.

---

## State

```python
state = (weakest_band, average_band, pass_result)
```

| Feature | Values |
|---|---|
| weakest_band | `np`, `dev`, `strong` |
| average_band | `np`, `dev`, `strong` |
| pass_result | `pp`, `pf`, `fp`, `ff` |

36 combinations. Only 24 reachable ($\text{weakest} \le \text{average}$).

Bands come from BKT:

- **np**: $< 0.50$
- **dev**: $0.50 - 0.80$
- **strong**: $\ge 0.80$

Pass result: 2 of 3 correct per skill.

---

## Actions

| Context | Allowed |
|---|---|
| After regular exercise | `progress`, `additional_exercise`, `foundational_exercise` |
| After additional exercise | `progress`, `foundational_exercise` |
| After foundational | Always `progress` (fixed) |
| After activity | Always `posttest_ready` (fixed) |

One Q-table. Runtime masks unavailable actions.

---

## Reward

$$\text{reward} = \text{mean\_bkt\_after} - \text{mean\_bkt\_before}$$

Positive = student learned. Negative = wasted time.

---

## Runtime algorithm

```python
def decide(state_key, allowed_actions):
    try:
        row = load_q_table().get(state_key)
        if not row:
            return "progress"

        filtered = {a: row[a] for a in allowed_actions if a in row}
        if not filtered:
            return "progress"

        return max(filtered, key=filtered.get)

    except (FileNotFoundError, KeyError, ValueError):
        return "progress"
```

Loads table once at startup. Deterministic. Never crashes.

---

## Artifact format

```json
{
  "_meta": {
    "policy_version": "Q-LEARNING-V1",
    "trained_episodes": 10000,
    "training_seed": 42
  },
  "q_values": {
    "(np, np, ff)": {"progress": 0.02, "additional_exercise": 0.10, "foundational_exercise": 0.30},
    "(np, np, pf)": {"progress": 0.05, "additional_exercise": 0.22, "foundational_exercise": 0.28},
    "...": "27 rows total"
  }
}
```

~50KB. Committed to repo.

---

## Persistence

Every decision writes to `adaptive_decision`:

```json
{
  "action": "foundational_exercise",
  "reason_code": "q_learning_argmax",
  "input_snapshot_json": {
    "state": "(np, dev, pf)",
    "q_values": {
      "progress": 0.08,
      "additional_exercise": 0.30,
      "foundational_exercise": 0.25
    },
    "chosen_action": "foundational_exercise",
    "available_actions": ["progress", "additional_exercise", "foundational_exercise"],
    "policy_version": "Q-LEARNING-V1"
  }
}
```

Full audit trail.

---

## Tables

**adaptive_decision** (unique on session):

| Field | Type |
|---|---|
| session | FK |
| action | `progress` / `additional_exercise` / `foundational_exercise` |
| reason_code | string |
| input_snapshot_json | JSONB |
| created_at | timestamp |

**adaptive_decision_target_skill**:

| Field | Type |
|---|---|
| decision | FK |
| skill | FK |
| target_kind | `next_exercise` / `follow_up` |

---

## Fallback rules

| Situation | Behavior |
|---|---|
| `q_table.json` missing | `progress` |
| State not in table | `progress` |
| All actions masked | `progress` |
| Invalid Q-value | `progress` |
| File corrupted | `progress` |

Every fallback logs `reason: q_learning_missing_fallback`. System never breaks.

---

## Safety cap

Outside Q-Learning:

| Rule | Effect |
|---|---|
| Max fails per skill | 3 |
| After 3 fails | Force `progress` + mark `follow_up` |

---

## Boundaries

Q-Learning cannot update BKT, score exercises, write feedback, or alter path. It writes only two tables: `adaptive_decision`, `adaptive_decision_target_skill`.

---

## Versioning

`Q-LEARNING-V1` — policy version. Any change to state, actions, or reward requires a new version. Old snapshots never reinterpreted.

---

## Update workflow

```
1. In trainer repo: python trainer.py
2. Check output/q_table.json
3. Copy to PathGen: apps/adaptive/q_table.json
4. Commit
5. Restart PathGen (reloads table)
```

No code changes in PathGen. Just the artifact.
