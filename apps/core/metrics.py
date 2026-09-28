from __future__ import annotations

from collections import defaultdict
from datetime import date
from statistics import mean, median

from django.db.models import Count, Q

from apps.accounts.models import User
from apps.adaptive.bkt import mastery_band
from apps.adaptive.models import Decision, DecisionTargetSkill, SkillMastery
from apps.feedback.models import SessionFeedback
from apps.learning.models import Session, StudentPath


METRICS_VERSION = "METRICS-V1"


def _window_label(date_from=None, date_to=None):
    if not date_from and not date_to:
        return "all-time"
    return f"{date_from or 'beginning'} to {date_to or 'present'}"


def _result(*, value, cohort, n, definition, date_from=None, date_to=None, **extra):
    result = {
        "value": value,
        "cohort": cohort,
        "n": n,
        "definition": definition,
        "window": _window_label(date_from, date_to),
        "version": METRICS_VERSION,
        "insufficient": n == 0,
    }
    result.update(extra)
    return result


def _students(students=None):
    if students is None:
        return User.objects.filter(role=User.Role.STUDENT)
    return students.filter(role=User.Role.STUDENT)


def _date_filter(queryset, field, date_from=None, date_to=None):
    if date_from:
        queryset = queryset.filter(**{f"{field}__date__gte": date_from})
    if date_to:
        queryset = queryset.filter(**{f"{field}__date__lte": date_to})
    return queryset


def active_students(students=None, *, cohort="All students", date_from=None, date_to=None):
    scoped = _students(students)
    cohort_size = scoped.count()
    value = scoped.filter(is_active=True).count() if cohort_size else None
    return _result(
        value=value,
        cohort=cohort,
        n=cohort_size,
        definition="Active student accounts in the selected cohort.",
        date_from=date_from,
        date_to=date_to,
    )


def completed_paths(students=None, *, cohort="All students", date_from=None, date_to=None):
    scoped = _students(students)
    cohort_size = scoped.count()
    value = (
        StudentPath.objects.filter(
            student__in=scoped,
            status=StudentPath.Status.COMPLETED,
        ).count()
        if cohort_size
        else None
    )
    return _result(
        value=value,
        cohort=cohort,
        n=cohort_size,
        definition="Students whose learning path is complete.",
        date_from=date_from,
        date_to=date_to,
    )


def _matched_scores(students, date_from=None, date_to=None):
    sessions = Session.objects.filter(
        student__in=_students(students),
        session_type__in=[Session.SessionType.PRETEST, Session.SessionType.POSTTEST],
        status=Session.Status.COMPLETED,
        voided_at__isnull=True,
        completed_at__isnull=False,
    ).annotate(
        total_count=Count("items", distinct=True),
        correct_count=Count(
            "items",
            filter=Q(items__response__selected_choice__is_correct=True),
            distinct=True,
        ),
    )
    sessions = _date_filter(sessions, "completed_at", date_from, date_to)
    sessions = sessions.order_by("student_id", "session_type", "-completed_at", "-created_at")

    latest = {}
    for session in sessions:
        key = (session.student_id, session.session_type)
        if key not in latest and session.total_count:
            latest[key] = (session.correct_count / session.total_count) * 100

    pairs = []
    student_ids = {student_id for student_id, _session_type in latest}
    for student_id in student_ids:
        pre = latest.get((student_id, Session.SessionType.PRETEST))
        post = latest.get((student_id, Session.SessionType.POSTTEST))
        if pre is not None and post is not None:
            pairs.append({"student_id": student_id, "pretest": pre, "posttest": post})
    return pairs


def matched_prepost_sample(students=None, *, cohort="All students", date_from=None, date_to=None):
    pairs = _matched_scores(students, date_from, date_to)
    count = len(pairs)
    return _result(
        value=count if count else None,
        cohort=cohort,
        n=count,
        definition="Distinct students with both a completed pre-test and post-test in the window.",
        date_from=date_from,
        date_to=date_to,
    )


def matched_gain(students=None, *, cohort="All students", date_from=None, date_to=None):
    pairs = _matched_scores(students, date_from, date_to)
    count = len(pairs)
    if count:
        pretest_mean = mean(pair["pretest"] for pair in pairs)
        posttest_mean = mean(pair["posttest"] for pair in pairs)
        value = mean(pair["posttest"] - pair["pretest"] for pair in pairs)
        series = {
            "Pre-test average": round(pretest_mean, 1),
            "Post-test average": round(posttest_mean, 1),
            "Average matched gain": round(value, 1),
        }
    else:
        value = None
        series = {}
    return _result(
        value=round(value, 1) if value is not None else None,
        cohort=cohort,
        n=count,
        definition="Average post-test score minus pre-test score for matched students only, in percentage points.",
        date_from=date_from,
        date_to=date_to,
        series=series,
    )


def bkt_mastery_bands(students=None, *, cohort="All students", date_from=None, date_to=None):
    masteries = SkillMastery.objects.filter(
        student__in=_students(students),
        evidence_count__gt=0,
    ).select_related("skill")
    masteries = _date_filter(masteries, "updated_at", date_from, date_to)
    counts = defaultdict(lambda: {"np": 0, "dev": 0, "strong": 0})
    names = {}
    sample_size = 0
    for mastery in masteries:
        counts[mastery.skill.code][mastery_band(mastery.p_known)] += 1
        names[mastery.skill.code] = mastery.skill.name
        sample_size += 1
    value = {
        code: {"name": names[code], **bands}
        for code, bands in sorted(counts.items())
    } if sample_size else None
    return _result(
        value=value,
        cohort=cohort,
        n=sample_size,
        definition="Evidence-bearing skill records grouped into not proficient, developing, and strong BKT bands.",
        date_from=date_from,
        date_to=date_to,
    )


def q_learning_decisions(students=None, *, cohort="All students", date_from=None, date_to=None):
    decisions = Decision.objects.filter(session__student__in=_students(students))
    decisions = _date_filter(decisions, "created_at", date_from, date_to)
    rows = decisions.values("session__lesson__code", "action").annotate(count=Count("id"))
    value = defaultdict(lambda: {
        Decision.Action.PROGRESS: 0,
        Decision.Action.ADDITIONAL_EXERCISE: 0,
        Decision.Action.FOUNDATIONAL_EXERCISE: 0,
    })
    sample_size = 0
    for row in rows:
        lesson_code = row["session__lesson__code"] or "Whole course"
        value[lesson_code][row["action"]] = row["count"]
        sample_size += row["count"]
    return _result(
        value=dict(sorted(value.items())) if sample_size else None,
        cohort=cohort,
        n=sample_size,
        definition="Persisted adaptive decisions grouped by lesson and selected action.",
        date_from=date_from,
        date_to=date_to,
    )


def follow_up_needed(students=None, *, cohort="All students", date_from=None, date_to=None):
    cohort_size = _students(students).count()
    if not cohort_size:
        return _result(
            value=None,
            cohort=cohort,
            n=0,
            definition="Students with at least one persisted follow-up target in the selected scope.",
            date_from=date_from,
            date_to=date_to,
        )
    targets = DecisionTargetSkill.objects.filter(
        decision__session__student__in=_students(students),
        target_kind=DecisionTargetSkill.TargetKind.FOLLOW_UP,
    )
    targets = _date_filter(targets, "decision__created_at", date_from, date_to)
    count = targets.values("decision__session__student_id").distinct().count()
    return _result(
        value=count if count else 0,
        cohort=cohort,
        n=cohort_size,
        definition="Students with at least one persisted follow-up target in the selected scope.",
        date_from=date_from,
        date_to=date_to,
    )


def median_elapsed_duration(students=None, *, cohort="All students", date_from=None, date_to=None):
    sessions = Session.objects.filter(
        student__in=_students(students),
        status=Session.Status.COMPLETED,
        voided_at__isnull=True,
        started_at__isnull=False,
        completed_at__isnull=False,
    )
    sessions = _date_filter(sessions, "completed_at", date_from, date_to)
    durations = defaultdict(list)
    for session in sessions.only("session_type", "started_at", "completed_at"):
        seconds = max(0, (session.completed_at - session.started_at).total_seconds())
        durations[session.get_session_type_display()].append(seconds)
    sample_size = sum(len(values) for values in durations.values())
    value = {
        stage: round(median(values) / 60, 1)
        for stage, values in sorted(durations.items())
    } if sample_size else None
    return _result(
        value=value,
        cohort=cohort,
        n=sample_size,
        definition="Median elapsed session time from started_at to completed_at, grouped by stage, in minutes.",
        date_from=date_from,
        date_to=date_to,
    )


def rag_reliability(students=None, *, cohort="All students", date_from=None, date_to=None):
    feedback = SessionFeedback.objects.filter(session__student__in=_students(students))
    feedback = _date_filter(feedback, "created_at", date_from, date_to)
    rows = feedback.values("generation_status").annotate(count=Count("id"))
    value = {"generated": 0, "fallback": 0}
    sample_size = 0
    for row in rows:
        value[row["generation_status"]] = row["count"]
        sample_size += row["count"]
    return _result(
        value=value if sample_size else None,
        cohort=cohort,
        n=sample_size,
        definition="Saved feedback outcomes grouped by generated and deterministic fallback status.",
        date_from=date_from,
        date_to=date_to,
    )
