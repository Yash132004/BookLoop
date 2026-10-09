from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import BookListing


class BookSearchTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.seller = user_model.objects.create_user(username='seller', password='test-pass')
        self.python_book = self.create_book(
            'Python Crash Course', 'Eric Matthes', 'A hands-on guide to programming in Python.',
            'Good', 'Vadodara', [1.0, 0.0],
        )
        self.ml_book = self.create_book(
            'Hands-On Machine Learning', 'Aurelien Geron',
            'Learn machine learning and artificial intelligence.',
            'Like New', 'Vaghodia', [0.9, 0.1],
        )
        self.other_book = self.create_book(
            'The Alchemist', 'Paulo Coelho', 'A novel about a personal journey.',
            'Fair', 'Vadodara', [-1.0, 0.0],
        )
        self.unavailable_book = self.create_book(
            'Unavailable Python Guide', 'Another Author', '', 'New', 'Vadodara', [1.0, 0.0],
            is_available=False,
        )

    def create_book(self, title, author, description, condition, location, embedding, **extra):
        return BookListing.objects.create(
            seller=self.seller,
            title=title,
            author=author,
            description=description,
            price=Decimal('120.00'),
            condition=condition,
            location=location,
            search_embedding=embedding,
            **extra,
        )

    def titles(self, query=''):
        response = self.client.get(reverse('books:listing_list'), {'q': query})
        self.assertEqual(response.status_code, 200)
        return [book.title for book in response.context['books']]

    @patch('apps.books.views.embed_text', return_value=[1.0, 0.0])
    def test_exact_title_search(self, _embed):
        self.assertEqual(self.titles('Python Crash Course')[0], 'Python Crash Course')

    @patch('apps.books.views.embed_text', return_value=[0.0, 1.0])
    def test_partial_title_search_keeps_keyword_behavior(self, _embed):
        self.assertEqual(self.titles('Crash'), ['Python Crash Course'])

    @patch('apps.books.views.embed_text', return_value=[0.0, 1.0])
    def test_author_search(self, _embed):
        self.assertEqual(self.titles('Matthes'), ['Python Crash Course'])

    @patch('apps.books.views.embed_text', return_value=[1.0, 0.0])
    def test_natural_language_semantic_search(self, _embed):
        self.assertIn('Python Crash Course', self.titles('books for learning programming'))

    def test_empty_query_shows_available_inventory_without_embedding(self):
        with patch('apps.books.views.embed_text') as embed:
            titles = self.titles()
        embed.assert_not_called()
        self.assertEqual(set(titles), {
            'Python Crash Course', 'Hands-On Machine Learning', 'The Alchemist',
        })

    @patch('apps.books.views.embed_text', return_value=[0.0, 1.0])
    def test_no_match_returns_empty_results(self, _embed):
        self.assertEqual(self.titles('astronomy textbooks'), [])

    @patch('apps.books.views.embed_text', return_value=[1.0, 0.0])
    def test_search_and_existing_filters_work_together(self, _embed):
        response = self.client.get(reverse('books:listing_list'), {
            'q': 'programming', 'condition': 'Good', 'location': 'vadodara',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual([book.pk for book in response.context['books']], [self.python_book.pk])

    def test_existing_filters_work_without_search(self):
        response = self.client.get(reverse('books:listing_list'), {
            'condition': 'Like New', 'location': 'vag',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual([book.pk for book in response.context['books']], [self.ml_book.pk])

    def test_book_detail_still_renders(self):
        response = self.client.get(reverse('books:detail', args=[self.python_book.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Python Crash Course')

    @patch('apps.books.views.embed_text', return_value=[1.0, 0.0])
    def test_live_search_endpoint_returns_only_the_results_fragment(self, _embed):
        response = self.client.get(reverse('books:search'), {'q': 'Python Crash Course'})
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'books/_results.html')
        self.assertContains(response, 'Python Crash Course')
        self.assertNotContains(response, '<!doctype html>')
        self.assertNotContains(response, 'Browse Books')

    def test_live_search_endpoint_accepts_only_get(self):
        response = self.client.post(reverse('books:search'))
        self.assertEqual(response.status_code, 405)

    @patch('apps.books.views.embed_text', return_value=[1.0, 0.0])
    def test_full_browse_page_remains_available_as_get_fallback(self, _embed):
        response = self.client.get(reverse('books:listing_list'), {'q': 'Python Crash Course'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="book-search-form"')
        self.assertContains(response, 'id="book-results"')
        self.assertContains(response, 'Python Crash Course')

    @patch('apps.books.views.embed_text', return_value=[1.0, 0.0])
    def test_existing_seller_create_edit_delete_flow_still_works(self, _embed):
        self.client.force_login(self.seller)
        create_response = self.client.post(reverse('books:create'), {
            'title': 'New Listing', 'author': 'Test Author', 'description': 'A test book',
            'price': '100.00', 'condition': 'Good', 'location': 'Vadodara',
        })
        created = BookListing.objects.get(title='New Listing')
        self.assertEqual(created.seller, self.seller)
        self.assertRedirects(create_response, reverse('books:detail', args=[created.pk]))
        self.assertEqual(created.search_embedding, [1.0, 0.0])

        edit_response = self.client.post(reverse('books:edit', args=[created.pk]), {
            'title': 'Edited Listing', 'author': 'Test Author', 'description': 'Updated',
            'price': '110.00', 'condition': 'Like New', 'location': 'Vaghodia',
        })
        created.refresh_from_db()
        self.assertRedirects(edit_response, reverse('books:detail', args=[created.pk]))
        self.assertEqual(created.title, 'Edited Listing')
        self.assertEqual(created.search_embedding, [1.0, 0.0])

        delete_response = self.client.post(reverse('books:delete', args=[created.pk]))
        self.assertRedirects(delete_response, reverse('books:my_listings'))
        self.assertFalse(BookListing.objects.filter(pk=created.pk).exists())
