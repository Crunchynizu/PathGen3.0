# PathGen 3.0 — Folder File Structure

Complete layout for the Django application.

## pathgen3.0app/ — complete app tree

```text
pathgen3.0app/
|
|-- manage.py
|-- requirements.txt
|-- .env                                   (gitignored)
|-- .env.example
|-- .gitignore
|-- AGENTS.md
|-- README.md
|-- config/
|   |-- __init__.py
|   |-- asgi.py
|   |-- wsgi.py
|   |-- urls.py
|   `-- settings/
|       |-- __init__.py
|       |-- base.py
|       |-- local.py
|       |-- production.py
|       `-- test.py
|
|-- content_source/
|   |-- README.md
|   |-- manifest.json
|   |-- media_manifest.json
|   |-- activity.json
|   |-- pretest_posttest.json
|   |-- lessons/
|   |   |-- lesson_1.json
|   |   |-- lesson_2.json
|   |   `-- lesson_3.json
|   `-- transcripts/
|       |-- VID-INTEGER-NUMBER-LINE.txt
|       |-- VID-INTEGER-ADD-SUBTRACT.txt
|       |-- VID-INTEGER-MULTIPLY-DIVIDE.txt
|       `-- VID-INTEGER-ORDER-OPERATIONS.txt
|
|-- apps/
|   |-- __init__.py
|   |
|   |-- accounts/
|   |   |-- __init__.py
|   |   |-- apps.py
|   |   |-- admin.py
|   |   |-- models.py
|   |   |-- urls.py
|   |   |-- views.py
|   |   |-- forms.py
|   |   |-- admin_forms.py
|   |   |-- services/
|   |   |   |-- __init__.py
|   |   |   `-- lifecycle.py
|   |   |-- selectors.py
|   |   |-- permissions.py
|   |   |-- validators.py
|   |   |-- sessions.py
|   |   |-- throttling.py
|   |   |-- middleware.py
|   |   |-- migrations/
|   |   |   |-- __init__.py
|   |   |   `-- 0001_initial.py
|   |   `-- management/
|   |       |-- __init__.py
|   |       `-- commands/
|   |           |-- __init__.py
|   |           `-- bootstrap_admin.py
|   |
|   |-- classrooms/
|   |   |-- __init__.py
|   |   |-- apps.py
|   |   |-- admin.py
|   |   |-- models.py
|   |   |-- urls.py
|   |   |-- views.py
|   |   |-- forms.py
|   |   |-- services/
|   |   |   |-- __init__.py
|   |   |   `-- lifecycle.py
|   |   |-- selectors.py
|   |   |-- permissions.py
|   |   |-- validators.py
|   |   `-- migrations/
|   |       |-- __init__.py
|   |       `-- 0001_initial.py
|   |
|   |-- curriculum/
|   |   |-- __init__.py
|   |   |-- apps.py
|   |   |-- admin.py
|   |   |-- models.py
|   |   |-- urls.py
|   |   |-- views.py
|   |   |-- forms.py
|   |   |-- services.py
|   |   |-- selectors.py
|   |   |-- permissions.py
|   |   |-- validators.py
|   |   |-- schemas.py
|   |   |-- seed.py
|   |   |-- schemas/
|   |   |   |-- lesson.schema.json
|   |   |   |-- activity.schema.json
|   |   |   |-- prepost.schema.json
|   |   |   |-- media.schema.json
|   |   |   |-- manifest.schema.json
|   |   |   `-- transcript.schema.json
|   |   |-- fixtures/
|   |   |   `-- .gitkeep
|   |   |-- management/
|   |   |   |-- __init__.py
|   |   |   `-- commands/
|   |   |       |-- __init__.py
|   |   |       |-- seed_curriculum.py
|   |   |       `-- validate_curriculum.py
|   |   `-- migrations/
|   |       |-- __init__.py
|   |       `-- 0001_initial.py
|   |
|   |-- learning/
|   |   |-- __init__.py
|   |   |-- apps.py
|   |   |-- admin.py
|   |   |-- models.py
|   |   |-- urls.py
|   |   |-- views.py
|   |   |-- forms.py
|   |   |-- interfaces.py
|   |   |-- services/
|   |   |   |-- __init__.py
|   |   |   |-- paths.py
|   |   |   |-- sessions.py
|   |   |   `-- responses.py
|   |   |-- selectors.py
|   |   |-- permissions.py
|   |   |-- validators.py
|   |   |-- transitions.py
|   |   `-- migrations/
|   |       |-- __init__.py
|   |       `-- 0001_initial.py
|   |
|   |-- adaptive/
|   |   |-- __init__.py
|   |   |-- apps.py
|   |   |-- admin.py
|   |   |-- models.py
|   |   |-- bkt.py
|   |   |-- q_learning.py
|   |   |-- q_table.json
|   |   |-- services.py
|   |   |-- selectors.py
|   |   |-- validators.py
|   |   `-- migrations/
|   |       |-- __init__.py
|   |       `-- 0001_initial.py
|   |
|   |-- feedback/
|   |   |-- __init__.py
|   |   |-- apps.py
|   |   |-- admin.py
|   |   |-- models.py
|   |   |-- services.py
|   |   |-- selectors.py
|   |   |-- prompts.py
|   |   |-- fallbacks.py
|   |   |-- providers/
|   |   |   |-- __init__.py
|   |   |   |-- base.py
|   |   |   |-- groq.py
|   |   |   `-- openai_embeddings.py
|   |   |-- retrieval/
|   |   |   |-- __init__.py
|   |   |   |-- chunking.py
|   |   |   |-- index.py
|   |   |   `-- similarity.py
|   |   |-- management/
|   |   |   |-- __init__.py
|   |   |   `-- commands/
|   |   |       |-- __init__.py
|   |   |       `-- build_retrieval_index.py
|   |   `-- migrations/
|   |       |-- __init__.py
|   |       `-- 0001_initial.py
|   |
|   `-- core/
|       |-- __init__.py
|       |-- apps.py
|       |-- admin.py
|       |-- models.py
|       |-- urls.py
|       |-- views.py
|       |-- forms.py
|       |-- admin_urls.py
|       |-- admin_views.py
|       |-- services/
|       |   |-- __init__.py
|       |   |-- settings.py
|       |   `-- audit.py
|       |-- selectors.py
|       |-- permissions.py
|       |-- validators.py
|       |-- metrics.py
|       |-- middleware.py
|       |-- context_processors.py
|       |-- health.py
|       `-- migrations/
|           |-- __init__.py
|           `-- 0001_initial.py
|
|-- templates/
|   |-- components/
|   |   |-- sidebar.html
|   |   |-- hamburger_menu.html
|   |   |-- breadcrumbs.html
|   |   `-- back_link.html
|   |
|   |-- pages/
|   |   |-- _base.html
|   |   |-- admin/
|   |   |   |-- admin_dashboard.html
|   |   |   |-- user_management.html
|   |   |   |-- class_management.html
|   |   |   |-- override.html
|   |   |   `-- audit_logs.html
|   |   |-- teacher/
|   |   |   |-- teacher_dashboard.html
|   |   |   |-- my_class.html
|   |   |   `-- class_detail.html
|   |   |-- student/
|   |   |   |-- student_dashboard.html
|   |   |   |-- my_lesson.html
|   |   |   `-- lesson.html
|   |   |-- shared/
|   |   |   |-- content.html
|   |   |   |-- view_lessons.html
|   |   |   |-- view_questions.html
|   |   |   `-- view_student_progress.html
|   |   `-- account/
|   |       |-- login.html
|   |       `-- my_account.html
|   |
|   |-- assessment/
|   |   `-- assessment.html
|   |
|   |-- error/
|   |   `-- error.html
|   |
|   `-- modals/
|       (unchanged structure, 24 files)
|
|-- static/
|   |-- css/
|   |   |-- theme.css                      (tokens, base, shared components)
|   |   |-- shell.css                      (main, secondary, focus, standalone shells)
|   |   |-- modals.css                     (shared dialog styling)
|   |   `-- pages/
|   |       |-- admin_dashboard.css
|   |       |-- user_management.css
|   |       |-- class_management.css
|   |       |-- student_list.css
|   |       |-- override.css
|   |       |-- audit_logs.css
|   |       |-- teacher_dashboard.css
|   |       |-- my_class.css
|   |       |-- student_dashboard.css
|   |       |-- my_lesson.css
|   |       |-- lesson.css
|   |       |-- content.css
|   |       |-- view_class_detail.css
|   |       |-- view_lesson.css
|   |       |-- view_lesson.detail.css
|   |       |-- view_questions.css
|   |       |-- view_student_progress_detail.css
|   |       |-- my_account.css
|   |       |-- login.css
|   |       |-- assessment.css
|   |       `-- error.css
|   |
|   |-- logo/
|   |   `-- pathgen.png
|   |
|   |-- avatar/
|   |   |-- student_avatar.png
|   |   |-- teacher_avatar.png
|   |   `-- admin_avatar.png
|   |
|   |-- lesson/
|   |   |-- lesson-1/
|   |   |   |-- integer-number-line.png
|   |   |   `-- opposites-example.png
|   |   |-- lesson-2/
|   |   |   |-- chip-model-zero-pairs.png
|   |   |   `-- sign-rules.png
|   |   `-- lesson-3/
|   |       |-- operation-order-steps.png
|   |       `-- temperature-change.png
|   |
|   |-- exercise/
|   |   |-- lesson-1/
|   |   |   |-- L1-R-S1-03.png
|   |   |   |-- L1-R-S5-03.png
|   |   |   |-- L1-A-S1-02.png
|   |   |   |-- L1-A-S5-03.png
|   |   |   |-- L1-F-S1-03.png
|   |   |   `-- L1-F-S5-02.png
|   |   |-- lesson-2/
|   |   |   |-- L2-R-S2-02.png
|   |   |   |-- L2-R-S3-03.png
|   |   |   |-- L2-A-S2-02.png
|   |   |   |-- L2-A-S3-03.png
|   |   |   |-- L2-F-S2-02.png
|   |   |   `-- L2-F-S3-03.png
|   |   `-- lesson-3/
|   |       |-- L3-R-S4-01.png
|   |       |-- L3-R-S6-01.png
|   |       |-- L3-A-S4-01.png
|   |       |-- L3-A-S6-01.png
|   |       |-- L3-F-S4-01.png
|   |       `-- L3-F-S6-01.png
|   |
|   |-- activity/
|   |   `-- whole-course/
|   |       |-- ACT-S1-01.png
|   |       `-- ACT-S2-01.png
|   |
|   `-- vendor/
|       |-- lucide/
|       |   `-- lucide.min.js
|       `-- chartjs/
|           `-- chart.umd.js
|
|-- retrieval_index/
|   |-- README.md
|   |-- index.schema.json
|   `-- pathgen_lessons.v1.json
|
|-- locale/
|   `-- .gitkeep
|
|-- tests/
|   |-- __init__.py
|   |-- factories.py
|   |-- test_phase2_schema.py
|   |-- test_phase2_constraints.py
|   |-- test_phase2_migrations.py
|   |-- test_phase3_auth.py
|   |-- test_phase3_authorization.py
|   |-- test_phase3_bootstrap.py
|   |-- test_phase3_lifecycle.py
|   |-- test_phase3_throttling.py
|   |-- test_phase4_settings.py
|   |-- test_phase4_classrooms.py
|   |-- test_phase4_management_views.py
|   |-- test_phase5.py
|   |-- test_phase6.py
|   |-- test_phase7_bkt.py
|   |-- test_phase8_q_learning.py
|   |-- test_phase10_retrieval.py
|   |-- test_phase11_feedback.py
|   |-- integration/
|   |   |-- test_full_student_path.py
|   |   |-- test_adaptive_branches.py
|   |   |-- test_prepost_matching.py
|   |   |-- test_access_overrides.py
|   |   `-- test_research_metrics.py
|   |-- e2e/
|   |   |-- test_role_navigation.py
|   |   |-- test_assessment_flow.py
|   |   |-- test_video_question.py
|   |   `-- test_keyboard_accessibility.py
|   `-- accessibility/
|       `-- test_templates.py
|
`-- scripts/
    |-- check.sh
    |-- validate_curriculum_source.py
    `-- release.sh
```

## Figure rules

- Avatars (`student_avatar.png`, `teacher_avatar.png`, `admin_avatar.png`) and logo (`pathgen.png`) are real committed files. They are **not** placeholders.
- Lesson content figures under `static/lesson/` are 1x1 transparent placeholders until the user replaces them.
- Exercise and activity figures under `static/exercise/` and `static/activity/` are 1x1 transparent placeholders until the user replaces them.
- Prompt-level figures only. A figure lives on `curriculum_question.image_asset`. Never on a choice.
- There is no `static/pretest_posttest/` folder.
- PP-13, PP-23, PP-26 have text choices.
- Prompt figures follow `static/{lesson,exercise,activity}/<lesson_slug>/<question_code>.png`.
- Icons are Lucide library only. No individual SVG files.
- Use `<i data-lucide="name"></i>`. Call `createIcons()` after `DOMContentLoaded`.
- Videos use real YouTube IDs and timestamps from `content_source/media_manifest.json`.
- Lesson content renders as a designed reading experience, not a JSON dump.
- Every page extends `pages/_base.html`. Page type is a rule, not a file.
