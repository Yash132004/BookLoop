from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path

from . import views


app_name = 'core'

urlpatterns = [
    path('', views.landing, name='landing'),
    path('accounts/login/', LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('accounts/logout/', LogoutView.as_view(), name='logout'),
    path('accounts/signup/', views.signup, name='signup'),
]
