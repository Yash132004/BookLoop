from django.urls import path

from . import views


app_name = 'orders'

urlpatterns = [
    path('', views.my_orders, name='my_orders'),
    path('checkout/<int:book_id>/', views.checkout, name='checkout'),
    path('success/<int:order_id>/', views.order_success, name='success'),
]
