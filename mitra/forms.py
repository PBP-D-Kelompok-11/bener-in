from django import forms
from .models import Mitra

class MitraForm(forms.ModelForm):
    class Meta:
        model = Mitra
        fields = ['nama_toko', 'layanan', 'alamat', 'kontak']
        widgets = {
            'nama_toko': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nama Toko Reparasi'}),
            'layanan': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Deskripsi layanan/keahlian'}),
            'alamat': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Alamat lengkap'}),
            'kontak': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nomor WhatsApp / HP'}),
        }