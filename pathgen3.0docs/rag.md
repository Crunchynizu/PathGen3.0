# RAG — General

## What is RAG?

Retrieval-Augmented Generation (RAG) is an architectural pattern that retrieves relevant domain-specific passages from a knowledge base and uses them to ground a large language model's (LLM) generation output.

Instead of permitting unconstrained generation, RAG enforces strict contextual grounding: *"Generate responses using only these retrieved passages."*

## Purpose

| Purpose | Description / Rationale |
| --- | --- |
| **Grounded Output** | Prevents factual hallucinations by constraining generation to verified texts. |
| **Bounded Context** | Ensures only authoritatively approved curriculum materials enter the context window. |
| **Auditable Traceability** | Logs retrieved document chunks to audit source attribution for every response. |
| **Deterministic Fallback** | Triggers automated fallbacks when retrieval confidence fails quality thresholds. |

## How It Works

The architecture executes across four primary processing pipeline stages:

| Stage | Operation |
| --- | --- |
| **1. Chunk** | Partition raw source documents into uniform semantic text segments. |
| **2. Embed** | Project each chunk text into a continuous vector space $\mathbf{c} \in \mathbb{R}^{d}$. |
| **3. Retrieve** | Identify top-$k$ nearest neighbor chunks maximizing similarity to query vector $\mathbf{q}$. |
| **4. Generate** | Construct a prompt combining query $\mathbf{q}$ and context chunks $\{c_1, \dots, c_k\}$ for LLM inference. |

## Pseudocode

```
function rag_feedback(session):
    # Stage 1-2: Precomputed offline index
    index = load_index()

    # Stage 3: Retrieve
    query = build_query(session)
    query_vector = embed(query)
    chunks = top_k_similar(index, query_vector, k=4, min_sim=0.35)

    # Stage 4: Generate
    prompt = assemble_prompt(session, chunks)
    response = llm_generate(prompt)

    if is_valid(response):
        return response
    else:
        return fallback(session)
```

## Python Implementation (Runtime)

```python
def generate_feedback(session):
    try:
        index = load_index()
        query_vector = embed(build_query(session))
        chunks = retrieve(index, query_vector, top_k=4, min_sim=0.35)

        prompt = build_prompt(session, chunks)
        response = groq_generate(prompt)

        if validate(response, session):
            return save(session, response, status="generated")
        else:
            return save(session, fallback(session), status="fallback")

    except Exception:
        return save(session, fallback(session), status="fallback")
```

---

# RAG in PathGen

## What is RAG in PathGen?

The automated feedback engine responsible for persisting exactly one personalized post-session feedback record per student session.

It executes upon completion of **regular**, **additional**, **foundational**, and **activity** sessions. It is explicitly disabled for **pretest** and **posttest** diagnostic phases.

## Purpose

| Objective | Specification |
| --- | --- |
| **Supportive Feedback** | Delivers targeted, personalized *"Your Next Focus"* instructional guidance. |
| **Grounded in Content** | Extracted exclusively from verified Grade 7 curriculum lesson passages. |
| **Bounded Output Length** | Hard limit of $\le 180$ words tailored to target reading levels. |
| **High Availability** | Guaranteed response delivery via deterministic fallback routines. |
| **Isolated State Space** | Strictly read-only output; cannot modify mastery scores or routing logic. |

## Chunking Policy

Source material originates from database lesson models (deserialized from `content_source/lessons/*.json`).

| Chunk Parameter | Target Specification |
| --- | --- |
| **Target Chunk Size** | $350$ tokens |
| **Hard Maximum Size** | $500$ tokens |
| **Sliding Window Overlap** | $50$ tokens |
| **Policy Specification** | `lesson-blocks-v1` |
| Index Volume | One chunk per lesson when under 500 tokens. Actual: 3 chunks for the 3 short lessons. |

Each indexed chunk schema contains:
* Stable `chunk_id`
* `lesson_code`
* `skill_codes`
* `source_fingerprint`
* Raw `text` block
* High-dimensional dense embedding vector $\mathbf{c} \in \mathbb{R}^{1536}$

## Retrieval Policy

Vector similarity is evaluated using cosine similarity over normalized embeddings:

$$
\text{similarity}(\mathbf{q}, \mathbf{c}) = \frac{\mathbf{q} \cdot \mathbf{c}}{\|\mathbf{q}\| \|\mathbf{c}\|}
$$

| Retrieval Parameter | Value |
| --- | --- |
| **Top-$k$ Chunks Retained** | $k = 4$ |
| **Minimum Similarity Threshold** | $\text{similarity} \ge 0.35$ |
| **Tie-Breaking Rule** | Ascending lexical order on stable `chunk_id` |
| **Embedding Model** | `text-embedding-3-small` ($1536$-dimensional) |
| **Generation Model** | `gpt-oss-120b` (hosted via Groq API) |

## Context Window Prompt Bounds

| Context Region | Hard Limit |
| --- | --- |
| **Retrieved Lesson Context** | $6{,}000$ characters |
| **Session Performance Evidence** | $3{,}000$ characters |
| **Total Assembled Prompt** | $12{,}000$ characters |
| **Max Output Length** | $180$ words |

## Pseudocode in PathGen

```python
# Offline Pipeline — Executed during deployment build
function build_index():
    lessons = read_lessons_from_database()
    chunks = chunk_with_policy(lessons, version="lesson-blocks-v1")
    for chunk in chunks:
        chunk.embedding = openai_embed(chunk.text)
    save_to_file("retrieval_index/pathgen_lessons.v1.json", chunks)


# Runtime Pipeline — Executed upon eligible session submission
function generate_feedback(session):
    if session.type in ["pretest", "posttest"]:
        return  # RAG explicitly disabled

    try:
        index = load_index()
        query = build_query(session)
        query_vector = openai_embed(query)
        chunks = retrieve(index, query_vector, top_k=4, min_sim=0.35)
        prompt = assemble_prompt(session, chunks)
        response = groq_generate(prompt)

        if validate(response, session):
            save_feedback(session, response, status="generated")
        else:
            save_feedback(session, fallback(session), status="fallback")

    except Exception:
        save_feedback(session, fallback(session), status="fallback")
```

## How RAG Works in PathGen

```
Session completes (deterministic DB transaction committed)
    ↓
Check session phase type
    ↓
If pretest or posttest → Terminate (skip RAG)
    ↓
Construct query context: lesson_code, weak skills, errors, hint usage
    ↓
Generate query embedding vector q via OpenAI API
    ↓
Query pre-loaded vector index (cached in memory)
    ↓
Compute Cosine Similarity against all index chunks
    ↓
Filter & rank chunks: keep top k=4 where similarity >= 0.35
    ↓
Assemble LLM prompt (system instruction + performance evidence + chunks)
    ↓
Execute LLM inference call via Groq API (gpt-oss-120b)
    ↓
Validate generated output string against bounds
    ↓
If Valid → Persist record with status="generated"
If Invalid or Exception → Persist fallback with status="fallback"
    ↓
The orchestrator marks the parent `learning_session` completed with `completed_at`
```

## Output Validation Rules

| Validation Gate | Rejection Action |
| --- | --- |
| **Non-empty Response** | Reject if empty or whitespace-only |
| **Length Cap** | Reject if word count $> 180$ words |
| **Credential Safety** | Reject if system credentials/prompts leaked |
| **Answer Key Leakage** | Reject if unreleased item solution keys detected |
| **Action Consistency** | Reject if output contradicts Q-Learning routing decision |
| **Factual Integrity** | Reject if unverified scores or skills are introduced |

*Failing any single validation check forces immediate fallback execution.*

## Fallback Strategy

Deterministic fallback responses are synthesized exclusively from persisted performance records:

```text
You completed Lesson 1.
Strong: S5 (3/3 correct).
Needs practice: S1 (2/3 correct).
Next step: foundational practice on opposites.
```

* **Properties:** Identical state yields identical output text. $100\%$ reliable, zero runtime latency dependencies.

## Failure Modes & Handling

| Failure Scenario | Recovery Behavior |
| --- | --- |
| **Embedding API Failure** | Fallback triggered |
| **Index File Missing or Corrupted** | Fallback triggered |
| **Zero Chunks Pass Similarity Threshold** ($\text{sim} < 0.35$) | Fallback triggered |
| **LLM Provider API Timeout** | Fallback triggered |
| **LLM Generates Invalid Response** | Fallback triggered |
| **Database Persistence Retry Failure** | Retry once; enforce Fallback |
| **Idempotency Conflict / Duplicate Delivery** | Return existing `feedback_session_feedback` record |

*Zero failure modes propagate to or mutate core student learning state.*

## Crash Recovery Protocol

In the event of a system crash occurring between session database commit and feedback creation:

```sql
SELECT ls.id
FROM learning_session ls
LEFT JOIN feedback_session_feedback fsf ON fsf.session_id = ls.id
WHERE ls.status = 'submitted'
  AND fsf.id IS NULL
  AND ls.session_type IN ('regular', 'additional', 'foundational', 'activity');
```

For each identified session, the RAG service generates and persists deterministic fallback feedback.

The orchestrator marks the session completed. The RAG service only writes the feedback row.

*Execution bypasses BKT, Q-Learning, and route computation entirely.*

## System Capabilities and Boundaries

| Action | Allowed | Rationale |
| --- | --- | --- |
| **Modify Student Scores** | **No** | Scores are strictly calculated by item scoring logic. |
| **Update BKT Estimates** | **No** | BKT maintains exclusive domain over mastery probabilities. |
| **Determine Session Routing** | **No** | Q-Learning model governs all adaptive transitions. |
| **Grant Access Control** | **No** | Module permissions managed by auth settings. |
| **Trigger Diagnostic Phase** | **No** | Policy prohibits RAG execution on pre/posttests. |

*The RAG service writes exactly one row in `feedback_session_feedback`, populating `feedback_text`, `generation_status`, and optionally `model_name`. The orchestrator, not the RAG service, marks the parent `learning_session` as completed with `completed_at` during feedback finalization. RAG never updates scores, BKT, decisions, or path.*

## Directory and Module Organization

```
apps/feedback/
├── __init__.py
├── apps.py
├── admin.py
├── models.py                 # Defines feedback_session_feedback
├── services.py                # Pipeline orchestrator
├── selectors.py               # Read-only database query interface
├── prompts.py                 # System prompt templates
├── fallbacks.py              # Deterministic fallback text generators
├── providers/
│   ├── __init__.py
│   ├── base.py                # Provider interface definitions
│   ├── groq.py                # Groq API client (gpt-oss-120b)
│   └── openai_embeddings.py  # OpenAI embeddings client (text-embedding-3-small)
├── retrieval/
│   ├── __init__.py
│   ├── chunking.py            # lesson-blocks-v1 chunking implementation
│   ├── index.py              # Index loading & validation routines
│   └── similarity.py          # Vector cosine similarity ranking
├── management/commands/
│   └── build_retrieval_index.py
└── migrations/

retrieval_index/
├── README.md
├── index.schema.json
└── pathgen_lessons.v1.json    # Pre-built serialized index (~200KB)

content_source/lessons/
├── lesson_1.json              # Canonical curriculum source files
├── lesson_2.json
└── lesson_3.json
```

### Database Schema

`feedback_session_feedback` — Single feedback entry per session:

| Field | Type | Description |
| --- | --- | --- |
| `session` | Foreign Key (Unique) | Reference to Student Session |
| `feedback_text` | Text | Persisted feedback body string |
| `generation_status` | String Enum | `generated` or `fallback` |
| `model_name` | String (Nullable) | `gpt-oss-120b` or `null` (if fallback) |
| `created_at` | Timestamp | Record creation timestamp |

## Environment Configuration

```dotenv
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=gpt-oss-120b
OPENAI_API_KEY=your_openai_api_key_here
EMBEDDING_MODEL=text-embedding-3-small
```

## Management Commands

```bash
# Build retrieval index offline (run once per curriculum build)
python manage.py build_retrieval_index --settings=config.settings.local

# Run retrieval and feedback unit test suite
python manage.py test tests.test_phase10_retrieval tests.test_phase11_feedback --settings=config.settings.test --keepdb
```

## Curriculum Index Rebuild Order

```bash
# 1. Update source lesson definitions in content_source/lessons/*.json
# 2. Validate structural integrity
python manage.py validate_curriculum

# 3. Reseed database models
python manage.py seed_curriculum

# 4. Rebuild vector retrieval index
python manage.py build_retrieval_index
```

*Failure to reseed before rebuilding the index will result in stale embedding representations.*

---

## Technical Summary

| Dimension | Specification |
| --- | --- |
| **Core Architecture** | Retrieval-Augmented Generation (RAG) |
| **PathGen Function** | Generates a single supportive feedback message per eligible session |
| **Active Phases** | Regular, Additional, Foundational, Activity |
| **Bypassed Phases** | Pretest, Posttest |
| **Chunking Parameters** | Target $350$ tokens, Max $500$ tokens, Overlap $50$ tokens |
| **Retrieval Strategy** | Top $k=4$ chunks matching $\text{similarity} \ge 0.35$ |
| **Embedding Vector Model** | `text-embedding-3-small` ($1536$-dimensional space) |
| **Generation LLM** | `gpt-oss-120b` via Groq API |
| **Max Prompt Allocation** | $12{,}000$ characters total |
| **Max Response Size** | $180$ words |
| **Core Module** | `apps/feedback/` |
| **Index Artifact** | `retrieval_index/pathgen_lessons.v1.json` |
| **Database Table** | `feedback_session_feedback` |
| **Fallback Mechanism** | Deterministic, template-based state summary |
| **State Side Effects** | None (strictly isolated read-only output) |
