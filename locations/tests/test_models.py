from django.db import IntegrityError, transaction

from locations.models import RepairPlace, SavedPlace

from .base import LocationsTestCase, make_customer, make_place, make_saved


class RepairPlaceTests(LocationsTestCase):
    def test_str_and_osm_url(self):
        place = make_place(osm_id=42, name='Tambal Ban')
        self.assertEqual(str(place), 'Tambal Ban (node/42)')
        self.assertEqual(place.osm_url, 'https://www.openstreetmap.org/node/42')

    def test_osm_element_is_unique(self):
        make_place(osm_id=1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_place(osm_id=1, name='Duplikat')

    def test_same_id_different_type_is_allowed(self):
        make_place(osm_id=1)
        make_place(osm_id=1, osm_type='way')
        self.assertEqual(RepairPlace.objects.count(), 2)


class SavedPlaceTests(LocationsTestCase):
    def setUp(self):
        super().setUp()
        self.customer = make_customer()
        self.place = make_place()

    def test_defaults_and_str(self):
        saved = make_saved(self.customer, self.place)
        self.assertEqual(saved.status, SavedPlace.Status.WANT)
        self.assertFalse(saved.is_deleted)
        self.assertIn('Servis HP Maju', str(saved))

    def test_soft_delete_hides_from_default_manager(self):
        saved = make_saved(self.customer, self.place)
        saved.soft_delete()
        self.assertTrue(saved.is_deleted)
        self.assertEqual(SavedPlace.objects.count(), 0)
        self.assertEqual(SavedPlace.all_objects.count(), 1)

    def test_restore_brings_it_back(self):
        saved = make_saved(self.customer, self.place)
        saved.soft_delete()
        saved.restore()
        self.assertFalse(saved.is_deleted)
        self.assertEqual(SavedPlace.objects.count(), 1)

    def test_customer_cannot_save_same_place_twice(self):
        make_saved(self.customer, self.place)
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_saved(self.customer, self.place)

    def test_two_customers_can_save_same_place(self):
        make_saved(self.customer, self.place)
        make_saved(make_customer('sari'), self.place)
        self.assertEqual(SavedPlace.objects.count(), 2)
