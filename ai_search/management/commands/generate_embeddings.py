"""
Generate embeddings for all search documents.

Usage::

    python manage.py generate_embeddings          # skip current vectors
    python manage.py generate_embeddings --force   # regenerate everything
"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db.models import F, Q

from ai_search.embeddings import EmbeddingConfigError, get_provider
from ai_search.models import EmbeddingStatus, ProductSearchDocument
from ai_search.services.embedding_service import generate_embedding_for_document


class Command(BaseCommand):
    help = "Generate vector embeddings for all ProductSearchDocument objects"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Regenerate embeddings even for documents with current vectors.",
        )

    def handle(self, *args, **options):
        force = options["force"]

        # Validate configuration before processing any documents.
        try:
            get_provider()
        except EmbeddingConfigError as exc:
            raise CommandError(str(exc))

        config = getattr(settings, "AI_SEARCH", {})
        model_name = config.get("EMBEDDING_MODEL", "")

        documents = ProductSearchDocument.objects.order_by("pk")
        total = documents.count()

        if total == 0:
            self.stdout.write(
                self.style.WARNING("No search documents found.")
            )
            return

        self.stdout.write(
            self.style.NOTICE(
                f"Found {total} search documents. "
                f"{'Force-regenerating all.' if force else 'Skipping current vectors.'}"
            )
        )

        success = 0
        failed = 0
        skipped = 0

        for doc in documents.iterator():
            doc_id = doc.pk

            if not force:
                # Check the usable-vector invariant inline to decide
                # whether to skip without entering the service.
                try:
                    emb = doc.embedding
                    if (
                        emb.status == EmbeddingStatus.READY
                        and emb.embedding is not None
                        and emb.model_name == model_name
                        and emb.content_hash == doc.content_hash
                    ):
                        skipped += 1
                        continue
                except Exception:
                    pass  # No embedding row — proceed to generate.

            result = generate_embedding_for_document(doc_id, force=force)
            if result:
                success += 1
            else:
                # Check if it was a skip (already current) or a failure.
                try:
                    emb = ProductSearchDocument.objects.get(
                        pk=doc_id,
                    ).embedding
                    if emb.status == EmbeddingStatus.FAILED:
                        failed += 1
                    else:
                        skipped += 1
                except Exception:
                    failed += 1

            processed = success + failed + skipped
            if processed % 10 == 0:
                self.stdout.write(
                    f"  Processed {processed}/{total} documents..."
                )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(f"Processed: {total} products")
        )
        self.stdout.write(self.style.SUCCESS(f"  Success: {success}"))
        if failed:
            self.stdout.write(self.style.ERROR(f"  Failed:  {failed}"))
        if skipped:
            self.stdout.write(self.style.WARNING(f"  Skipped: {skipped}"))
