# build_order.md

Implementation sequence for PathGen 3.0.

---

## Phase 0 — Baseline frozen

Specs, seed JSON, and policy constants are already decided. No code.

---

## Phase 1 — Bootstrap

**Build:**
- Django monolith
- Settings split (base, local, production, test)
- Custom user model set as `AUTH_USER_MODEL`
- 7 empty app shells
- `/health/` endpoint
- Console logging
- Tailwind standalone CLI + `input.css`
- `.env.example`, `.gitignore`
- `Procfile`
- Test framework configured against PostgreSQL

**Do not:** any models beyond User, any UI, any auth flow.

**Exit:** `manage.py check` passes on local, test, production.

---

## Phase 2 — Schema

**Build:**
- 22 domain tables
- Constraints, indexes, partial uniqueness
- Append-only triggers on 3 tables
- Migration tests
- Factory helpers

**Do not:** any views, any services, any UI.

**Exit:** migrations apply and roll back. Direct DB constraint tests pass.

---

## Phase 3 — Authentication, RBAC, lifecycle

**Build:**
- Login / logout
- Role permissions (admin, teacher, student)
- Scoped selectors
- Own name + password change
- `bootstrap_admin` command
- Account lifecycle (create, deactivate, reactivate)
- Session invalidation
- Audit service
- Login throttling

**Do not:** any dashboard, any curriculum, any engines.

**Exit:** role matrix tests pass. Class-free student access works.

---

## Phase 4 — Settings, classes, shared shell

**Build:**
- Singleton settings + revision checks
- Global override page
- Class + teacher + membership lifecycle
- 4 base templates
- Sidebar, mobile nav
- Modal framework
- 20 partials
- 24 modals
- Admin + teacher pages

**Do not:** curriculum import, sessions, engines.

**Exit:** settings conflicts fail safely. Class membership never gates learning.

---

## Phase 5 — Content source, assets, and seeding

**Purpose:** Extract the source PDFs into JSON, copy source assets, validate, and seed the curriculum database.

### Inputs

- `../pathgen3.0docs/content/lesson.pdf` — curriculum
- `../pathgen3.0docs/content/pretest_posttest.pdf` — protected assessment
- `../pathgen3.0docs/content/avatar/*.png`
- `../pathgen3.0docs/content/logo/pathgen.png`
- `../pathgen3.0docs/assets/css/theme.css`

`../pathgen3.0docs/` is read-only. Never modify it.

### Step 1 — Extract PDFs into JSON

Read both PDFs and write:

```
content_source/
├── manifest.json
├── media_manifest.json
├── activity.json
├── pretest_posttest.json
├── lessons/
│   ├── lesson_1.json
│   ├── lesson_2.json
│   └── lesson_3.json
└── transcripts/
    ├── VID-INTEGER-NUMBER-LINE.txt
    ├── VID-INTEGER-ADD-SUBTRACT.txt
    ├── VID-INTEGER-MULTIPLY-DIVIDE.txt
    └── VID-INTEGER-ORDER-OPERATIONS.txt
```

Rules:

- 3 lessons, 6 skills.
- 94 questions total: 18 regular, 18 additional, 18 foundational, 10 activity, 30 pre/post.
- Every question has exactly 4 choices labeled A–D and exactly one correct answer.
- **All 4 choices on every question are text-only. Never use `image_asset` on `curriculum_question_choice`.**
- Pre/post set: 30 items in fixed order PP-01 to PP-30.
- PP-13, PP-23, PP-26 are text-only. Do not extract choice images. Use the text choices already present in the PDF for PP-23 and PP-26. For PP-13, rewrite as a text-only item that tests representations of -4, with four text choices and one keyed answer. Record the rewrite in `manifest.json` under a `prepost_rewrites` key.
- Include SHA-256 of `../pathgen3.0docs/content/pretest_posttest.pdf` in `manifest.json`.
- Bloom labels: 4 LOTS / 2 HOTS per regular and additional exercise, 2 LOTS / 1 HOTS per foundational skill block, 6 LOTS / 4 HOTS for the activity.
- Activity distribution: S1=2, S2=2, S3=2, S4=2, S5=1, S6=1.
- Scoring: `SCORING-V2` — 2 of 3 correct passes a skill.
- Bloom labels are metadata only. They never affect scoring, BKT, routing, selection, or access.

### Step 2 — Copy source assets

```
../pathgen3.0docs/content/avatar/student_avatar.png  →  static/avatar/student_avatar.png
../pathgen3.0docs/content/avatar/teacher_avatar.png  →  static/avatar/teacher_avatar.png
../pathgen3.0docs/content/avatar/admin_avatar.png    →  static/avatar/admin_avatar.png
../pathgen3.0docs/content/logo/pathgen.png            →  static/logo/pathgen.png
```

### Step 3 — Prompt figures

- All lesson, exercise, and activity figures are 1x1 transparent placeholders. Do not extract or replace them.
- Avatars and logo are copied from `content/` as real files.
- Prompt-level figures only. Never on a choice.

### Step 4 — Build

- JSON schemas under `apps/curriculum/schemas/`
- `validate_curriculum` management command
- `seed_curriculum` management command
- PDF SHA-256 verification
- Read-only Content pages: `shared/content.html`, `shared/view_lessons.html`, `shared/view_questions.html`

### Step 5 — Verify

- `validate_curriculum` passes.
- `seed_curriculum` imports all rows.
- Counts match `manifest.json`: 94 total, 30 pre/post, 18 regular, 18 additional, 18 foundational, 10 activity.
- Every question has exactly 4 text choices labeled A–D and exactly one correct answer.
- No `curriculum_question_choice` has `image_asset` set.
- Pre/post set excluded from Content pages.
- Avatars and logo present in `static/`.
- PDF SHA-256 matches `manifest.json`.

### Do not

- Implement sessions, responses, BKT, Q-Learning, or RAG.
- Expose pre/post answer keys in any rendered page.
- Change the fixed PP-01 to PP-30 order.
- Add `image_asset` to `curriculum_question_choice`.
- Extract number-line choice images for PP-13, PP-23, PP-26.

### Exit

All Step 5 checks pass.

---

## Phase 6 — Sessions and assessment UI

**Build:**
- Path state machine
- Session issuance with row locks
- Response service with idempotency
- One-question-at-a-time UI (4 assessment types)
- Overview → Assessment → Result flow
- Immediate vs delayed feedback rules
- Hint tracking (foundational only)
- Video cue pause
- Exit confirmation
- My Lesson stepper

**Do not:** any BKT, Q-Learning, or RAG.

**Exit:** post-test creates zero BKT events (stub). Duplicate POST is idempotent.

---

## Phase 7 — BKT engine

**Build:**
- `bkt.py` with 3 formulas
- Parameters: P(L0)=0.30, P(T)=0.09, P(G)=0.10, P(S)=0.09
- Phase rules (pretest, posttest, hinted)
- Row locking per (student, skill)
- Append-only mastery events

**Do not:** any routing, any feedback.

**Exit:** formula tests pass. Posttest creates no event. Hinted path skips posterior.

---

## Phase 8 — Q-Learning engine

**Build:**
- `q_learning.py` — loader + `decide()`
- `q_table.json` — frozen artifact (from external trainer)
- Decision persistence to `adaptive_decision`
- Action masking per context
- Fallback to `progress` on any failure
- Safety cap: 3 fails → force progress

**Do not:** the trainer. Training happens externally.

**Exit:** loader validates artifact. Fallback works when file missing. Argmax is deterministic.

---

## Phase 9 — Orchestrator

**Build:**
- Atomic transactions: response → BKT → scoring → Q-Learning → path
- Row locks across path and session
- Crash recovery
- Failure matrix tests
- Fixed transitions

**Do not:** any RAG.

**Exit:** no partial state on failure. Concurrency tests pass.

---

## Phase 10 — RAG ingestion

**Build:**
- `lesson-blocks-v1` chunking (350/500/50)
- Stable chunk IDs + fingerprints
- OpenAI `text-embedding-3-small` embeddings
- `build_retrieval_index` command
- Versioned index at `retrieval_index/pathgen_lessons.v1.json`
- Loader with staleness check
- In-memory cosine retrieval (top 4, min 0.35)

**Do not:** any Groq calls, any feedback writes.

**Exit:** rebuild is deterministic. Stale index is refused.

---

## Phase 11 — RAG generation

**Build:**
- Groq `gpt-oss-120b` adapter
- Prompt assembly with bounds (12,000 chars, 180 words)
- Output validation
- Deterministic fallback
- Unique feedback per session
- Crash recovery for pending feedback

**Do not:** any dashboards.

**Exit:** every applicable session ends with generated or fallback feedback.

---

## Phase 12 — Dashboards

**Build:**
- Admin dashboard (KPIs, charts, audit preview)
- Teacher dashboard (follow-up first, then charts)
- Student dashboard (Next Step, path, skills, feedback, results)
- `view_student_progress.html`
- Chart.js with accessible tables
- Versioned metric definitions in `core/metrics.py`

**Do not:** any new data sources.

**Exit:** every chart states cohort, N, definition. Empty states distinct from zero.

---

## Phase 13 — Hardening

**Build:**
- Threat model review
- CSRF, cookies, host headers, proxy config
- Role/object leakage tests
- Keyboard, screen-reader, zoom, reduced-motion checks
- WCAG 2.2 AA verification
- Query count and index review
- Retrieval latency measurement

**Do not:** add new features.

**Exit:** no high-severity findings. Accessibility passes.

---

## Phase 14 — End-to-end acceptance

**Build:**
- Full path tests
- Both adaptive branches (additional, foundational)
- Matched pre/post reporting
- BKT + Q-Learning provenance replay
- Audit immutability verification
- Posttest creates zero BKT events
- Concurrency and recovery scenarios

**Do not:** skip any acceptance test.

**Exit:** acceptance suite maps to every spec. Metrics reconcile with raw evidence.

---

## Phase 15 — Deploy to Railway

Before Phase 15, run `build_order_must.md` Fix phases 1 through 8. Phase 14 flows into `build_order_must.md`, not directly into Phase 15. Phase 15 only starts after Fix 8 passes.

**Build:**
- Railway web service with Gunicorn
- Managed PostgreSQL
- WhiteNoise static
- Railway env variables
- Release command: `migrate --noinput`
- Health check
- Backup and rollback runbook
- Admin bootstrap procedure
- Reseed curriculum on Railway

**Do not:** commit `.env` or secrets.

**Exit:** staging deploy passes smoke tests. Rollback rehearsed. Production keys exist only in Railway.

---

## Final release gate

- `build_order_must.md` Fix 1 through 8 are complete. No template uses the old base/partial structure. `input.css` is 3 lines. `static/icon/` does not exist.
- All canonical specs consistent with implementation.
- All V1 policy constants match `manifest.json`.
- No protected history destructively cascaded.
- BKT, Q-Learning, RAG boundaries enforced in code and tests.
- Role scope, class optionality, settings gates, posttest no-BKT all pass end-to-end.
- Every decision carries `policy_version`.
- External trainer produces `q_table.json` matching the contract.
- Prompt-level figures present at their expected paths (real or placeholder).
- No `curriculum_question_choice` has `image_asset` set.
- Pre/post set is text-only, including PP-13, PP-23, PP-26.
- PP-13 rewrite is documented in `manifest.json` under `prepost_rewrites`.

---

## Phase summary

| Phase | Focus |
|---|---|
| 0 | Baseline frozen |
| 1 | Bootstrap |
| 2 | Schema (22 tables) |
| 3 | Auth + RBAC |
| 4 | Settings + classes + shell |
| 5 | Content source, assets, seeding |
| 6 | Sessions + assessment UI |
| 7 | BKT engine |
| 8 | Q-Learning engine |
| 9 | Orchestrator |
| 10 | RAG ingestion |
| 11 | RAG generation |
| 12 | Dashboards |
| 13 | Hardening |
| 14 | End-to-end acceptance |
| 15 | Deploy to Railway |

**16 phases total (0–15).**

---

## Summary of changes vs previous version

1. **Phase 5** — fully replaced. Paths corrected to `../pathgen3.0docs/content/`. Text-only choices rule added. PP-13, PP-23, PP-26 handled. Counts, Bloom, activity distribution, and scoring corrected.
2. **Final release gate** — added three bullets (no choice images, pre/post text-only, PP-13 rewrite documented) and changed "All figures" to "Prompt-level figures".
3. **Phase summary** — Phase 5 label updated to "Content source, assets, seeding".
