# BookLoop Technical Guide

This guide explains how the main BookLoop features are built, why the project uses these technologies, and how the parts fit together. It describes the current implementation in this repository; it is not a proposal for features that have not been built.

## 1. What BookLoop does

BookLoop is a Django marketplace for people in the same locality to list, find, and buy physical books. A person uses one normal Django account to buy and sell. Book listings and orders are stored in the same database, and the site renders its pages with Django templates, Bootstrap, CSS, and JavaScript.

The main apps are:

- `apps/core`: homepage and shared signup-related functionality.
- `apps/books`: book listings, text search, image search, and seller listing management.
- `apps/orders`: checkout, order creation, success page, and order history.

The homepage also uses a small content-based recommendation service; its existing detailed explanation is in [RECOMMENDATION_SYSTEM.md](RECOMMENDATION_SYSTEM.md).

## 2. Main application flow

```text
Visitor opens homepage
  ├─ Browse Books → available listings and search/filter tools
  │    └─ Book details → Buy Now → sign in if needed → Checkout
  │                               └─ Order saved → Success → My Orders
  └─ Sign up / Log in
       └─ Sell a Book → create listing → listing detail / My Listings
```

### Listing and order data

- `BookListing` stores its seller, title, author, description, price, condition, locality, optional cover image, availability, and creation date.
- `Order` stores its buyer, the listing being ordered, shipping address, shipping cost, total, status, and creation date.
- Both user relationships use Django’s configured user model. Each user can be a buyer and a seller.
- `Order.book` uses `PROTECT`, so a listing referenced by an order cannot be deleted accidentally.

### Buying flow

1. The buyer opens an available book and chooses **Buy Now**.
2. Django requires login and checks that the book is still available and is not being purchased by its seller.
3. Checkout shows the book and asks for a shipping address. The current MVP shipping charge is fixed at ₹50.
4. On submission, the server reads the actual book price from the database; it does not trust a price sent by the browser.
5. A database transaction creates a pending order and marks the listing unavailable. The listing is checked again inside the transaction to prevent two successful purchases of the same one-copy listing.
6. The buyer is redirected to an order success page. Order history is filtered by the signed-in user.

This is an order workflow, not a payment workflow: no payment gateway or payment status is implemented.

## 3. Ordinary keyword search and semantic search

### The searchable text

`apps/books/semantic.py` builds one text string for each listing using the fields that exist: title, author, description, condition, and location. BookLoop does not currently have a category field, so categories are not part of this search.

### Keyword search

The existing keyword behavior checks whether the query appears in the title or author, without case sensitivity. This keeps predictable searches such as `Clean Code` and author-name searches useful. Condition and locality are separate GET filters; they are applied to the available inventory before results are ranked.

### Semantic search

Keyword matching cannot find related concepts when the words differ. To help with that, BookLoop uses a pretrained text embedding model through FastEmbed:

- Model: `sentence-transformers/all-MiniLM-L6-v2`.
- Input: the user's query or the combined text of a listing.
- Output: a numeric vector (an embedding) representing the text's meaning in the model's learned vector space.
- Comparison: cosine similarity, which measures how closely two vectors point in the same direction.

For a non-empty query, the server embeds the query, compares it with each eligible listing's stored `search_embedding`, and sorts qualifying results by relevance. The current text-search threshold is `0.45`. Title matches receive an additional `0.35` ranking boost, and author matches receive `0.20`. A book can therefore match by title/author keywords or by semantic similarity. The output is always selected from real available `BookListing` database rows; the model does not generate book names or records.

### When text embeddings are created

The listing's text vector is generated when a listing is created or edited. Existing inventory can be indexed with:

```powershell
python manage.py index_book_search
```

The vector is stored in `BookListing.search_embedding`, a Django `JSONField`. This keeps repeated searches from embedding every listing again. Django loads FastEmbed and its model lazily: ordinary application startup does not initialize the model. The first model use may need to obtain model files; if FastEmbed/model initialization fails, the site logs the problem and search falls back to title/author keyword matching.

### Is this AI?

This is machine-learning-assisted search: a pretrained model converts text into vectors. It is not generative AI. It does not write answers, invent inventory, train on BookLoop user data, or call a hosted AI API. After embedding, matching and ordering are deterministic cosine-similarity and sorting logic.

## 4. Debounced live search

Live search keeps the same Django search rules and results template. JavaScript changes how the browser requests and displays results; it does not implement a second search engine.

### Request flow

```text
Typing / changing a filter
  → start or reset 400 ms timer
  → GET /books/search/?q=...&condition=...&location=...
  → Django applies availability, filters, keyword and semantic ranking
  → Django returns the existing book-card HTML fragment
  → JavaScript replaces the contents of #book-results
```

The initial browse page still renders its book cards on the server. `#book-results` is the shared container for those initial cards and later search results. `apps/books/views.py` renders `books/_results.html` for the search endpoint, so the response contains the card/empty-state fragment rather than an entire page.

### Why debounce and cancellation are used

- **Debounce (400 ms):** waits until the user pauses typing before sending a request. This avoids an unnecessary request for every keystroke.
- **Fetch API:** built into browsers and sufficient for this small asynchronous request; no AJAX library or frontend framework is needed.
- **AbortController:** cancels an older request when a newer query starts.
- **Request version number:** prevents a response that finishes late from replacing the results for a newer query.
- **`replaceChildren()`:** removes the current result set before inserting the returned fragment, avoiding old cards remaining underneath new ones.
- **Loading and status text:** communicates searching, no results, or a recoverable request error.

The query string is kept in the page URL with `history.replaceState`, so the current search is visible in the address bar. Without JavaScript, the text-search form submits as a normal GET request and Django renders the full browse page.

## 5. Image-based book search

### What it compares

Image search compares an uploaded picture with cover images attached to existing BookLoop listings. It does not search the internet, identify a book from a catalog, or create a listing. Only available listings that have an image and a stored image vector can match.

The implementation uses:

- Pillow (`PIL`) to validate, open, orient, and convert image files.
- FastEmbed with `Qdrant/clip-ViT-B-32-vision` to convert a cover image into a visual embedding.
- Cosine similarity and server-side sorting to rank the eligible database listings.
- The same Django `_results.html` fragment and `#book-results` container as text search.

This image model creates image vectors. The system compares uploaded image vectors with listing image vectors; it does not currently compare image vectors directly with text vectors.

### Upload validation and privacy behavior

The image form uses a normal file picker; it does not request camera or webcam access. Django validates that the upload is a supported JPEG, PNG, or WebP image, is at most 5 MB, and is no more than 25 megapixels. Pillow applies EXIF orientation and converts the image to RGB for processing. The search upload is embedded in memory and is not saved as a new media file. The browser submits it to Django with `POST` and the normal CSRF token.

The result threshold defaults to `0.80` and can be changed with the `BOOK_IMAGE_SEARCH_THRESHOLD` environment setting. Only matches at or above that threshold are returned, sorted by similarity. Condition and locality filters are also respected. A higher threshold means fewer, stricter results; a lower threshold may show more weak matches. The right value depends on real cover photos and should be calibrated against them.

### When cover vectors are generated

New listing images are embedded when a listing is created. Replacing/removing an image updates or clears its vector when the listing is edited. Existing images can be indexed with:

```powershell
python manage.py index_book_images
```

The vector is stored in `BookListing.image_embedding`, separately from the text vector. An old listing without an image vector is skipped until indexed; a listing without a cover image cannot participate in image search.

### Image search request flow

```text
User selects local image file
  → JavaScript sends multipart POST /books/image-search/
  → Django validates upload and builds its image embedding
  → compare against stored vectors for available, pictured listings
  → rank above-threshold matches
  → return book cards or “No books found” fragment
  → replace #book-results
```

The same AbortController/version approach prevents an old image-search response from overwriting a newer search. Starting a text search cancels an active image request, and vice versa.

## 6. Why these technologies were chosen

| Choice | Why it fits this MVP | Alternatives and trade-offs |
|---|---|---|
| Django views, ORM, and templates | Keeps routes, validation, permissions, and HTML rendering in the existing Python application. Search results use actual database listings. | A separate REST API and frontend framework would add another layer and duplicate template/UI work without a current need. |
| SQLite | Simple local development database and suitable for the present demo-sized inventory. Django ORM keeps database access portable. | MySQL is a reasonable later deployment database. PostgreSQL plus a vector extension becomes attractive if the catalog needs indexed vector search. |
| Bootstrap + custom CSS | Responsive components and forms with a small amount of project-specific styling. | React/Vue or another framework is unnecessary for a few server-rendered pages and small interactions. |
| Browser Fetch API | Built in, asynchronous, and enough to fetch the existing HTML result fragment. | jQuery/AJAX libraries can simplify older projects but are an extra dependency here. A full-page GET remains the fallback for text search. |
| FastEmbed local embeddings | Runs pretrained models in the Python application and stores vectors alongside each listing. No hosted AI endpoint or API key is used. | External embedding APIs shift inference off the server but require network access, credentials, privacy review, and usage-cost controls. A search server/vector database is more scalable but adds infrastructure. |
| SQLite JSONField vectors + cosine similarity in Python | Minimal storage and straightforward to understand for a small catalog. | It scans eligible vectors linearly, so cost grows with inventory size. Approximate-nearest-neighbor indexes (for example, a vector database or PostgreSQL vector extension) can reduce search time at scale but add setup and operations. |
| Pillow image handling | Well-established local image decoding and validation, already used by the Django image form. | A hosted image API would require transmitting user images to an external service; basic pixel hashes are lighter but generally do not handle different crops, lighting, or camera angles well. |

Model imports are lazy, so the non-search parts of BookLoop can start without loading the embedding models. `requirements.txt` explicitly lists FastEmbed. The code also imports Pillow for image validation and preprocessing; make sure Pillow is installed in development/deployment environments (Django's image fields require it too). Model files may be downloaded on first use and cached locally; no API key is required.

## 7. Recommendations on the homepage

The **Recommended for You** section reuses stored text vectors and the existing order history. A signed-in user's recent non-cancelled orders act as a basic interest signal; available listings are compared against those ordered books. Anonymous visitors and users without useful order history get a recent-available-listings fallback. This is content-based recommendation logic assisted by the same pretrained text embeddings, not collaborative filtering or a model trained on BookLoop users. See [RECOMMENDATION_SYSTEM.md](RECOMMENDATION_SYSTEM.md) for exact exclusions, thresholds, and edge cases.

## 8. Limitations and what could change later

- Semantic search and image search compare every eligible listing's stored vector in application code. This is practical for a small MVP but does not provide a vector index.
- Search quality depends on the listing description, cover photo, pretrained model, and similarity threshold. Poor, angled, cropped, or visually different images can lower match scores.
- Text matching does not include a category field because the model currently has no category field.
- Model startup/inference needs local model files and adequate compute. A fresh offline machine with no cached model cannot create embeddings; text search then still works by title/author, while image search may return no matches.
- The recommendation profile uses only recent order history and can treat a pending order as an interest signal. It is not a learned personal recommendation model.
- Checkout uses a fixed shipping amount and creates an order without payment processing. There is no cart, chat, ratings/reviews, or maps in the current flow.
- The current live-search fragment is HTML rendered by Django, not JSON. This reuses the book-card template and avoids a separate JavaScript renderer.

For a larger marketplace, practical next steps would be to measure model latency and relevance first, then consider background indexing, caching, a vector index, or a hosted inference provider only if the scale or operational needs justify them.

## 9. Code map

| Area | Main files |
|---|---|
| Book data and stored vectors | `apps/books/models.py` |
| Text representation and cosine similarity | `apps/books/semantic.py` |
| Image representation and preprocessing | `apps/books/image_search.py` |
| Search, image search, listing create/edit | `apps/books/views.py` |
| Image upload validation | `apps/books/forms.py` |
| Search URLs | `apps/books/urls.py` |
| Live search and image upload behavior | `static/js/main.js` |
| Search controls and shared result container | `templates/books/list.html` |
| Shared result cards and empty state | `templates/books/_results.html` |
| Text vector command | `apps/books/management/commands/index_book_search.py` |
| Image vector command | `apps/books/management/commands/index_book_images.py` |
| Checkout and order history | `apps/orders/views.py`, `apps/orders/models.py` |
| Homepage recommendations | `apps/core/recommendations.py`, `templates/core/landing.html` |

## 10. Useful commands

Run commands from the directory containing `manage.py`:

```powershell
python manage.py check
python manage.py test
python manage.py index_book_search
python manage.py index_book_images
```

The indexing commands prepare vectors for existing inventory. New and edited listings are indexed automatically by the listing views.
