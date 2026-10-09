"""Small content-based recommendations using existing orders and book vectors."""

from apps.books.models import BookListing
from apps.books.semantic import cosine_similarity
from apps.orders.models import Order


RECOMMENDATION_LIMIT = 4
RELEVANCE_THRESHOLD = 0.45
PROFILE_ORDER_LIMIT = 5


def get_book_recommendations(user=None, limit=RECOMMENDATION_LIMIT):
    """Recommend available books related to recent purchases, with a recent fallback."""
    books = BookListing.objects.filter(is_available=True).select_related('seller')
    purchase_vectors = []
    purchased_book_ids = []

    if user is not None and user.is_authenticated:
        purchases = Order.objects.filter(buyer=user).exclude(
            status=Order.Status.CANCELLED
        )
        purchased_book_ids = list(purchases.values_list('book_id', flat=True))
        recent_purchases = purchases.select_related('book').order_by('-created_at', '-pk')[:PROFILE_ORDER_LIMIT]
        purchase_vectors = [
            order.book.search_embedding
            for order in recent_purchases
            if order.book.search_embedding
        ]
        books = books.exclude(seller=user)
        if purchased_book_ids:
            books = books.exclude(pk__in=purchased_book_ids)

    if purchase_vectors:
        ranked = []
        for book in books:
            if not book.search_embedding:
                continue
            relevance = max(
                cosine_similarity(book.search_embedding, vector)
                for vector in purchase_vectors
            )
            if relevance >= RELEVANCE_THRESHOLD:
                ranked.append((relevance, book))

        ranked.sort(key=lambda item: (item[0], item[1].created_at, item[1].pk), reverse=True)
        if ranked:
            return [book for relevance, book in ranked[:limit]]

    # Cold-start and unrelated-history fallback comes from the live inventory.
    return list(books.order_by('-created_at', '-pk')[:limit])
