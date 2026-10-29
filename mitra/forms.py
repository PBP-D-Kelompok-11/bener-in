from django import forms
from .models import Mitra

class MitraForm(forms.ModelForm):
    class Meta:
        model = Mitra
        fields = ['nama_toko', 'layanan', 'alamat', 'kontak']
        widgets = {
            'nama_toko': forms.TextInput(attrs={
                'class': 'form-input-custom', 
                'placeholder': 'Contoh: Benerin Laptop & HP Depok'
            }),
            'layanan': forms.Textarea(attrs={
                'class': 'form-input-custom', 
                'rows': 3, 
                'placeholder': 'Contoh: Service Hardware Laptop, Ganti LCD, Install OS, Perbaikan Mati Total'
            }),
            'alamat': forms.Textarea(attrs={
                'class': 'form-input-custom', 
                'rows': 3, 
                'placeholder': 'Contoh: Jl. Margonda Raya No. 123, Beji, Kota Depok, Jawa Barat'
            }),
            'kontak': forms.TextInput(attrs={
                'class': 'form-input-custom', 
                'placeholder': 'Contoh: 081234567890'
            }),
        }
        labels = {
            'nama_toko': 'Nama Toko',
            'layanan': 'Layanan Reparasi',
            'alamat': 'Alamat Lengkap Toko',
            'kontak': 'Nomor Kontak / WhatsApp',
        }