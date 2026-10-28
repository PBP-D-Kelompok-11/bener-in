from django import forms

from .models import SavedPlace


class SavedPlaceForm(forms.ModelForm):
    class Meta:
        model = SavedPlace
        fields = ['note', 'status']
        labels = {'note': 'Catatan (opsional)', 'status': 'Status'}
        widgets = {
            'note': forms.Textarea(attrs={
                'rows': 3, 'maxlength': 500,
                'placeholder': 'Mis. buka sampai jam 5 sore, bisa servis layar HP',
            }),
        }

    def clean_note(self):
        return ' '.join((self.cleaned_data.get('note') or '').split())
