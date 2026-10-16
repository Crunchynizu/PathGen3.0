from django.db import migrations, models


def fill_units(apps, schema_editor):
    """Lessons seeded before parts existed are whole units: unit = order, no part."""
    Lesson = apps.get_model("curriculum", "Lesson")
    for lesson in Lesson.objects.all():
        lesson.unit_number = lesson.lesson_order
        lesson.unit_title = lesson.title
        lesson.save(update_fields=["unit_number", "unit_title"])


class Migration(migrations.Migration):

    dependencies = [
        ("curriculum", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="lesson",
            name="part_number",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="lesson",
            name="unit_number",
            field=models.PositiveSmallIntegerField(default=1),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="lesson",
            name="unit_title",
            field=models.CharField(default="", max_length=255),
            preserve_default=False,
        ),
        migrations.RunPython(fill_units, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="lesson",
            constraint=models.CheckConstraint(
                condition=models.Q(unit_number__gt=0)
                & (models.Q(part_number__isnull=True) | models.Q(part_number__gt=0)),
                name="lesson_unit_part_positive",
            ),
        ),
        migrations.AddConstraint(
            model_name="lesson",
            constraint=models.UniqueConstraint(
                fields=["unit_number", "part_number"],
                name="unique_lesson_unit_part",
            ),
        ),
    ]
