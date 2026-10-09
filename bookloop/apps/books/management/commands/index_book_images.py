from django.core.management.base import BaseCommand

from apps.books.image_search import embed_listing_image
from apps.books.models import BookListing


class Command(BaseCommand):
    help = 'Generate missing image embeddings for existing book listings.'

    def handle(self, *args, **options):
        processed = skipped = failed = 0

        books = BookListing.objects.exclude(image='').iterator()
        for book in books:
            if book.image_embedding:
                skipped += 1
                continue

            embedding = embed_listing_image(book)
            if embedding:
                book.image_embedding = embedding
                book.save(update_fields=['image_embedding'])
                processed += 1
            else:
                failed += 1

        self.stdout.write(
            f'Image indexing complete: {processed} processed, '
            f'{skipped} skipped, {failed} failed.'
        )
