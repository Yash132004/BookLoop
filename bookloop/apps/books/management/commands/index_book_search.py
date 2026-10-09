from django.core.management.base import BaseCommand

from apps.books.models import BookListing
from apps.books.semantic import book_search_text, embed_text


class Command(BaseCommand):
    help = 'Generate or refresh semantic search vectors for existing books.'

    def handle(self, *args, **options):
        books = BookListing.objects.all().iterator()
        indexed = 0

        for book in books:
            embedding = embed_text(book_search_text(book))
            if embedding is None:
                self.stderr.write(
                    self.style.ERROR('Could not load FastEmbed or its model; no books were indexed.')
                )
                return
            book.search_embedding = embedding
            book.save(update_fields=['search_embedding'])
            indexed += 1

        self.stdout.write(self.style.SUCCESS(f'Indexed {indexed} book listing(s).'))
