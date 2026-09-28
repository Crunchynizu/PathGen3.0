from django.db.models import OuterRef, Subquery

from apps.adaptive.models import Decision, DecisionTargetSkill, SkillMastery


def decisions_for_students(students, *, date_from=None, date_to=None):
    decisions = Decision.objects.filter(session__student__in=students)
    if date_from:
        decisions = decisions.filter(created_at__date__gte=date_from)
    if date_to:
        decisions = decisions.filter(created_at__date__lte=date_to)
    return decisions.select_related("session", "session__student", "session__lesson")


def follow_up_targets_for_students(students, *, date_from=None, date_to=None):
    mastery = SkillMastery.objects.filter(
        student_id=OuterRef("decision__session__student_id"),
        skill_id=OuterRef("skill_id"),
        evidence_count__gt=0,
    ).values("p_known")[:1]
    targets = DecisionTargetSkill.objects.filter(
        decision__session__student__in=students,
        target_kind=DecisionTargetSkill.TargetKind.FOLLOW_UP,
    )
    if date_from:
        targets = targets.filter(decision__created_at__date__gte=date_from)
    if date_to:
        targets = targets.filter(decision__created_at__date__lte=date_to)
    return (
        targets.select_related(
            "decision",
            "decision__session",
            "decision__session__student",
            "decision__session__lesson",
            "skill",
        )
        .annotate(current_p_known=Subquery(mastery))
        .order_by("-decision__created_at")
    )
