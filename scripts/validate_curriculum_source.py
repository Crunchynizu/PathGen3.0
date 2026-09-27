import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

import django

django.setup()

from apps.curriculum.source import validate_curriculum_source


if __name__ == "__main__":
    summary = validate_curriculum_source()
    print(
        "Curriculum source valid: "
        f"{summary['questions_total']} questions, "
        f"{summary['figures']} prompt figures, {summary['videos']} videos."
    )
