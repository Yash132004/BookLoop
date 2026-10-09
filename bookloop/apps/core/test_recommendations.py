from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.books.models import BookListing
from apps.orders.models import Order

from .recommendations import get_book_recommendations


class BookRecommendationTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.seller = user_model.objects.create_user(username='recommendation-seller')
        self.buyer = user_model.objects.create_user(username='recommendation-buyer')

    def make_book(self, title, vector=None, *, seller=None, available=True):
        return BookListing.objects.create(
            seller=seller or self.seller,
            title=title,
            author='Test Author',
            description='A test listing',
            price=Decimal('100.00'),
            condition=BookListing.Condition.GOOD,
            location='Vadodara',
            search_embedding=vector or [],
            is_available=available,
        )

    def make_order(self, book, *, status=Order.Status.DELIVERED):
        return Order.objects.create(
            buyer=self.buyer,
            book=book,
            shipping_address='Vadodara',
            shipping_cost=Decimal('50.00'),
            total_price=Decimal('150.00'),
            status=status,
        )

    def test_anonymous_user_gets_recent_available_inventory_fallback(self):
        old = self.make_book('Older Book')
        newest = self.make_book('Newest Book')
        unavailable = self.make_book('Unavailable Book', available=False)

        recommendations = get_book_recommendations()

        self.assertEqual([book.pk for book in recommendations], [newest.pk, old.pk])
        self.assertNotIn(unavailable, recommendations)

    def test_new_logged_in_user_gets_cold_start_fallback(self):
        first = self.make_book('First Book')
        self.make_book('Seller Own Listing', seller=self.buyer)

        self.assertEqual(get_book_recommendations(self.buyer), [first])

    def test_relevant_purchase_history_ranks_similar_available_books(self):
        purchased = self.make_book('Purchased Python Book', [1.0, 0.0], available=False)
        similar = self.make_book('Another Python Book', [0.99, 0.01])
        unrelated = self.make_book('Unrelated Poetry Book', [-1.0, 0.0])
        self.make_order(purchased)

        recommendations = get_book_recommendations(self.buyer)

        self.assertEqual(recommendations, [similar])
        self.assertNotIn(purchased, recommendations)
        self.assertNotIn(unrelated, recommendations)

    def test_unrelated_history_uses_recent_inventory_fallback(self):
        purchased = self.make_book('Purchased Science Book', [1.0, 0.0], available=False)
        older = self.make_book('Older Unrelated Book', [0.0, 1.0])
        latest = self.make_book('Latest Unrelated Book', [-1.0, 0.0])
        self.make_order(purchased)

        recommendations = get_book_recommendations(self.buyer)

        self.assertEqual(recommendations[0], latest)
        self.assertIn(older, recommendations)

    def test_previous_non_cancelled_purchase_is_not_recommended_again(self):
        purchased = self.make_book('Purchased Book', [1.0, 0.0])
        similar = self.make_book('Similar Book', [1.0, 0.0])
        self.make_order(purchased)

        recommendations = get_book_recommendations(self.buyer)

        self.assertIn(similar, recommendations)
        self.assertNotIn(purchased, recommendations)

    def test_no_available_books_returns_empty_list(self):
        self.make_book('Sold Book', available=False)

        self.assertEqual(get_book_recommendations(), [])

    def test_small_inventory_returns_only_books_that_exist(self):
        first = self.make_book('Only Book')

        self.assertEqual(get_book_recommendations(limit=4), [first])

    def test_large_inventory_is_limited_to_requested_recommendation_count(self):
        books = [self.make_book(f'Book {index:03}') for index in range(30)]

        recommendations = get_book_recommendations(limit=4)

        self.assertEqual(len(recommendations), 4)
        self.assertEqual(recommendations, list(reversed(books[-4:])))

    def test_deleted_or_unavailable_books_disappear_on_next_calculation(self):
        first = self.make_book('First Book')
        second = self.make_book('Second Book')
        self.assertIn(first, get_book_recommendations())

        first.delete()
        second.is_available = False
        second.save(update_fields=['is_available'])

        self.assertEqual(get_book_recommendations(), [])

    def test_homepage_keeps_existing_content_and_shows_recommendations(self):
        self.make_book('Homepage Recommendation')

        response = self.client.get(reverse('core:landing'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Books deserve more than one reader.')
        self.assertContains(response, 'Good stories travel further together.')
        self.assertContains(response, 'Recommended for You')
        self.assertContains(response, 'Homepage Recommendation')

    def test_homepage_works_without_inventory_or_recommendations(self):
        response = self.client.get(reverse('core:landing'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Books deserve more than one reader.')
        self.assertNotContains(response, 'Recommended for You')

    def test_signup_and_existing_book_detail_still_work(self):
        book = self.make_book('Detail Page Book')
        response = self.client.post(reverse('core:signup'), {
            'username': 'new-recommendation-user',
            'email': 'reader@example.test',
            'password1': 'A-strong-test-password-123',
            'password2': 'A-strong-test-password-123',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.get(reverse('core:landing')).status_code, 200)
        detail = self.client.get(reverse('books:detail', args=[book.pk]))
        self.assertContains(detail, 'Detail Page Book')

    def test_existing_checkout_and_order_history_still_work(self):
        book = self.make_book('Checkout Regression Book')
        self.client.force_login(self.buyer)

        checkout = self.client.get(reverse('orders:checkout', args=[book.pk]))
        self.assertEqual(checkout.status_code, 200)
        response = self.client.post(reverse('orders:checkout', args=[book.pk]), {
            'shipping_address': 'Vadodara',
        })

        book.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertFalse(book.is_available)
        self.assertTrue(Order.objects.filter(buyer=self.buyer, book=book).exists())
        self.assertContains(self.client.get(reverse('orders:my_orders')), 'Checkout Regression Book')
