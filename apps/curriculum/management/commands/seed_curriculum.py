from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.curriculum.models import (
    Lesson,
    LessonSkill,
    Question,
    QuestionChoice,
    QuestionSet,
    QuestionSetItem,
    Skill,
    Video,
)
from apps.curriculum.source import (
    CurriculumSourceError,
    iter_question_sets,
    load_curriculum_source,
    validate_curriculum_source,
)


def immutable_upsert(model, lookup, defaults, *, published_parent=None):
    instance, created = model.objects.get_or_create(**lookup, defaults=defaults)
    if created:
        return instance, True
    changed = [field for field, value in defaults.items() if getattr(instance, field) != value]
    is_published = getattr(instance, "is_published", False) or bool(published_parent)
    if changed and is_published:
        identity = ", ".join(f"{key}={value}" for key, value in lookup.items())
        raise CommandError(f"Published curriculum is immutable: {model.__name__}({identity}) differs in {changed}")
    if changed:
        for field in changed:
            setattr(instance, field, defaults[field])
        instance.save(update_fields=changed)
    return instance, False


class Command(BaseCommand):
    help = "Transactionally and idempotently seed the validated Phase 5 curriculum."

    def handle(self, *args, **options):
        try:
            validate_curriculum_source()
            source = load_curriculum_source()
        except CurriculumSourceError as exc:
            raise CommandError(str(exc)) from exc

        created = {
            "skills": 0,
            "lessons": 0,
            "videos": 0,
            "questions": 0,
            "choices": 0,
            "sets": 0,
            "items": 0,
        }

        with transaction.atomic():
            skills = {}
            for record in source["manifest"]["skills"]:
                skill, was_created = immutable_upsert(
                    Skill,
                    {"code": record["code"]},
                    {
                        "name": record["name"],
                        "description": record["description"],
                        "p_l0": Decimal(record["p_l0"]),
                        "p_t": Decimal(record["p_t"]),
                        "p_g": Decimal(record["p_g"]),
                        "p_s": Decimal(record["p_s"]),
                    },
                )
                skills[skill.code] = skill
                created["skills"] += was_created

            lessons = {}
            for document in source["lessons"]:
                record = document["lesson"]
                lesson, was_created = immutable_upsert(
                    Lesson,
                    {"code": record["code"]},
                    {
                        "slug": record["slug"],
                        "lesson_order": record["lesson_order"],
                        "unit_number": record["unit_number"],
                        "part_number": record["part_number"],
                        "unit_title": record["unit_title"],
                        "title": record["title"],
                        "summary": record["summary"],
                        "content_json": record["content"],
                        "content_schema_version": record["content_schema_version"],
                        "is_published": True,
                    },
                )
                lessons[lesson.code] = lesson
                created["lessons"] += was_created
                for display_order, skill_code in enumerate(record["skill_codes"], start=1):
                    immutable_upsert(
                        LessonSkill,
                        {"lesson": lesson, "skill": skills[skill_code]},
                        {"display_order": display_order},
                        published_parent=lesson.is_published,
                    )

            videos = {}
            for record in source["media"]["videos"]:
                transcript = (source["root"] / record["transcript_file"]).read_text(encoding="utf-8")
                video, was_created = immutable_upsert(
                    Video,
                    {"code": record["code"]},
                    {
                        "title": record["title"],
                        "youtube_video_id": record["youtube_video_id"] or record["code"],
                        "duration_seconds": record["duration_seconds"],
                        "transcript": transcript,
                    },
                )
                videos[video.code] = video
                created["videos"] += was_created

            questions = {}
            for question_set in iter_question_sets(source):
                for record in question_set["questions"]:
                    video = videos.get(record.get("video_code"))
                    question, was_created = immutable_upsert(
                        Question,
                        {"code": record["code"]},
                        {
                            "skill": skills[record["skill_code"]],
                            "prompt": record["prompt"],
                            "difficulty": record["difficulty"],
                            "presentation_type": record["presentation_type"],
                            "cognitive_level": record["cognitive_level"],
                            "solution_steps_json": record.get("solution_steps", []),
                            "explanation": record.get("explanation", ""),
                            "hint": record.get("hint"),
                            "feedback_correct": record.get("explanation", ""),
                            "feedback_incorrect": record.get("hint") or record.get("explanation", ""),
                            "image_asset": record.get("image_asset"),
                            "image_alt": record.get("image_alt"),
                            "visual_component": None,
                            "visual_config_json": None,
                            "video": video,
                            "video_pause_seconds": record.get("video_pause_seconds"),
                            "is_published": True,
                        },
                    )
                    questions[question.code] = question
                    created["questions"] += was_created
                    for display_order, choice_record in enumerate(record["choices"], start=1):
                        _, choice_created = immutable_upsert(
                            QuestionChoice,
                            {"question": question, "label": choice_record["label"]},
                            {
                                "text": choice_record["text"],
                                "is_correct": choice_record["is_correct"],
                                "misconception_code": None,
                                "display_order": display_order,
                            },
                            published_parent=question.is_published,
                        )
                        created["choices"] += choice_created

            for set_record in iter_question_sets(source):
                question_set, was_created = immutable_upsert(
                    QuestionSet,
                    {"code": set_record["code"]},
                    {
                        "name": set_record["name"],
                        "set_type": set_record["set_type"],
                        "lesson": lessons.get(set_record.get("lesson_code")),
                        "skill": skills.get(set_record.get("skill_code")),
                        "is_published": True,
                    },
                )
                created["sets"] += was_created
                for display_order, question_record in enumerate(set_record["questions"], start=1):
                    _, item_created = immutable_upsert(
                        QuestionSetItem,
                        {"question_set": question_set, "question": questions[question_record["code"]]},
                        {"display_order": display_order},
                        published_parent=question_set.is_published,
                    )
                    created["items"] += item_created

        self.stdout.write(self.style.SUCCESS("Curriculum seed complete."))
        self.stdout.write(
            "Created: " + ", ".join(f"{name}={count}" for name, count in created.items())
        )
        self.stdout.write(
            f"Database totals: skills={Skill.objects.count()}, lessons={Lesson.objects.count()}, "
            f"videos={Video.objects.count()}, questions={Question.objects.count()}, "
            f"choices={QuestionChoice.objects.count()}, sets={QuestionSet.objects.count()}, "
            f"items={QuestionSetItem.objects.count()}."
        )
