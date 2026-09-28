from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.feedback.providers.openai_embeddings import OpenAIEmbeddingClient
from apps.feedback.retrieval.builder import build_index
from apps.feedback.retrieval.index import load_index


class Command(BaseCommand):
    help = "Build the versioned PathGen lesson retrieval index."

    def add_arguments(self, parser):
        parser.add_argument(
            "--source-dir",
            type=Path,
            default=Path(settings.BASE_DIR) / "content_source" / "lessons",
        )
        parser.add_argument(
            "--output",
            type=Path,
            default=(
                Path(settings.BASE_DIR)
                / "retrieval_index"
                / "pathgen_lessons.v1.json"
            ),
        )

    def handle(self, *args, **options):
        try:
            embedder = OpenAIEmbeddingClient()
            index = build_index(
                source_dir=options["source_dir"],
                output_path=options["output"],
                embedder=embedder,
            )
            load_index.cache_clear()
        except Exception as exc:
            raise CommandError(f"Retrieval index build failed: {exc}") from exc

        chunk_count = len(index["chunks"])
        total_tokens = index["_meta"]["total_tokens"]
        self.stdout.write(
            self.style.SUCCESS(
                f"Retrieval index built: chunks={chunk_count}, total_tokens={total_tokens}"
            )
        )
