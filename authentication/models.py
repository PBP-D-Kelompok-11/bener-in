from django.contrib.auth.models import AbstractUser
from django.db import models


class KategoriBarang(models.TextChoices):
    """Kunci sama dengan dropdown kategori di peta (index.html)."""
    GADGET = 'gadget', 'Gadget (HP, laptop, tablet)'
    ELEKTRONIK = 'elektronik', 'Perabot elektronik (TV, kulkas, AC)'
    MOBIL = 'mobil', 'Mobil'
    MOTOR = 'motor', 'Motor'
    SEPEDA = 'sepeda', 'Sepeda'
    FURNITUR = 'furnitur', 'Furnitur & perabot kayu'
    SEPATU = 'sepatu', 'Sepatu & tas'
    PAKAIAN = 'pakaian', 'Pakaian & jahitan'
    JAM = 'jam', 'Jam tangan & jam dinding'
    PERHIASAN = 'perhiasan', 'Perhiasan'
    LAINNYA = 'lainnya', 'Lainnya (reparasi umum)'


class BaseAccount(AbstractUser):
    """Field bersama. Abstract, jadi Customer dan MitraReparasi punya tabel sendiri."""
    role = None  # diisi di subclass, dipakai navbar: user.role
    first_name = None  # diganti nama_lengkap
    last_name = None

    nama_lengkap = models.CharField(max_length=150)
    no_hp = models.CharField(max_length=20)

    # Dua model turunan AbstractUser: related_name harus beda supaya tidak bentrok di Group/Permission
    groups = models.ManyToManyField(
        'auth.Group', verbose_name='groups', blank=True,
        related_name='%(class)s_set', related_query_name='%(class)s',
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission', verbose_name='user permissions', blank=True,
        related_name='%(class)s_set', related_query_name='%(class)s',
    )

    class Meta:
        abstract = True

    def get_full_name(self):
        return self.nama_lengkap

    def get_short_name(self):
        return self.nama_lengkap.split(' ')[0] or self.username


class Customer(BaseAccount):
    role = 'customer'
    alamat = models.TextField(blank=True)

    def __str__(self):
        return f'{self.nama_lengkap} (@{self.username})'


class MitraReparasi(BaseAccount):
    role = 'mitra'
    nama_usaha = models.CharField(max_length=150)
    layanan = models.JSONField(default=list)  # daftar kunci KategoriBarang
    alamat = models.TextField()
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)

    class Meta:
        verbose_name = 'mitra reparasi'
        verbose_name_plural = 'mitra reparasi'

    def __str__(self):
        return f'{self.nama_usaha} (@{self.username})'