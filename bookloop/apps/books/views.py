import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models.deletion import ProtectedError
from django.conf import settings
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET
from django.views.decorators.http import require_POST

from .forms import BookImageSearchForm, BookListingForm
from .image_search import embed_listing_image, embed_uploaded_image
from .models import BookListing
from .semantic import book_search_text, embed_text, cosine_similarity

logger = logging.getLogger(__name__)
SEMANTIC_MATCH_THRESHOLD = 0.45


def _listing_context(request):
    books = BookListing.objects.filter(is_available=True).select_related('seller')

    search_query = request.GET.get('q', '').strip()
    selected_condition = request.GET.get('condition', '').strip()
    selected_location = request.GET.get('location', '').strip()

    valid_conditions = [value for value, label in BookListing.Condition.choices]
    if selected_condition and selected_condition.lower() in {
        value.lower() for value in valid_conditions
    }:
        books = books.filter(condition__iexact=selected_condition)
    else:
        selected_condition = ''

    if selected_location:
        books = books.filter(location__icontains=selected_location)

    books = list(books)

    if search_query:
        query_embedding = embed_text(search_query)
        ranked_books = []

        for book in books:
            title_match = search_query.casefold() in book.title.casefold()
            author_match = search_query.casefold() in book.author.casefold()
            keyword_match = title_match or author_match
            similarity = cosine_similarity(query_embedding, book.search_embedding)

            # Keep existing title/author search, while allowing semantic matches
            # from the listing's title, author, description, condition, or location.
            if keyword_match or similarity >= SEMANTIC_MATCH_THRESHOLD:
                relevance = similarity
                if title_match:
                    relevance += 0.35
                elif author_match:
                    relevance += 0.20
                ranked_books.append((relevance, book))

        books = [book for relevance, book in sorted(
            ranked_books, key=lambda result: result[0], reverse=True
        )]

    return {
        'books': books,
        'search_query': search_query,
        'selected_condition': selected_condition,
        'selected_location': selected_location,
        'conditions': BookListing.Condition.choices,
    }


def listing_list(request):
    return render(request, 'books/list.html', _listing_context(request))


@require_GET
def listing_search(request):
    """Return only the book cards/empty state for debounced live search."""
    return render(request, 'books/_results.html', _listing_context(request))


@require_POST
def listing_image_search(request):
    """Return matching available listings as the existing results fragment."""
    form = BookImageSearchForm(request.POST, request.FILES)
    matches = []

    if form.is_valid():
        query_embedding = None
        try:
            query_embedding = embed_uploaded_image(form.cleaned_data['image'])
        except Exception:
            # A bad/corrupt upload or unavailable local model is a no-match,
            # not a server traceback or filesystem detail shown to the user.
            logger.exception('Image search embedding failed.')

        if query_embedding:
            books = BookListing.objects.filter(
                is_available=True,
            ).exclude(image='').select_related('seller')

            condition = request.POST.get('condition', '').strip()
            valid_conditions = [value for value, label in BookListing.Condition.choices]
            if condition.lower() in {value.lower() for value in valid_conditions}:
                books = books.filter(condition__iexact=condition)

            location = request.POST.get('location', '').strip()
            if location:
                books = books.filter(location__icontains=location)

            threshold = getattr(settings, 'BOOK_IMAGE_SEARCH_THRESHOLD', 0.80)
            ranked_books = []
            for book in books:
                if not book.image_embedding:
                    continue
                similarity = cosine_similarity(query_embedding, book.image_embedding)
                if similarity >= threshold:
                    ranked_books.append((similarity, book))

            matches = [book for similarity, book in sorted(
                ranked_books, key=lambda result: result[0], reverse=True
            )]

    return render(request, 'books/_results.html', {'books': matches})


def listing_detail(request, pk):
    book = get_object_or_404(BookListing.objects.select_related('seller'), pk=pk)
    return render(request, 'books/detail.html', {'book': book})


@login_required
def listing_create(request):
    if request.method == 'POST':
        form = BookListingForm(request.POST, request.FILES)
        if form.is_valid():
            book = form.save(commit=False)
            book.seller = request.user
            book.save()
            book.image_embedding = embed_listing_image(book)
            book.save(update_fields=['image_embedding'])
            book.search_embedding = embed_text(book_search_text(book)) or []
            book.save(update_fields=['search_embedding'])
            messages.success(request, 'Your book listing has been created.')
            return redirect('books:detail', pk=book.pk)
    else:
        form = BookListingForm()

    return render(request, 'books/create.html', {'form': form})


@login_required
def listing_edit(request, pk):
    book = get_object_or_404(BookListing, pk=pk, seller=request.user)

    if request.method == 'POST':
        previous_image_name = book.image.name if book.image else ''
        form = BookListingForm(request.POST, request.FILES, instance=book)
        if form.is_valid():
            image_removed = form.cleaned_data.get('image') is False
            book = form.save(commit=False)
            if image_removed:
                book.image = ''
            book.save()
            current_image_name = book.image.name if book.image else ''
            if current_image_name != previous_image_name:
                book.image_embedding = embed_listing_image(book) if current_image_name else []
                book.save(update_fields=['image_embedding'])
                if previous_image_name:
                    book.image.storage.delete(previous_image_name)
            book.search_embedding = embed_text(book_search_text(book)) or []
            book.save(update_fields=['search_embedding'])
            messages.success(request, 'Your book listing has been updated.')
            return redirect('books:detail', pk=book.pk)
    else:
        form = BookListingForm(instance=book)

    return render(request, 'books/edit.html', {'form': form, 'book': book})


@login_required
def listing_delete(request, pk):
    book = get_object_or_404(BookListing, pk=pk, seller=request.user)

    if request.method == 'POST':
        book_title = book.title
        image_name = book.image.name if book.image else ''
        image_storage = book.image.storage if image_name else None
        try:
            book.delete()
        except ProtectedError:
            messages.error(request, 'This book cannot be deleted because it is linked to an order.')
            return redirect('books:detail', pk=book.pk)
        if image_name:
            image_storage.delete(image_name)
        messages.success(request, f'“{book_title}” was deleted.')
        return redirect('books:my_listings')

    return render(request, 'books/confirm_delete.html', {'book': book})


@login_required
def my_listings(request):
    books = BookListing.objects.filter(seller=request.user).order_by('-created_at')
    return render(request, 'books/my_listings.html', {'books': books})
