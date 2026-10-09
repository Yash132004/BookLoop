from django.shortcuts import render

from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django import forms
from django.shortcuts import redirect, render

from .recommendations import get_book_recommendations

class SignupForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'


def landing(request):
    recommendations = get_book_recommendations(request.user)
    return render(request, 'core/landing.html', {'recommendations': recommendations})


def signup(request):
    if request.user.is_authenticated:
        return redirect('/books/')

    if request.method == 'POST':
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('/books/')
    else:
        form = SignupForm()

    return render(request, 'registration/signup.html', {'form': form})
