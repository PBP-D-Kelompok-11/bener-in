from django.core.cache import cache
from django.test import TestCase

from authentication.models import Customer, KategoriBarang, MitraReparasi
from locations.models import RepairPlace, SavedPlace

CUSTOMER_BACKEND = 'authentication.backends.CustomerBackend'
MITRA_BACKEND = 'authentication.backends.MitraBackend'
AJAX = {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'}


def make_customer(username='budi'):
    return Customer.objects.create_user(
        username=username, password='kata-sandi-123',
        nama_lengkap=f'{username.title()} Santoso', no_hp='0812',
    )


def make_mitra(username='bengkel', lat='-6.200000', lng='106.800000',
               layanan=(KategoriBarang.GADGET,), active=True):
    return MitraReparasi.objects.create_user(
        username=username, password='kata-sandi-123', nama_lengkap='Pak Joko',
        no_hp='0899', nama_usaha=f'Usaha {username}', layanan=list(layanan),
        alamat='Jl. Mawar 1', latitude=lat, longitude=lng, is_active=active,
    )


def make_place(osm_id=1, name='Servis HP Maju', category='gadget', **extra):
    fields = dict(
        osm_type='node', osm_id=osm_id, name=name, category=category,
        latitude='-6.200000', longitude='106.800000',
        address='Jl. Melati 5', phone='021-555',
    )
    fields.update(extra)
    return RepairPlace.objects.create(**fields)


def make_saved(customer, place, **extra):
    return SavedPlace.objects.create(customer=customer, place=place, **extra)


class LocationsTestCase(TestCase):
    def setUp(self):
        cache.clear()  # cache dan rate limit tidak boleh bocor antar tes

    def login_customer(self, customer):
        self.client.force_login(customer, backend=CUSTOMER_BACKEND)

    def login_mitra(self, mitra):
        self.client.force_login(mitra, backend=MITRA_BACKEND)
