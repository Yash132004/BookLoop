from django.contrib import admin

from .models import BookListing


@admin.register(BookListing)
class BookListingAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'title',
        'author',
        'seller',
        'price',
        'condition',
        'location',
        'is_available',
        'created_at',
    )
    list_filter = ('condition', 'is_available', 'location')
    search_fields = ('title', 'author', 'seller__username')
