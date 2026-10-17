from django.db import models
from django.conf import settings

class Mitra(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='mitra_profile')
    nama_toko = models.CharField(max_length=255)
    layanan = models.TextField(help_text="Layanan atau keahlian perbaikan yang disediakan")
    alamat = models.TextField()
    kontak = models.CharField(max_length=50)

    def __str__(self):
        return self.nama_toko