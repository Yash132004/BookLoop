from django.urls import path

from . import views


app_name = 'books'

urlpatterns = [
    path('', views.listing_list, name='listing_list'),
    path('search/', views.listing_search, name='search'),
    path('image-search/', views.listing_image_search, name='image_search'),
    path('create/', views.listing_create, name='create'),
    path('my-listings/', views.my_listings, name='my_listings'),
    path('<int:pk>/edit/', views.listing_edit, name='edit'),
    path('<int:pk>/delete/', views.listing_delete, name='delete'),
    path('<int:pk>/', views.listing_detail, name='detail'),
]
