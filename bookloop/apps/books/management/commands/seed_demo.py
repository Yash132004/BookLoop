import os
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.books.models import BookListing


DEMO_USERS = (
    ('bookloop_demo_seller1', 'seller1@example.test', 'Aarav', 'Patel'),
    ('bookloop_demo_seller2', 'seller2@example.test', 'Mira', 'Shah'),
    ('bookloop_demo_seller3', 'seller3@example.test', 'Rohan', 'Desai'),
    ('bookloop_demo_seller4', 'seller4@example.test', 'Kavya', 'Mehta'),
)

DEMO_BOOKS = (
    {
        'title': 'Atomic Habits', 'author': 'James Clear', 'price': '280.00',
        'condition': BookListing.Condition.GOOD, 'location': 'Alkapuri, Vadodara',
        'seller': 0, 'description': 'A practical guide to building better habits, with light signs of use.',
    },
    {
        'title': 'Clean Code', 'author': 'Robert C. Martin', 'price': '450.00',
        'condition': BookListing.Condition.LIKE_NEW, 'location': 'Gotri, Vadodara',
        'seller': 1, 'description': 'A well-kept programming book with clean pages and a sound cover.',
    },
    {
        'title': 'Python Crash Course', 'author': 'Eric Matthes', 'price': '520.00',
        'condition': BookListing.Condition.NEW, 'location': 'Manjalpur, Vadodara',
        'seller': 2, 'description': 'A nearly unused introduction to Python programming and projects.',
    },
    {
        'title': 'The Alchemist', 'author': 'Paulo Coelho', 'price': '150.00',
        'condition': BookListing.Condition.FAIR, 'location': 'Karelibaug, Vadodara',
        'seller': 3, 'description': 'A much-loved paperback with some wear on the cover; all pages are intact.',
    },
    {
        'title': 'Rich Dad Poor Dad', 'author': 'Robert T. Kiyosaki', 'price': '190.00',
        'condition': BookListing.Condition.GOOD, 'location': 'Fatehgunj, Vadodara',
        'seller': 0, 'description': 'A readable copy with minor shelf wear.',
    },
    {
        'title': "Harry Potter and the Philosopher's Stone", 'author': 'J. K. Rowling', 'price': '240.00',
        'condition': BookListing.Condition.LIKE_NEW, 'location': 'Akota, Vadodara',
        'seller': 1, 'description': 'A gently read fantasy paperback in very good shape.',
    },
    {
        'title': 'Deep Work', 'author': 'Cal Newport', 'price': '310.00',
        'condition': BookListing.Condition.GOOD, 'location': 'Vaghodia',
        'seller': 2, 'description': 'A useful productivity read with a few light marks on the cover.',
    },
    {
        'title': 'Think and Grow Rich', 'author': 'Napoleon Hill', 'price': '175.00',
        'condition': BookListing.Condition.FAIR, 'location': 'Nizampura, Vadodara',
        'seller': 3, 'description': 'An older, well-read copy with intact pages and visible cover wear.',
    },
    {
        'title': 'Introduction to Algorithms',
        'author': 'Thomas H. Cormen, Charles E. Leiserson, Ronald L. Rivest, Clifford Stein',
        'price': '950.00', 'condition': BookListing.Condition.GOOD,
        'location': 'Waghodia Road, Vadodara', 'seller': 0,
        'description': 'A substantial computer science reference in good used condition.',
    },
    {
        'title': 'The Pragmatic Programmer', 'author': 'David Thomas and Andrew Hunt', 'price': '390.00',
        'condition': BookListing.Condition.NEW, 'location': 'Vasna-Bhayli Road, Vadodara',
        'seller': 1, 'description': 'A carefully stored copy with minimal signs of handling.',
    },
)


class Command(BaseCommand):
    help = 'Create reusable local demo users and book listings for BookLoop.'

    def handle(self, *args, **options):
        password = os.environ.get('BOOKLOOP_DEMO_PASSWORD', 'LocalBooks!2026')
        if not password:
            raise CommandError('BOOKLOOP_DEMO_PASSWORD cannot be empty.')

        User = get_user_model()
        sellers = []
        users_created = 0
        listings_created = 0

        with transaction.atomic():
            for username, email, first_name, last_name in DEMO_USERS:
                user, created = User.objects.get_or_create(
                    username=username,
                    defaults={
                        'email': email,
                        'first_name': first_name,
                        'last_name': last_name,
                    },
                )
                if created:
                    user.set_password(password)
                    user.save(update_fields=['password'])
                    users_created += 1
                sellers.append(user)

            for book_data in DEMO_BOOKS:
                data = book_data.copy()
                seller = sellers[data.pop('seller')]
                defaults = {
                    **data,
                    'price': Decimal(data['price']),
                    'is_available': True,
                }
                _, created = BookListing.objects.get_or_create(
                    seller=seller,
                    title=data['title'],
                    author=data['author'],
                    defaults=defaults,
                )
                if created:
                    listings_created += 1

        self.stdout.write(self.style.SUCCESS(
            f'Demo seed complete: {users_created} users created; '
            f'{listings_created} listings created.'
        ))
        self.stdout.write('Demo login credentials (development only):')
        for username, email, _, _ in DEMO_USERS:
            self.stdout.write(f'  Username: {username}  Email: {email}  Password: {password}')
        self.stdout.write(
            'If a demo user already existed, its existing password was preserved.'
        )
