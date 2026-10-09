# BookLoop Product Context

## 1. Product summary

BookLoop is a local marketplace for buying and selling physical new and used books. A person has one account and can both buy and sell. Book listings include a simple text locality, so people can find books offered near them without needing map or distance infrastructure.

The MVP focuses on the core marketplace loop: discover a real listing, decide whether to buy it, place a simple order, and give a book another reader by listing it for sale.

## 2. Problem and motivation

Readers may have difficulty finding affordable books nearby, while people who have finished reading a book may have no simple way to offer it to local readers. BookLoop brings those two activities into one small marketplace.

The product is intended to:

- Make nearby book listings easy to browse and search.
- Help readers find lower-cost new and used books.
- Give sellers a straightforward way to list a book they already own.
- Keep useful physical books in circulation and connect readers locally.

These are the product goals the MVP is designed to explore; the current application does not claim to measure marketplace impact or guarantee a listing will sell.

## 3. Target users and use

BookLoop has one type of account. The same person can act as a buyer in one interaction and a seller in another.

### Buyers

Browse available books, search by title/author/topic, narrow results by condition or locality, inspect book details, provide a shipping address at checkout, and review orders in **My Orders**.

### Sellers

Sign in, create a listing with book details and an optional cover image, and manage their own listings from **My Listings**. Seller ownership is assigned by the server from the signed-in account.

### Typical journey

```text
Homepage → Browse Books → Search/filter or image search → Book details
          → Buy Now → Checkout → Order confirmation → My Orders

Sign up / Log in → Sell a Book → Create listing → My Listings
```

## 4. Technology stack

| Layer | Technology | Role in BookLoop |
|---|---|---|
| Server | Python and Django | URL routing, views, forms, authentication, permissions, ORM, model validation, admin, and server-rendered pages. |
| Page rendering | Django templates | Produces the homepage, browse results, listing details, account pages, checkout, and order history as HTML. |
| UI | Bootstrap 5 CDN, custom CSS, HTML | Responsive grid, navigation, forms, cards, alerts, and the BookLoop visual style. |
| Browser behavior | Small vanilla JavaScript module and Fetch API | Debounces live search, submits selected cover images asynchronously, manages loading text, and replaces the results fragment. |
| Database | SQLite for development | Stores users, listings, orders, and embedding vectors during MVP development. |
| Media | Django `ImageField` and local `media/` directory | Stores seller-uploaded listing covers in development. Search uploads are processed in memory rather than retained as new listing media. |
| Text/image vectors | FastEmbed and pretrained models | Creates local text and image embeddings used by semantic search, recommendations, and cover similarity. No hosted AI API key is required. |
| Image processing | Pillow | Validates and normalizes uploaded image files before image inference. |

The project uses Django’s built-in User model, not separate Buyer and Seller models. `bookloop/settings.py` uses SQLite by default and has an environment-based database engine switch for a future MySQL setup. A MySQL server and appropriate database driver are still needed to run it against MySQL.

## 5. Project structure

```text
bookloop/
├── manage.py
├── requirements.txt
├── bookloop/                 # Django project configuration
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
├── apps/
│   ├── core/                 # Homepage, signup, recommendations
│   ├── books/                # Book listings, search, image search, seller tools
│   └── orders/               # Checkout and buyer order history
├── templates/               # Shared and app-specific HTML templates
├── static/
│   ├── css/style.css
│   └── js/main.js
├── media/books/             # Uploaded listing covers in development
├── db.sqlite3               # Local development database
├── BOOKLOOP_TECHNICAL_GUIDE.md
└── RECOMMENDATION_SYSTEM.md
```

App code is imported under the `apps.*` package path. `bookloop/urls.py` includes the three app URL configurations and serves media files during development when `DEBUG` is enabled. Static and media paths are set in Django settings.

## 6. Main data model

### `BookListing`

The listing belongs to a seller through a foreign key to Django’s user model. It stores title, author, optional description, price, condition, locality, optional uploaded image, availability, and creation time. It also stores two derived fields used for matching:

- `search_embedding`: the listing’s text vector.
- `image_embedding`: the listing cover’s visual vector.

These fields are numeric data represented in a Django `JSONField`; they are not separate book records.

### `Order`

An order links a buyer (Django user) to a `BookListing` and stores the shipping address, shipping cost, total price, status, and creation time. `Order.book` uses `PROTECT`, which prevents deleting a listing that an order references.

```text
Django User ──< BookListing (seller)
Django User ──< Order (buyer) >── BookListing
```

An order is for one listing in this MVP. There is no cart or multi-item order model.

## 7. Implemented functionality

### Accounts

- Signup creates a normal Django user and signs them in.
- Login uses Django’s built-in `LoginView`.
- Logout uses Django’s built-in `LogoutView` and a CSRF-protected POST form.
- Seller tools, checkout, and order history require login.

### Browsing and search

- Browse available listings and open book detail pages.
- Filter by condition and locality.
- Search title and author using case-insensitive substring matching.
- Extend keyword matching with semantic similarity, using listing title, author, description, condition, and locality as text.
- Use debounced live search with a 400 ms delay. Fetch returns a Django-rendered result fragment, and JavaScript replaces the contents of the shared results container. Request cancellation and version checks prevent stale responses replacing newer results.
- Search by selecting a local image file. Django validates the upload, creates an image embedding, compares it with stored vectors for available listings that have indexed covers, and returns ranked matches above a configurable similarity threshold.

Semantic and image search use pretrained machine-learning models to create embeddings, then use ordinary cosine-similarity and sorting logic. They are not generative AI: they do not invent books or search the internet. Detailed implementation notes are in [BOOKLOOP_TECHNICAL_GUIDE.md](BOOKLOOP_TECHNICAL_GUIDE.md).

### Recommendations

The homepage may show up to four available listings. Signed-in users with order history get a simple content-based ranking based on existing text embeddings. Anonymous visitors and users without useful order history receive recent available listings as a fallback. The system does not use views, searches, likes, ratings, or collaborative filtering. See [RECOMMENDATION_SYSTEM.md](RECOMMENDATION_SYSTEM.md).

### Selling

- Create a listing with an optional image.
- Edit or delete only listings owned by the signed-in user.
- See the signed-in user’s own listings and whether each is available.
- Text and image embeddings are generated during listing create/edit when the model is available. Management commands can index older listings.

### Buying and orders

- A buyer can order an available listing belonging to another user.
- Checkout uses the price read from the database, a fixed ₹50 shipping charge, and a server-calculated total.
- Django creates a pending order and marks the one-copy listing unavailable in a database transaction.
- Buyers see their own order history and an order-success page.
- Order status values are Pending, Confirmed, Shipped, Delivered, and Cancelled.

### Administration

Django admin provides searchable/filterable management views for listings and orders, useful for reviewing the demo inventory and order records.

## 8. Why this implementation fits the MVP

- **One Django project and server-rendered templates:** keeps the application easier to explain, run, and debug than a separate API plus frontend application.
- **Built-in authentication:** avoids custom password/session code and keeps account handling conventional.
- **Django ORM:** keeps model relationships and queries readable and supports moving from SQLite to MySQL with configuration and driver changes rather than rewriting marketplace views.
- **SQLite:** has no separate database service to run during local development.
- **Bootstrap with a small custom stylesheet:** provides responsive building blocks while retaining a distinct BookLoop look.
- **Fetch instead of a frontend framework:** live search needs only a small asynchronous request and existing rendered book cards.
- **Stored embeddings:** listings are embedded when created/edited or through explicit indexing commands, instead of embedding the entire inventory every time a user searches.
- **A simple shipping amount and no payment gateway:** keeps checkout demonstrable without implying real payment processing or shipping-service integration.

For the small MVP inventory, vectors are compared in application code. This is straightforward but scales linearly with eligible listings. A larger catalog could justify background indexing, caching, or a vector index, but those are not required for the current application.

## 9. Product boundaries and current limitations

BookLoop intentionally does not currently implement:

- Payment processing, refunds, or payment tracking.
- Carrier/shipping APIs, AI shipping estimates, maps, or distance calculation.
- Chat or direct messaging.
- Ratings, reviews, or notifications.
- Wishlist, cart, or multi-book checkout.
- Recommendation features trained from extensive behavioral data.

Image search can only match available listings with a cover image and a generated `image_embedding`. Search quality depends on the image, model, and configured similarity threshold. Model packages and model files must be available to the Python environment that runs Django; see the technical guide for indexing and dependency commands.

## 10. Running and checking the project

From the directory containing `manage.py`, use the Python interpreter for the project’s virtual environment. For the current workspace layout in PowerShell:

```powershell
..\venv\Scripts\python.exe -m pip install -r requirements.txt
..\venv\Scripts\python.exe manage.py migrate
..\venv\Scripts\python.exe manage.py check
..\venv\Scripts\python.exe manage.py runserver
```

If older listings have not yet been indexed, use:

```powershell
..\venv\Scripts\python.exe manage.py index_book_search
..\venv\Scripts\python.exe manage.py index_book_images
```

The first use of FastEmbed models may require model files to be downloaded and cached. Run Django with the same Python environment where FastEmbed is installed.

## 11. Product direction

The MVP demonstrates a clear marketplace path while leaving room to grow. Future versions could add real payments, better shipping estimates, locality distance tools, richer book categories, order communication, and recommendations after the core marketplace is validated. Those additions should build on the existing User, BookListing, and Order foundation instead of introducing separate buyer/seller identities or duplicating inventory.
