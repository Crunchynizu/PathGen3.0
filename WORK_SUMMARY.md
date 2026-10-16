# PathGen 3.0 (ours): what was done, and what is left

For the PathGen team. Everything here is in `pathgen3.0-ours/` unless it says otherwise. The groupmate's original `pathgen3.0-workspace/` was not changed.

All 298 automated tests pass.

---

## 1. Q-learning trial v3 (`../q-learning-test-v3/`)

The trial was rerun with the Lesson 2 split before any app code changed. It is built on v2, which had passed at 75,000 episodes.

**What was added: a second set of states for the Lesson 2 parts.**

| | Lessons 1 and 3 | Lesson 2 parts (2.1, 2.2, 2.3) |
|---|---|---|
| Exercise | 6 items: 2 skills × 3 | 6 items: 1 skill × 6 |
| A skill passes with | 2 of 3 | 4 of 6 |
| State | (weakest band, average band, pass/fail per skill) | (band, band, pass/fail) |
| Foundational exercise | 3 items per failed skill | 3 items |
| After a pass | Q-learning decides | Always move on to the next part (team rule) |
| After a fail | Q-learning decides | Stay on the same part (additional / foundational), never back to an earlier part |

**Result: PASS.**
- **Weight pairs:** 24 of 30 pass the checks for both state sets. The selected pair (burden 0.02, completion 0.02) is the same one v2 used.
- **Training:** 75,000 episodes per seed, 10 seeds. Every state–action pair got at least 563 updates.
- **Output:** a 30-row Q-table, now installed at `pathgen3.0app/apps/adaptive/q_table.json`.
- **Lessons 1 and 3:** their rows are identical to v2, so the Lesson 2 split did not change their policy.

**Why the "pass = move on" rule exists:** left to itself, training gives every student who passes a part an extra 6-item exercise, even at "Strong". That is because the simulated student never gets tired. The team chose to keep the rule, and to keep Lessons 1 and 3 as trained.

**Every exercise is capped at three tries:** regular → additional → foundational, then the student moves on whether they pass or fail. There is also a safety cap: after 3 fails on one skill, the student is moved on and flagged for the teacher.

Details: `../q-learning-test-v3/output/training_report.md`.

---

## 2. Lesson 2 taught in three parts

Students still see **Lessons 1–3**. Lesson 2 shows as one lesson with three parts inside it.

- **Data:** each part is its own lesson record (`L2-1`, `L2-2`, `L2-3`), grouped as unit 2. Lesson 3 moved to lesson order 5.
- **Skills (now 7):**
  - S3 is now **Multiply integers**;
  - new **S7 Divide integers**;
  - 9 existing items were retagged from S3 to S7 (tag only; wording, choices and keys unchanged), including PP-06, PP-17, PP-25 and PP-30. PP-17 mixes × and ÷ and counts as division.
- **Questions:** 121 in total. **27 are new drafts** for the Lesson 2 parts and need team review (see section 7).
- **Scoring:** SCORING-V3, a skill passes with two-thirds correct (2 of 3, or 4 of 6).
- **Updated screens:** My Lesson, the dashboard, results, the teacher decision chart ("Lesson 2.1" labels) and the content page (counts 3 lessons, not 5).
- **AI feedback:** the retrieval index used for the AI feedback was rebuilt for the new lessons (`retrieval_index/pathgen_lessons.v1.json`).

---

## 3. Student screens

**Colour pass (dashboard, My Lesson, lesson pages)**
- **Backdrop:** soft colour washes over a faint dot grid instead of flat white.
- **Cards:** tinted in their colour, with a stronger tint on the header strip. Items inside stay white so they stand out.
- **Lesson parts:** each part is tinted in its lesson's colour (Lesson 1 teal, Lesson 2 violet, Lesson 3 amber).

**Bugs fixed**
- **Wrong lesson colour:** every lesson showed Lesson 1's teal; a CSS rule overrode the lesson colour.
- **Staff styles on student pages:** styles meant for teacher/admin pages also hit student pages. That moved "My Lesson" to the right and changed some buttons and badges on My Lesson and My Account.
- **Feedback shown twice:** after answering, the explanation appeared twice. 91 questions repeat their explanation word for word as feedback; it now shows once, under "Why". The question content itself is unchanged.

**`gamified_vibe`: experiment, can be rolled back**

A game *feel* with no game mechanics: no points, stars, badges, streaks, rewards, mascot or leaderboard. It has:
- dark outlines with solid shadows;
- chunky buttons that press down;
- sticker-style icons;
- bouncy entrances;
- a trail-style path where the current stop hops;
- striped progress bars;
- drifting + − × ÷ symbols in the background.

It covers the dashboard, My Lesson, lessons, exercises and the Activity. **The pre-test and post-test are excluded**, so they stay identical to each other.

To roll back: delete one line in `templates/_base.html` and the file `static/css/gamified_vibe.css` (see `GAMIFIED_VIBE.md`).

---

## 4. Teacher, admin and error pages

All remaining unstyled pages were restyled, phone first:
- override settings, users, classes and audit logs;
- teacher and admin dashboards, my classes, class detail and student progress;
- content, lessons and questions;
- the error page and 22 dialogs.

On phones, tables turn into stacked cards and filters fold away.

Also fixed: the teacher/admin charts drew in grey because some colour settings were missing.

---

## 5. Earlier fixes still in place

- **Q-table:** the trained table replaces the placeholder that was in the original app.
- **Finished sessions never completed:** exercises stayed "submitted" forever, so there was no result page and no feedback. Sessions are now finished right after the last answer.
- **Exercise feedback:** now shown right on the question; the answer is marked, with an explanation.
- **Lessons:** hands-on lesson pieces were added: number line, chips, sign grid, order-of-operations steps, thermometer, step reveal, spot the mistake.

---

## 6. Things we checked and decided to leave as they are

- **BKT order effect.** With the current settings (guess 0.10, slip 0.09), the last two or three answers decide the mastery band. Examples:
  - a student who gets 3 of 6 but ends on three right answers is rated "Strong";
  - 2 of 6 can also end "Strong".

  The app and the Q-learning trainer use the same formula, so they agree with each other.
  - **Lesson 2 parts:** not affected; a fail never moves the student on early.
  - **Lessons 1 and 3:** a student who failed one skill can still be moved on when both skills end "Strong". Q-learning's scores for the choices are nearly tied there. The failed skill is flagged for the teacher.
  - **Decision:** keep the settings and keep the bands as shown. **Mention this in the thesis as a known BKT limitation.**
- **Lesson rules:** Lessons 1, 2 and 3 keep their current rules (see section 1).

---

## 7. To do / to check before students use it

**Content (team)**
- [ ] Review the **27 draft questions** and the new Lesson 2 text in `LESSON2_PARTS_REVIEW.md`. Each draft is marked as pending teacher review in the content files.
- [x] Lesson 3 "common mistake" said *"Correct order gives 14"*, but −3 × (−4) + (−18) ÷ 6 = **9** (the 14 belongs to the worked example). **Fixed to 9.**
- [x] AI-feedback index rebuilt after the Lesson 3 fix (it matches the current lesson text).
- [x] **Lesson 1 video hidden.** Its YouTube video ("Negative numbers and number-line examples", ID `qW-Ce44lI0Q`) was removed from YouTube ("This video is unavailable"). Students saw a black broken player. The ID is now removed from `content_source/media_manifest.json`, so:
  - Lesson 1 shows "Video not yet available. Keep reading, or open the transcript";
  - Activity question **ACT-S5-01** ("After the number-line segment, which is greatest…") shows the question straight away. It can be answered without the video.

  The other three videos (Lessons 2.1, 2.2/2.3 and 3, all Khan Academy) were checked and still work. The tests were updated to match.
- [ ] **Optional: replace the Lesson 1 video.** Pick a working YouTube video on negative numbers and the number line, plus the clip's start and end times (the old clip was 1:00–1:50; the Activity question pauses at the clip's end). Then put its ID back in `media_manifest.json` (`youtube_video_id` and `youtube_url`). The transcript file is still a placeholder too.
- [ ] 6 of the 10 Activity items are word-for-word copies of regular-exercise items (ACT-S2-02, S3-01, S3-02, S4-01, S4-02, S6-01). Students may already have seen their answers. Decide whether to keep them.
- [ ] Lesson, exercise and activity **figures are still 1×1 placeholders**; replace them, or accept "Picture coming soon".
- [x] **`gamified_vibe`: keep.** The adviser reviewed it on 2026-10-08: more engaging for G7 students (UI and game feel), and the questions are fine.

**Docs**
- [ ] `pathgen3.0app/AGENTS.md` still says 6 skills, 94 questions and SCORING-V2. It is now 7 skills, 121 questions and SCORING-V3, with Lesson 2 in parts. Update it, and any spec in `pathgen3.0docs/` that repeats those numbers (owner: groupmate).

**Security: reviewed, all checks pass.** Checked with the production settings:
- [x] Django's production checklist (`check --deploy`): no issues.
- [x] Production settings: `DEBUG` off, required secret key / hosts / CSRF origins (it refuses to start without them), HTTPS redirect, HSTS, Secure + HttpOnly cookies, clickjacking and no-sniff headers.
- [x] `.env` was never committed to git.
- [x] Every page needs login and the right role, except the login page, the home redirect and the health check.
- [x] Live checks:
  - a student gets "not found" for another student's sessions and results;
  - students and teachers are blocked from admin pages;
  - logged-out users are sent to login;
  - a form sent without its security token (CSRF) is rejected;
  - http redirects to https;
  - repeated wrong passwords are slowed down (429).
- [x] No unsafe HTML output (only form help text written by developers), and no raw SQL built from user input. The login `next` redirect is checked.
- [x] **Fixed:** the friendly error page existed but was never used. Wrong or blocked addresses showed Django's bare "Not Found" text; they now show PathGen's error page, with no technical details.
- [ ] Optional, not done: a Content-Security-Policy header. It would need care because of the YouTube embeds, Google Fonts and inline progress-bar widths, so it is not worth the risk this close to the run.

**Browser console**
- [x] No `console.log` or `debugger` left in `static/js/`.
- [ ] Open each page with the browser's developer tools (F12 → Console) and note any red errors. Cover the student pages (dashboard, My Lesson, a lesson, an exercise, a result) and the teacher and admin pages. Agents are not allowed to drive a browser here (AGENTS.md), so this one is manual.

**Before students use it**
- [ ] Deploy using section 8.
- [ ] Do a full run on a real phone: login → pre-test → Lessons 1, 2.1–2.3, 3 → Activity → post-test.
- [ ] Freeze the exercise and test screens before the pre-test, so the pre-test and post-test look the same.

---

## 8. Deploying (Railway or any host that reads a Procfile)

**Already made deploy-ready:**
- **Production build:** it failed because the bundled Chart.js and Lucide files pointed to `.map` debug files that are not included. Those two comment lines were removed; charts and icons work the same.
- **Start command (`Procfile`):** now runs migrations, builds the static files, then starts the server, all with the production settings named explicitly. Before, these commands could silently use the local debug settings, and every page would then have failed.
- **Python version:** pinned to 3.12 in `.python-version`.
- **Smoke test:** with the production settings, every reachable page for each role loads with no errors and no missing files.

**Important: which git repo to deploy from.** `pathgen3.0app/` is a copy of the groupmate's repo (`origin` = `github.com/yannadev/pathgen3.0`, branch `main`), with about 97 changed files that are not committed. **Agree with the groupmate before pushing.** Use a new branch (for example `ours`) or a separate repo, so their `main` is not overwritten. Commit everything, including `retrieval_index/pathgen_lessons.v1.json` and `content_source/media_manifest.json`.

**Steps**

1. **Run the tests locally**: all 298 should pass. The AI-feedback index is already rebuilt; rebuild it again only if lesson text changes (`.venv\Scripts\python.exe manage.py build_retrieval_index`).
   ```
   .venv\Scripts\python.exe manage.py test
   ```
2. **Commit and push** to the branch or repo you agreed on.
3. **Create the service** from that repo/branch, and add a **new, empty PostgreSQL database**. It must be fresh: the seed refuses to change curriculum that is already published.
4. **Set these variables on the server:**

   | Variable | Value |
   |---|---|
   | `DJANGO_SETTINGS_MODULE` | `config.settings.production` |
   | `SECRET_KEY` | a long random string: `python -c "import secrets; print(secrets.token_urlsafe(50))"` |
   | `DATABASE_URL` | the PostgreSQL connection URL from the host |
   | `ALLOWED_HOSTS` | the site's domain only, e.g. `pathgen-production.up.railway.app` (no `https://`, no `*`) |
   | `CSRF_TRUSTED_ORIGINS` | the same domain with `https://`, e.g. `https://pathgen-production.up.railway.app` |
   | `GROQ_API_KEY`, `GROQ_MODEL` | same as in your local `.env` |
   | `OPENAI_API_KEY`, `EMBEDDING_MODEL` | same as in your local `.env` (`text-embedding-3-small`) |
   | `PATHGEN_BOOTSTRAP_ADMIN_PASSWORD` | a strong password for the first admin (remove it after step 6) |

5. **Deploy.** The Procfile runs migrations and builds the static files on every start. Open `https://<domain>/health/`: it should show `{"status": "ok"}`.
6. **One time only**, in the host's shell (Railway: the service's shell, or `railway run`):
   ```
   python manage.py seed_curriculum --settings=config.settings.production
   python manage.py bootstrap_admin --username <admin-name> --noinput --settings=config.settings.production
   ```
   Then delete `PATHGEN_BOOTSTRAP_ADMIN_PASSWORD` from the variables.
7. **Log in as the admin** and create the teacher and student accounts and the class(es). In Override, set Study Access on; leave Post-test Access off until the post-test day.
8. **Check on a phone:**
   - log in as a test student, finish one lesson exercise, and confirm a written tip appears (not the plain "You completed Regular session…" fallback, which means the API keys or the index are wrong);
   - open a wrong address and confirm the PathGen error page shows.

**If something goes wrong**
- **Every page gives a server error:** the static build ran without the production settings. Check that `DJANGO_SETTINGS_MODULE` is set, and look at the deploy log for `collectstatic`.
- **"Bad Request (400)":** `ALLOWED_HOSTS` doesn't match the domain exactly.
- **Login form gives 403:** `CSRF_TRUSTED_ORIGINS` is missing the `https://` domain.
- **The seed refuses to run:** the database already has an older curriculum. Use a fresh database.
- **Feedback is always the plain fallback:** missing API keys, or the committed index doesn't match the lesson text (rebuild it and commit it).
- **A lesson video shows "Video unavailable":** the video was removed from YouTube. Remove its ID from `media_manifest.json` (as done for Lesson 1) or replace it.

---

## 9. Speed pass (2026-10-08)

Students use phones, often on mobile data, so this pass cut what each page downloads and made the server handle a whole class at once. **Nothing looks different.**

**Downloads**

| What | Before | After |
|---|---|---|
| Avatars (shown at 88 px or smaller) | 1.0–2.1 MB each, 2000×2000 | 11–15 KB each, 192×192 |
| Logo / browser-tab icon | 90 KB, 3750×3750 | 4 KB, 192×192 |
| Icon library (every page) | 348 KB (all 1,768 Lucide icons) | 20 KB (the ~100 icons we use) |
| Web font request (every page) | a request to Google Fonts that **always failed** | removed |
| Page HTML | not compressed | gzip-compressed |
| Page HTML, admin "Users" (45 users) | 514 KB | 234 KB before compression |

- **Originals:** the full-size avatars and logo are kept in `original_assets/` (not deployed).
- **Icons:** the icons render exactly as before; this was checked on all 399 icons in the templates. After adding a new `data-lucide` icon, rebuild the file with `scripts/build_lucide_subset.mjs` (steps are at the top of that file). A test fails if an icon is missing.
- **Font:** the Google Fonts address was invalid (Google answered "400: Invalid selector"), so Inter never loaded. Everyone, including the adviser, has been seeing the phone's own font (Roboto on Android, San Francisco on iPhone). The link is removed, so the approved look stays exactly the same, and each page skips a failing request to Google.
- **Unused style names:** Tailwind was removed earlier, but about 3,400 of its class names were still written in the templates and did nothing. They were removed. Only names used by no CSS or JS file were removed.

**Server, for a class finishing at the same time**
- **Threads:** the server now runs 3 processes × 4 threads (12 requests at once instead of 3), in the `Procfile`. While one student waits for AI feedback, the others' pages still load.
- **Time limits on the AI calls:** embeddings 10 s (there was no limit) and Groq 20 s per try (was 30 s). The worst case now stays under the server's request limit. If a call times out, the student gets the written fallback tip, as before.
- **Database:** checked with a 40-student class. Every page uses a fixed number of queries, whatever the class size, so no change was needed.

---

## Running it locally

From `pathgen3.0app/`, using the project's `.venv` (plain `python` has no Django):

```
.venv\Scripts\python.exe manage.py runserver
.venv\Scripts\python.exe manage.py test
```

`DATABASE_URL` must point to a PostgreSQL database. Tip: if a style change doesn't show up, the browser is using an old copy. Do a hard refresh (Ctrl+Shift+R).
