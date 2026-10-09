from decimal import Decimal
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from PIL import Image

from .models import BookListing


def image_upload(name='cover.png', color=(220, 40, 40), size=(16, 16)):
    output = BytesIO()
    Image.new('RGB', size, color).save(output, format='PNG')
    return SimpleUploadedFile(name, output.getvalue(), content_type='image/png')


class BookImageSearchTests(TestCase):
    def setUp(self):
        self.seller = get_user_model().objects.create_user(username='image-seller')
        self.match = self.create_book(
            'Matching Cover', 'Good', 'Vadodara', [1.0, 0.0]
        )
        self.other = self.create_book(
            'Unrelated Cover', 'Fair', 'Vaghodia', [0.0, 1.0]
        )
        self.unavailable = self.create_book(
            'Unavailable Cover', 'Good', 'Vadodara', [1.0, 0.0], is_available=False
        )
        self.without_image = BookListing.objects.create(
            seller=self.seller,
            title='No Image', author='Reader', price=Decimal('50.00'),
            condition='Good', location='Vadodara',
        )

    def create_book(self, title, condition, location, vector, **extra):
        return BookListing.objects.create(
            seller=self.seller,
            title=title,
            author='Reader',
            price=Decimal('50.00'),
            condition=condition,
            location=location,
            image=f'books/{title.lower().replace(" ", "-")}.png',
            image_embedding=vector,
            **extra,
        )

    @override_settings(BOOK_IMAGE_SEARCH_THRESHOLD=0.80)
    @patch('apps.books.views.embed_uploaded_image', return_value=[1.0, 0.0])
    def test_valid_matching_image_returns_only_similar_available_listings(self, _embed):
        response = self.client.post(
            reverse('books:image_search'), {'image': image_upload()}
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'books/_results.html')
        self.assertContains(response, 'Matching Cover')
        self.assertNotContains(response, 'Unrelated Cover')
        self.assertNotContains(response, 'Unavailable Cover')
        self.assertNotContains(response, 'No Image')

    @patch('apps.books.views.embed_uploaded_image', return_value=[0.0, 1.0])
    def test_unrelated_image_returns_similarity_ranked_book(self, _embed):
        response = self.client.post(
            reverse('books:image_search'), {'image': image_upload(color=(20, 40, 220))}
        )
        self.assertContains(response, 'Unrelated Cover')
        self.assertNotContains(response, 'Matching Cover')

    @patch('apps.books.views.embed_uploaded_image', return_value=[0.0, 1.0])
    def test_no_indexed_images_returns_no_books_found(self, _embed):
        BookListing.objects.update(image_embedding=[])
        response = self.client.post(
            reverse('books:image_search'), {'image': image_upload()}
        )
        self.assertContains(response, 'No books found')

    def test_invalid_and_non_image_uploads_return_no_books_found(self):
        for upload in (
            SimpleUploadedFile('bad.png', b'not an image', content_type='image/png'),
            SimpleUploadedFile('notes.txt', b'plain text', content_type='text/plain'),
        ):
            response = self.client.post(reverse('books:image_search'), {'image': upload})
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'No books found')

    def test_oversized_image_is_rejected(self):
        valid_png = image_upload().read()
        oversized = SimpleUploadedFile(
            'large.png', valid_png + b' ' * (5 * 1024 * 1024), content_type='image/png'
        )
        response = self.client.post(reverse('books:image_search'), {'image': oversized})
        self.assertContains(response, 'No books found')

    @patch('apps.books.views.embed_uploaded_image', return_value=[1.0, 0.0])
    def test_condition_and_location_filters_apply_to_image_search(self, _embed):
        response = self.client.post(reverse('books:image_search'), {
            'image': image_upload(), 'condition': 'Good', 'location': 'vadodara',
        })
        self.assertContains(response, 'Matching Cover')
        self.assertNotContains(response, 'Unrelated Cover')

    def test_get_is_not_allowed_and_post_uses_csrf_middleware(self):
        self.assertEqual(self.client.get(reverse('books:image_search')).status_code, 405)
        csrf_client = Client(enforce_csrf_checks=True)
        response = csrf_client.post(
            reverse('books:image_search'), {'image': image_upload()}
        )
        self.assertEqual(response.status_code, 403)


class BookImageEmbeddingLifecycleTests(TestCase):
    def setUp(self):
        self.seller = get_user_model().objects.create_user(
            username='listing-seller', password='test-pass'
        )
        self.client.force_login(self.seller)

    @patch('apps.books.views.embed_text', return_value=[1.0, 0.0])
    @patch('apps.books.views.embed_listing_image', return_value=[0.2, 0.8])
    def test_create_listing_generates_image_embedding(self, _image_embed, _text_embed):
        response = self.client.post(reverse('books:create'), {
            'title': 'New Cover', 'author': 'Reader', 'price': '50.00',
            'condition': 'Good', 'location': 'Vadodara', 'image': image_upload(),
        })
        book = BookListing.objects.get(title='New Cover')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(book.image_embedding, [0.2, 0.8])
        _image_embed.assert_called_once_with(book)

    def make_book(self):
        return BookListing.objects.create(
            seller=self.seller, title='Editable Cover', author='Reader',
            price=Decimal('50.00'), condition='Good', location='Vadodara',
            image=image_upload('old.png'), image_embedding=[1.0, 0.0],
        )

    @patch('apps.books.views.embed_text', return_value=[1.0, 0.0])
    @patch('apps.books.views.embed_listing_image', return_value=[0.0, 1.0])
    def test_replacing_image_updates_embedding(self, _image_embed, _text_embed):
        book = self.make_book()
        response = self.client.post(reverse('books:edit', args=[book.pk]), {
            'title': book.title, 'author': book.author, 'price': '50.00',
            'condition': book.condition, 'location': book.location,
            'image': image_upload('new.png', color=(10, 10, 230)),
        })
        book.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(book.image_embedding, [0.0, 1.0])
        _image_embed.assert_called_once_with(book)

    @patch('apps.books.views.embed_text', return_value=[1.0, 0.0])
    @patch('apps.books.views.embed_listing_image')
    def test_unchanged_image_does_not_regenerate_embedding(self, _image_embed, _text_embed):
        book = self.make_book()
        response = self.client.post(reverse('books:edit', args=[book.pk]), {
            'title': book.title, 'author': book.author, 'price': '50.00',
            'condition': book.condition, 'location': book.location,
        })
        book.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(book.image_embedding, [1.0, 0.0])
        _image_embed.assert_not_called()

    @patch('apps.books.views.embed_text', return_value=[1.0, 0.0])
    @patch('apps.books.views.embed_listing_image')
    def test_removing_image_clears_embedding(self, _image_embed, _text_embed):
        book = self.make_book()
        response = self.client.post(reverse('books:edit', args=[book.pk]), {
            'title': book.title, 'author': book.author, 'price': '50.00',
            'condition': book.condition, 'location': book.location, 'image-clear': 'on',
        })
        book.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertFalse(book.image)
        self.assertEqual(book.image_embedding, [])
        _image_embed.assert_not_called()
