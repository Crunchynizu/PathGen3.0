# gamified_vibe (experiment, 2026-10-04)

A trial of a game *feel* on the student side, without game mechanics, to see whether it suits
Grade 7 students. There are no points, stars, badges, streaks, rewards, leaderboards or mascot:
only the look and motion of a game UI.

## What it changes

The student dashboard, My Lesson, the lesson pages, and the exercise and Activity screens
(regular, additional, foundational, activity). The pre-test and post-test are untouched, so they
still look identical to each other. Questions, choices, hints and scoring are unchanged: only the
styling around them changes.

- Dark "ink" outlines and solid offset shadows on cards
- Chunky buttons that press down; the next-step button is sunny yellow with a nudging arrow
- Sticker-style icons (tilted, outlined, wiggle on hover)
- Bouncy pop-in of page blocks, one after another
- Trail-style path lines; the current stop hops
- Candy-striped, moving progress and skill bars
- Slowly drifting math symbols (+ − × ÷) in the background
- Exercises/Activity: outlined question card, choice tiles that pop in and press down, striped progress bar, framed feedback bubble
- Everything stops moving when the device asks for reduced motion

## Files

| File | Change |
|---|---|
| `pathgen3.0app/static/css/gamified_vibe.css` | new, holds the whole experiment |
| `pathgen3.0app/templates/_base.html` | one `<link>` line after `{% block page_css %}` |

## Roll back

1. Delete the `gamified_vibe.css` `<link>` line in `templates/_base.html` (it is marked with a comment).
2. Delete `static/css/gamified_vibe.css`.
3. Delete this file.

Nothing else depends on it. The tests pass with or without it.
