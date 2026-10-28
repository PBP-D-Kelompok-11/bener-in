from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone

from authentication.models import KategoriBarang

# Nilai `osm_type` untuk baris RepairPlace yang merupakan "cermin" dari mitra
# terdaftar bener.in (osm_id = pk mitra). Dipakai supaya mitra bisa disimpan
# lewat SavedPlace yang sama tanpa mengubah skema database.
MITRA_SOURCE = 'mitra'


class RepairPlace(models.Model):
    """Tempat reparasi yang berasal dari OpenStreetMap (Overpass API).

    Tabel ini berfungsi sebagai cache/direktori lokal: diisi saat pengguna
    mencari di peta atau lewat `manage.py seed_repair_places`. Pengguna tidak
    mengubahnya langsung, yang di-CRUD pengguna adalah `SavedPlace`.
    """

    osm_type = models.CharField(max_length=10)  # node / way / relation
    osm_id = models.BigIntegerField()
    name = models.CharField(max_length=255)
    category = models.CharField(max_length=20, choices=KategoriBarang.choices)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    address = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=60, blank=True)
    fetched_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(
                fields=['osm_type', 'osm_id'], name='unique_osm_element',
            ),
        ]
        indexes = [
            models.Index(fields=['category']),
            models.Index(fields=['latitude', 'longitude']),
        ]

    def __str__(self):
        return f'{self.name} ({self.osm_type}/{self.osm_id})'

    @property
    def osm_url(self):
        return f'https://www.openstreetmap.org/{self.osm_type}/{self.osm_id}'

    @property
    def is_mitra(self):
        return self.osm_type == MITRA_SOURCE

    @property
    def detail_url(self):
        """Tautan detail: halaman review untuk mitra, halaman OSM untuk lainnya."""
        if self.is_mitra:
            return reverse('reviews:mitra', args=[self.osm_id])
        return self.osm_url


class ActiveSavedPlaceManager(models.Manager):
    """Manager bawaan: hanya tempat yang belum dihapus (soft delete)."""

    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)


class SavedPlace(models.Model):
    """Tempat reparasi yang disimpan seorang customer, lengkap dengan catatan."""

    class Status(models.TextChoices):
        WANT = 'want', 'Ingin dikunjungi'
        VISITED = 'visited', 'Sudah dikunjungi'

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='saved_places',
    )
    place = models.ForeignKey(
        RepairPlace, on_delete=models.CASCADE, related_name='saved_by',
    )
    note = models.CharField(max_length=500, blank=True)
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.WANT,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True, editable=False)

    objects = ActiveSavedPlaceManager()  # harus pertama: jadi default manager
    all_objects = models.Manager()

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['customer', 'place'], name='unique_saved_place_per_customer',
            ),
        ]
        indexes = [models.Index(fields=['customer', 'deleted_at'])]

    def __str__(self):
        return f'{self.place.name} (disimpan {self.customer_id})'

    @property
    def is_deleted(self):
        return self.deleted_at is not None

    def soft_delete(self):
        self.deleted_at = timezone.now()
        self.save(update_fields=['deleted_at', 'updated_at'])

    def restore(self):
        self.deleted_at = None
        self.save(update_fields=['deleted_at', 'updated_at'])
