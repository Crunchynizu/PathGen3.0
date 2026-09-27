from django.db import migrations


CREATE_APPEND_ONLY_TRIGGERS = """
CREATE OR REPLACE FUNCTION pathgen_prevent_append_only_modification()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION USING
        ERRCODE = '55000',
        MESSAGE = 'This table is append-only';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER no_update_mastery_event
BEFORE UPDATE OR DELETE ON adaptive_mastery_event
FOR EACH ROW EXECUTE FUNCTION pathgen_prevent_append_only_modification();

CREATE TRIGGER no_update_adaptive_decision
BEFORE UPDATE OR DELETE ON adaptive_decision
FOR EACH ROW EXECUTE FUNCTION pathgen_prevent_append_only_modification();

CREATE TRIGGER no_update_audit_event
BEFORE UPDATE OR DELETE ON core_audit_event
FOR EACH ROW EXECUTE FUNCTION pathgen_prevent_append_only_modification();
"""

DROP_APPEND_ONLY_TRIGGERS = """
DROP TRIGGER IF EXISTS no_update_mastery_event ON adaptive_mastery_event;
DROP TRIGGER IF EXISTS no_update_adaptive_decision ON adaptive_decision;
DROP TRIGGER IF EXISTS no_update_audit_event ON core_audit_event;
DROP FUNCTION IF EXISTS pathgen_prevent_append_only_modification();
"""


class Migration(migrations.Migration):
    dependencies = [
        ("adaptive", "0002_initial"),
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(
            sql=CREATE_APPEND_ONLY_TRIGGERS,
            reverse_sql=DROP_APPEND_ONLY_TRIGGERS,
        )
    ]
