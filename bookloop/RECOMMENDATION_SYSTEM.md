# BookLoop Recommendation System

## What it does

The homepage can show a small **Recommended for You** section containing books from the current BookLoop inventory. It returns up to four listings. Recommendations only use available listings, so a sold or otherwise unavailable book is not suggested.

## Is this AI or normal logic?

It is a simple content-based recommendation system that combines a machine-learning model with ordinary application logic:

- FastEmbed uses the pretrained `sentence-transformers/all-MiniLM-L6-v2` text model to represent a listing's text as a numeric embedding.
- BookLoop uses deterministic cosine-similarity comparisons and sorting rules to choose recommendations.

So it uses machine learning for text representation, but it is **not** a generative AI feature and it is **not** a recommendation model trained on BookLoop users. There is no chatbot, external AI API, or user-specific model training.

## Data used

### Book listing content

The existing `BookListing.search_embedding` field stores a precomputed text vector. It is generated from the listing's:

- title
- author
- description
- condition
- location

The project does not currently have a book category field. Image embeddings are separate and are not used for recommendations.

### User history

The only recommendation history currently available is the user's `Order` records. BookLoop does not store book views, searches, cart activity, wishlists, or declared interests.

The current implementation treats every non-`Cancelled` order as a purchase signal, including orders that are still `Pending`. It does not yet distinguish completed purchases from orders in progress.

For a signed-in user, the service uses up to five of their most recent orders whose status is not `Cancelled`. Those ordered books provide the content profile. A recommendation must be available, must not be one of those already ordered books, and must not be the user's own listing.

## How recommendations are selected

1. Load up to five recent non-cancelled orders for the signed-in user and use their books' existing text vectors.
2. Find available listings, excluding the user's own books and books already ordered by that user.
3. Compare each candidate's vector with the vectors from the order history using cosine similarity.
4. A candidate is considered relevant when its best similarity score is at least **0.45**.
5. Sort relevant books from highest similarity to lowest and return up to four.
6. If the user has no usable order vectors or no candidates pass the relevance cutoff, use the newest available listings as a fallback.

This calculation does not generate embeddings during the homepage request. It reuses vectors already stored on listings and performs simple vector comparisons. Anonymous users and signed-in users without useful purchase history receive the same recent-listings fallback. For signed-in users, their own books and non-cancelled purchases are excluded from that fallback too.

## When vectors are generated

New listings and listing edits use the existing text-search indexing logic to create `search_embedding`. Existing listings can be indexed with:

```powershell
python manage.py index_book_search
```

The recommendation service reads those vectors; it does not maintain a second copy or a recommendation-specific embedding field.

## Relevant implementation files

- `apps/core/recommendations.py` — recommendation scoring and recent-listing fallback.
- `apps/core/views.py` — supplies recommendations to the landing page.
- `templates/core/landing.html` — displays the section using the existing book-card partial.
- `apps/books/models.py` — defines listing content and `search_embedding`.
- `apps/orders/models.py` — provides purchase history.
- `apps/books/semantic.py` — creates text embeddings and calculates cosine similarity.

## Cold start and edge cases

- **Anonymous visitor:** sees the most recently added available listings.
- **New signed-in user:** sees recent available listings, excluding their own.
- **No usable purchase vectors:** uses the recent-listing fallback.
- **Unrelated purchase history:** if no candidate reaches the similarity cutoff, uses the recent-listing fallback.
- **No available inventory:** returns no recommendations, so the homepage hides the section.
- **Small inventory:** returns fewer than four if fewer eligible books exist.
- **Deleted or unavailable book:** is absent from the next recommendation calculation because the service queries current listings each time.
- **Cancelled order:** does not count as purchase history and does not exclude that book from recommendations if it is available again.

## What it does not do

- It does not record browsing or search behavior.
- It does not use categories, ratings, reviews, likes, or collaborative filtering.
- It does not use book-cover image vectors.
- It does not guarantee recommendations based on a user's full reading history; only up to five recent non-cancelled orders are considered.
- It does not cache recommendation results. It recomputes scores for a signed-in user on each homepage request, using already-computed vectors and no model inference. This is suitable for the current small MVP inventory, but a much larger catalog may need result caching or a vector index.

## Tests

The recommendation tests cover anonymous and new users, relevant and unrelated purchase history, previous purchases, no inventory, small and larger inventories, listing deletion and availability changes, homepage rendering, signup, book details, checkout, and order history.

Run the checks from the Django project directory:

```powershell
python manage.py check
python manage.py test
```
