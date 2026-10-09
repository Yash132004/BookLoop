from django import forms
from PIL import Image, UnidentifiedImageError

from .models import BookListing


class BookListingForm(forms.ModelForm):
    class Meta:
        model = BookListing
        fields = (
            'title',
            'author',
            'description',
            'price',
            'condition',
            'location',
            'image',
        )
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'author': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'min': '0.01', 'step': '0.01'}),
            'condition': forms.Select(attrs={'class': 'form-select'}),
            'location': forms.TextInput(attrs={'class': 'form-control'}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }


class BookImageSearchForm(forms.Form):
    image = forms.ImageField()

    def clean_image(self):
        image_file = self.cleaned_data['image']
        if image_file.size > 5 * 1024 * 1024:
            raise forms.ValidationError('Choose an image smaller than 5 MB.')

        try:
            image_file.seek(0)
            with Image.open(image_file) as image:
                if image.format not in {'JPEG', 'PNG', 'WEBP'}:
                    raise forms.ValidationError('Use a JPEG, PNG, or WebP image.')
                if image.width * image.height > 25_000_000:
                    raise forms.ValidationError('Choose an image with 25 megapixels or fewer.')
                image.verify()
            image_file.seek(0)
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
            raise forms.ValidationError('The selected file is not a valid supported image.')

        return image_file
