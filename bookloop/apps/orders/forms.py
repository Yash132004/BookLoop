from django import forms


class CheckoutForm(forms.Form):
    shipping_address = forms.CharField(
        label='Shipping address',
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Enter the address where you would like the book delivered',
        }),
    )
