from django import forms

from authentication.models import MitraReparasi

from .models import RepairRequest


class RepairRequestCreateForm(forms.ModelForm):
    mitra = forms.ModelChoiceField(
        queryset=MitraReparasi.objects.none(),
        error_messages={
            'required': 'Pilih mitra reparasi.',
            'invalid_choice': 'Mitra ini tidak tersedia. Pilih mitra aktif lainnya.',
        },
    )

    class Meta:
        model = RepairRequest
        fields = ['category', 'mitra', 'item_name', 'description']
        labels = {
            'category': 'Kategori barang',
            'item_name': 'Nama barang',
            'description': 'Masalah yang dialami',
        }
        widgets = {
            'category': forms.RadioSelect(attrs={'class': 'repair-radio'}),
            'item_name': forms.TextInput(attrs={
                'placeholder': 'Contoh: ponsel Samsung A52',
                'autocomplete': 'off',
                'aria-describedby': 'repair-item-hint repair-item-error',
            }),
            'description': forms.Textarea(attrs={
                'rows': 6,
                'placeholder': 'Ceritakan kerusakan, gejala, dan kapan masalah mulai terjadi.',
                'aria-describedby': 'repair-description-hint repair-description-error',
            }),
        }
        error_messages = {
            'category': {'required': 'Pilih kategori barang.', 'invalid_choice': 'Pilih kategori yang tersedia.'},
            'item_name': {'required': 'Isi nama barang.'},
            'description': {'required': 'Jelaskan masalah pada barang.'},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['mitra'].queryset = MitraReparasi.objects.filter(is_active=True)

    def clean_item_name(self):
        value = self.cleaned_data['item_name'].strip()
        if not value:
            raise forms.ValidationError('Isi nama barang.')
        return value

    def clean_description(self):
        value = self.cleaned_data['description'].strip()
        if not value:
            raise forms.ValidationError('Jelaskan masalah pada barang.')
        return value
