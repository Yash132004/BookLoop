from django.conf import settings
from django.db import models


class BookListing(models.Model):
    class Condition(models.TextChoices):
        NEW = 'New', 'New'
        LIKE_NEW = 'Like New', 'Like New'
        GOOD = 'Good', 'Good'
        FAIR = 'Fair', 'Fair'

    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='book_listings',
    )
    title = models.CharField(max_length=200)
    author = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    # Precomputed text vector used to rank semantic search results.
    search_embedding = models.JSONField(default=list, blank=True)
    # Precomputed visual vector used only by image-based book search.
    image_embedding = models.JSONField(default=list, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    condition = models.CharField(max_length=10, choices=Condition.choices)
    location = models.CharField(max_length=100)
    image = models.ImageField(upload_to='books/', blank=True)
    is_available = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.title} by {self.author}'
