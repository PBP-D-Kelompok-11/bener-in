from django import forms

from .models import Review


class ReviewForm(forms.ModelForm):
    # Dideklarasikan sendiri supaya tidak ada pilihan kosong "---------".
    rating = forms.TypedChoiceField(
        label='Rating',
        choices=Review.RATING_CHOICES,
        coerce=int,
        widget=forms.RadioSelect,
        error_messages={'required': 'Pilih rating 1 sampai 5.'},
    )

    class Meta:
        model = Review
        fields = ['rating', 'comment']
        labels = {'comment': 'Komentar (opsional)'}
        widgets = {
            'comment': forms.Textarea(attrs={
                'rows': 4,
                'placeholder': 'Ceritakan pengalamanmu dengan mitra ini',
            }),
        }