from django.core.management.base import BaseCommand, CommandError

from apps.curriculum.source import CurriculumSourceError, validate_curriculum_source


class Command(BaseCommand):
    help = "Validate the Phase 5 curriculum JSON, assets, and source PDF hashes."

    def handle(self, *args, **options):
        try:
            summary = validate_curriculum_source()
        except CurriculumSourceError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS("Curriculum source is valid."))
        self.stdout.write(
            "Questions: {questions_total} total; {prepost} pre/post; {regular} regular; "
            "{additional} additional; {foundational} foundational; {activity} activity.".format(**summary)
        )
        self.stdout.write(f"Prompt figures: {summary['figures']}; videos: {summary['videos']}.")
        self.stdout.write(f"Pre/post PDF SHA-256: {summary['pretest_posttest_sha256']}")
