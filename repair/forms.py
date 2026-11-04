from django import forms

from authentication.models import KategoriBarang, MitraReparasi

from .models import RepairRequest


class RepairRequestCreateForm(forms.ModelForm):
    # ModelChoiceField mengubah ID yang dikirim browser menjadi objek Mitra yang valid.
    mitra = forms.ModelChoiceField(
        queryset=MitraReparasi.objects.none(),
        error_messages={
            'required': 'Pilih mitra reparasi.',
            'invalid_choice': 'Mitra ini tidak tersedia. Pilih mitra aktif lainnya.',
        },
    )

    class Meta:
        model = RepairRequest
        # Pemilik dan status tidak berasal dari browser; view dan model yang menentukannya.
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
        self.fields['category'].choices = KategoriBarang.choices
        # Yang divalidasi di server adalah Mitra aktif. Cocok kategori hanya prioritas tampilan.
        self.fields['mitra'].queryset = MitraReparasi.objects.filter(is_active=True)

    # Django memanggil clean_<field>() lewat is_valid(); return nilainya atau lempar ValidationError.
    # Untuk membandingkan dua isian, tempatnya clean() di kelas form yang sama.
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
    

class RepairRequestEditForm(forms.ModelForm):
    # Form edit sengaja terpisah: kategori, Mitra, dan status tidak bisa diubah lewat form ini.
    class Meta:
        model = RepairRequest
        fields = ['item_name', 'description']
        labels = {
            'item_name': 'Nama barang',
            'description': 'Masalah yang dialami',
        }
        widgets = {
            'item_name': forms.TextInput(attrs={
                'placeholder': 'Contoh: ponsel Samsung A52',
                'aria-describedby': 'repair-edit-item-hint repair-edit-item-error',
            }),
            'description': forms.Textarea(attrs={
                'rows': 6,
                'placeholder': 'Ceritakan kerusakan, gejala, dan kapan masalah mulai terjadi.',
                'aria-describedby': 'repair-edit-description-hint repair-edit-description-error',
            }),
        }
        error_messages = {
            'item_name': {'required': 'Isi nama barang.'},
            'description': {'required': 'Jelaskan masalah pada barang.'},
        }


class MitraTransitionForm(forms.Form):
    # Form membaca aksi yang diminta, bukan menyimpan status. Izin dan urutan dicek di view/model.
    # expected_status adalah status saat kartu dirender, bukan status yang dipercaya begitu saja.
    expected_status = forms.ChoiceField(choices=RepairRequest.Status.choices)
    to_status = forms.ChoiceField(choices=[
        (RepairRequest.Status.ACCEPTED, 'Terima permintaan'),
        (RepairRequest.Status.REJECTED, 'Tolak permintaan'),
        (RepairRequest.Status.IN_PROGRESS, 'Mulai reparasi'),
        (RepairRequest.Status.COMPLETED, 'Selesaikan reparasi'),
        (RepairRequest.Status.UNABLE_TO_REPAIR, 'Tidak dapat diperbaiki'),
    ])
    reason = forms.CharField(required=False, strip=True, widget=forms.Textarea)
