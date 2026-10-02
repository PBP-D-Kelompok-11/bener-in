from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from .models import Customer, KategoriBarang, MitraReparasi


class RegisterBaseForm(forms.ModelForm):
    password1 = forms.CharField(label='Password', widget=forms.PasswordInput)
    password2 = forms.CharField(label='Ulangi password', widget=forms.PasswordInput)
    field_order = ['username', 'password1', 'password2']

    def clean_username(self):
        username = self.cleaned_data['username']
        # Unique di DB hanya berlaku per tabel, jadi cek dua tabel di sini
        if (Customer.objects.filter(username__iexact=username).exists()
                or MitraReparasi.objects.filter(username__iexact=username).exists()):
            raise ValidationError('Username ini sudah dipakai.')
        return username

    def clean(self):
        data = super().clean()
        p1, p2 = data.get('password1'), data.get('password2')
        if p1 and p2 and p1 != p2:
            self.add_error('password2', 'Password tidak sama.')
        elif p1:
            try:
                validate_password(p1)
            except ValidationError as e:
                self.add_error('password1', e)
        return data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
        return user


class CustomerRegisterForm(RegisterBaseForm):
    class Meta:
        model = Customer
        fields = ['username', 'nama_lengkap', 'email', 'no_hp', 'alamat']
        labels = {'nama_lengkap': 'Nama lengkap', 'email': 'Email (opsional)',
                  'no_hp': 'No. HP', 'alamat': 'Alamat (opsional)'}
        widgets = {'alamat': forms.Textarea(attrs={'rows': 3})}


class MitraRegisterForm(RegisterBaseForm):
    layanan = forms.MultipleChoiceField(
        label='Layanan yang dikerjakan',
        choices=KategoriBarang.choices,
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = MitraReparasi
        fields = ['username', 'nama_lengkap', 'nama_usaha', 'email', 'no_hp',
                  'layanan', 'alamat', 'latitude', 'longitude']
        labels = {'nama_lengkap': 'Nama penanggung jawab', 'nama_usaha': 'Nama usaha',
                  'email': 'Email (opsional)', 'no_hp': 'Kontak (HP/WhatsApp)',
                  'alamat': 'Alamat usaha'}
        widgets = {'alamat': forms.Textarea(attrs={'rows': 3}),
                   'latitude': forms.HiddenInput, 'longitude': forms.HiddenInput}
        error_messages = {'latitude': {'required': 'Klik peta untuk menandai lokasi usahamu.'},
                          'longitude': {'required': 'Klik peta untuk menandai lokasi usahamu.'}}