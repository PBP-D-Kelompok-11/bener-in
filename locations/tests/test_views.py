from django.urls import reverse

from locations.models import RepairPlace, SavedPlace

from .base import (AJAX, LocationsTestCase, make_customer, make_mitra, make_place,
                   make_saved)


class DiscoverViewTests(LocationsTestCase):
    def test_public_page_renders(self):
        response = self.client.get(reverse('locations:discover'))
        self.assertContains(response, 'Peta reparasi')
        self.assertContains(response, 'Nomor telepon disembunyikan')

    def test_customer_gets_saved_ids(self):
        customer = make_customer()
        place = make_place()
        make_saved(customer, place)
        make_saved(customer, make_place(2), )  # akan di-soft-delete
        SavedPlace.objects.get(place__osm_id=2).soft_delete()
        self.login_customer(customer)
        response = self.client.get(reverse('locations:discover'))
        self.assertEqual(response.context['saved_ids'], [place.pk])
        self.assertTrue(response.context['is_customer'])
        self.assertNotContains(response, 'Nomor telepon disembunyikan')

    def test_mitra_can_view_but_is_not_customer(self):
        self.login_mitra(make_mitra())
        response = self.client.get(reverse('locations:discover'))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['is_customer'])
        self.assertEqual(response.context['saved_ids'], [])


class AuthGateTests(LocationsTestCase):
    """Semua halaman tempat tersimpan: login + customer."""

    def urls(self):
        return [
            ('get', reverse('locations:saved')),
            ('post', reverse('locations:saved_create')),
            ('get', reverse('locations:saved_edit', args=[1])),
            ('post', reverse('locations:saved_delete', args=[1])),
            ('post', reverse('locations:saved_restore', args=[1])),
        ]

    def test_anonymous_is_redirected_to_login(self):
        for method, url in self.urls():
            response = getattr(self.client, method)(url)
            self.assertEqual(response.status_code, 302, url)
            self.assertTrue(response['Location'].startswith(reverse('authentication:login')), url)
            self.assertIn('next=', response['Location'])

    def test_anonymous_ajax_gets_401_json(self):
        response = self.client.post(reverse('locations:saved_create'), **AJAX)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()['login_url'], reverse('authentication:login'))

    def test_mitra_gets_403(self):
        self.login_mitra(make_mitra())
        for method, url in self.urls():
            self.assertEqual(getattr(self.client, method)(url).status_code, 403, url)

    def test_403_page_explains_why(self):
        self.login_mitra(make_mitra())
        response = self.client.get(reverse('locations:saved'))
        self.assertContains(response, 'Kamu tidak punya akses', status_code=403)


class SavedListTests(LocationsTestCase):
    def setUp(self):
        super().setUp()
        self.customer = make_customer()
        self.other = make_customer('sari')
        self.login_customer(self.customer)
        self.hp = make_saved(self.customer, make_place(1, 'Servis HP Maju', 'gadget', address='Depok'),
                             note='buka sore', status='visited')
        self.sepeda = make_saved(self.customer, make_place(2, 'Bengkel Sepeda', 'sepeda'))
        make_saved(self.other, make_place(3, 'Milik Sari', 'gadget'))
        self.url = reverse('locations:saved')

    def names(self, **params):
        response = self.client.get(self.url, params)
        self.assertEqual(response.status_code, 200)
        return sorted(s.place.name for s in response.context['items'])

    def test_shows_only_own_places(self):
        self.assertEqual(self.names(), ['Bengkel Sepeda', 'Servis HP Maju'])

    def test_hides_soft_deleted(self):
        self.sepeda.soft_delete()
        self.assertEqual(self.names(), ['Servis HP Maju'])

    def test_filter_by_text_in_name_address_or_note(self):
        self.assertEqual(self.names(q='maju'), ['Servis HP Maju'])
        self.assertEqual(self.names(q='depok'), ['Servis HP Maju'])
        self.assertEqual(self.names(q='sore'), ['Servis HP Maju'])

    def test_filter_by_category_and_status(self):
        self.assertEqual(self.names(category='sepeda'), ['Bengkel Sepeda'])
        self.assertEqual(self.names(status='visited'), ['Servis HP Maju'])
        self.assertEqual(self.names(category='gadget', status='want'), [])

    def test_invalid_filter_values_are_ignored(self):
        response = self.client.get(self.url, {'category': 'roket', 'status': 'xx'})
        self.assertEqual(len(response.context['items']), 2)
        self.assertEqual(response.context['category'], '')
        self.assertEqual(response.context['status'], '')

    def test_empty_states(self):
        self.assertContains(self.client.get(self.url, {'q': 'tidak-ada'}), 'Tidak ada tempat yang cocok')
        SavedPlace.objects.filter(customer=self.customer).delete()
        self.assertContains(self.client.get(self.url), 'Belum ada tempat tersimpan')

    def test_item_escapes_html_from_osm(self):
        make_saved(self.customer, make_place(9, '<script>alert(1)</script>', 'jam'))
        response = self.client.get(self.url)
        self.assertNotContains(response, '<script>alert(1)</script>')
        self.assertContains(response, '&lt;script&gt;')


class SavedCreateTests(LocationsTestCase):
    def setUp(self):
        super().setUp()
        self.customer = make_customer()
        self.place = make_place()
        self.login_customer(self.customer)
        self.url = reverse('locations:saved_create')

    def post(self, data=None, ajax=True, **extra):
        data = {'place_id': self.place.pk, 'status': 'want', **(data or {})}
        return self.client.post(self.url, data, **(AJAX if ajax else {}), **extra)

    def test_ajax_create(self):
        response = self.post({'note': '  buka   sore '})
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertTrue(body['ok'])
        saved = SavedPlace.objects.get()
        self.assertEqual((saved.customer, saved.place, saved.note), (self.customer, self.place, 'buka sore'))
        self.assertEqual(body['saved']['id'], saved.pk)
        self.assertEqual(body['saved']['delete_url'], reverse('locations:saved_delete', args=[saved.pk]))

    def test_non_ajax_create_redirects_with_message(self):
        response = self.post(ajax=False, follow=True)
        self.assertRedirects(response, reverse('locations:saved'))
        self.assertContains(response, 'Servis HP Maju disimpan.')

    def test_saving_twice_is_idempotent(self):
        self.post()
        response = self.post()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(SavedPlace.objects.count(), 1)

    def test_saving_again_after_delete_revives_with_new_data(self):
        self.post({'note': 'lama'})
        SavedPlace.objects.get().soft_delete()
        response = self.post({'note': 'baru', 'status': 'visited'})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(SavedPlace.all_objects.count(), 1)
        saved = SavedPlace.objects.get()
        self.assertEqual((saved.note, saved.status), ('baru', 'visited'))

    def test_unknown_or_bad_place_id(self):
        for value in ('9999', 'abc', ''):
            response = self.post({'place_id': value})
            self.assertEqual(response.status_code, 404, value)
        self.assertEqual(SavedPlace.objects.count(), 0)

    def test_non_ajax_error_redirects_with_message(self):
        response = self.post({'place_id': '9999'}, ajax=False, follow=True)
        self.assertContains(response, 'Tempat tidak ditemukan.')

    def test_validation_errors(self):
        response = self.post({'status': 'xx'})
        self.assertEqual(response.status_code, 400)
        self.assertIn('status', response.json()['errors'])
        response = self.post({'note': 'x' * 501})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(SavedPlace.objects.count(), 0)

    def test_get_not_allowed(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_integrity_race_returns_existing(self):
        from unittest import mock
        existing = make_saved(self.customer, self.place)
        # Simulasikan: pengecekan awal tidak melihat baris (balapan dua request).
        with mock.patch.object(SavedPlace.all_objects, 'filter',
                               return_value=SavedPlace.all_objects.none()) as patched:
            response = self.post()
        self.assertTrue(patched.called)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['saved']['id'], existing.pk)
        self.assertEqual(SavedPlace.objects.count(), 1)


class SavedEditTests(LocationsTestCase):
    def setUp(self):
        super().setUp()
        self.customer = make_customer()
        self.other = make_customer('sari')
        self.saved = make_saved(self.customer, make_place(), note='lama')
        self.url = reverse('locations:saved_edit', args=[self.saved.pk])

    def test_owner_can_view_and_update(self):
        self.login_customer(self.customer)
        self.assertContains(self.client.get(self.url), 'Servis HP Maju')
        response = self.client.post(self.url, {'note': 'baru', 'status': 'visited'}, follow=True)
        self.assertRedirects(response, reverse('locations:saved'))
        self.assertContains(response, 'Perubahan disimpan.')
        self.saved.refresh_from_db()
        self.assertEqual((self.saved.note, self.saved.status), ('baru', 'visited'))

    def test_invalid_post_shows_errors_and_changes_nothing(self):
        self.login_customer(self.customer)
        response = self.client.post(self.url, {'note': 'x' * 501, 'status': 'visited'})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].errors)
        self.saved.refresh_from_db()
        self.assertEqual(self.saved.note, 'lama')

    def test_other_customer_gets_403_and_cannot_change(self):
        self.login_customer(self.other)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        response = self.client.post(self.url, {'note': 'diretas', 'status': 'visited'})
        self.assertEqual(response.status_code, 403)
        self.saved.refresh_from_db()
        self.assertEqual(self.saved.note, 'lama')

    def test_missing_and_deleted_are_404(self):
        self.login_customer(self.customer)
        self.assertEqual(self.client.get(reverse('locations:saved_edit', args=[9999])).status_code, 404)
        self.saved.soft_delete()
        self.assertEqual(self.client.get(self.url).status_code, 404)


class SavedDeleteRestoreTests(LocationsTestCase):
    def setUp(self):
        super().setUp()
        self.customer = make_customer()
        self.other = make_customer('sari')
        self.saved = make_saved(self.customer, make_place())
        self.delete_url = reverse('locations:saved_delete', args=[self.saved.pk])
        self.restore_url = reverse('locations:saved_restore', args=[self.saved.pk])

    def test_ajax_delete_is_soft(self):
        self.login_customer(self.customer)
        response = self.client.post(self.delete_url, **AJAX)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['restore_url'], self.restore_url)
        self.assertEqual(SavedPlace.objects.count(), 0)
        self.assertEqual(SavedPlace.all_objects.count(), 1)

    def test_non_ajax_delete_redirects(self):
        self.login_customer(self.customer)
        response = self.client.post(self.delete_url, follow=True)
        self.assertRedirects(response, reverse('locations:saved'))
        self.assertContains(response, 'dihapus dari simpanan')

    def test_delete_requires_post(self):
        self.login_customer(self.customer)
        self.assertEqual(self.client.get(self.delete_url).status_code, 405)
        self.assertEqual(SavedPlace.objects.count(), 1)

    def test_other_customer_cannot_delete_or_restore(self):
        self.login_customer(self.other)
        self.assertEqual(self.client.post(self.delete_url, **AJAX).status_code, 403)
        self.assertEqual(SavedPlace.objects.count(), 1)
        self.saved.soft_delete()
        self.assertEqual(self.client.post(self.restore_url, **AJAX).status_code, 403)
        self.assertEqual(SavedPlace.objects.count(), 0)

    def test_deleting_twice_is_404(self):
        self.login_customer(self.customer)
        self.client.post(self.delete_url, **AJAX)
        self.assertEqual(self.client.post(self.delete_url, **AJAX).status_code, 404)

    def test_restore_after_delete(self):
        self.login_customer(self.customer)
        self.client.post(self.delete_url, **AJAX)
        response = self.client.post(self.restore_url, **AJAX)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(SavedPlace.objects.count(), 1)

    def test_restore_on_active_item_is_harmless(self):
        self.login_customer(self.customer)
        self.assertEqual(self.client.post(self.restore_url, **AJAX).status_code, 200)
        self.assertEqual(SavedPlace.objects.count(), 1)

    def test_restore_unknown_is_404(self):
        self.login_customer(self.customer)
        url = reverse('locations:saved_restore', args=[9999])
        self.assertEqual(self.client.post(url, **AJAX).status_code, 404)



class SaveMitraTests(LocationsTestCase):
    """Mitra bener.in (penanda hijau di peta) bisa disimpan seperti tempat OSM."""

    def setUp(self):
        super().setUp()
        self.customer = make_customer()
        self.mitra = make_mitra()
        self.login_customer(self.customer)
        self.url = reverse('locations:saved_create')

    def post(self, data=None, **extra):
        data = {'mitra_id': self.mitra.pk, 'status': 'want', **(data or {})}
        return self.client.post(self.url, data, **AJAX, **extra)

    def test_save_mitra_creates_mirror_and_saved_place(self):
        response = self.post({'note': 'dekat rumah'})
        self.assertEqual(response.status_code, 201)
        saved = SavedPlace.objects.get()
        self.assertEqual(saved.customer, self.customer)
        self.assertEqual((saved.place.osm_type, saved.place.osm_id), ('mitra', self.mitra.pk))
        self.assertEqual(saved.note, 'dekat rumah')
        self.assertEqual(response.json()['saved']['id'], saved.pk)

    def test_two_customers_share_one_mirror_row(self):
        self.post()
        self.client.logout()
        self.login_customer(make_customer('siti'))
        self.assertEqual(self.post().status_code, 201)
        self.assertEqual(SavedPlace.objects.count(), 2)
        self.assertEqual(RepairPlace.objects.filter(osm_type='mitra').count(), 1)

    def test_saving_twice_is_idempotent(self):
        self.post()
        self.assertEqual(self.post().status_code, 200)
        self.assertEqual(SavedPlace.objects.count(), 1)

    def test_unknown_bad_or_inactive_mitra_is_404_and_creates_nothing(self):
        inactive = make_mitra('tutup', active=False)
        for value in ('9999', 'abc', inactive.pk):
            self.assertEqual(self.post({'mitra_id': value}).status_code, 404, value)
        self.assertEqual(RepairPlace.objects.count(), 0)
        self.assertEqual(SavedPlace.objects.count(), 0)

    def test_invalid_form_does_not_create_mirror_row(self):
        self.assertEqual(self.post({'status': 'xx'}).status_code, 400)
        self.assertEqual(RepairPlace.objects.count(), 0)

    def test_mitra_account_cannot_save(self):
        self.client.logout()
        self.login_mitra(self.mitra)
        self.assertEqual(self.post().status_code, 403)

    def test_osm_place_id_still_works(self):
        place = make_place()
        response = self.client.post(self.url, {'place_id': place.pk, 'status': 'want'}, **AJAX)
        self.assertEqual(response.status_code, 201)

    def test_discover_separates_osm_and_mitra_ids(self):
        osm = make_place()
        make_saved(self.customer, osm)
        self.post()
        response = self.client.get(reverse('locations:discover'))
        self.assertEqual(response.context['saved_ids'], [osm.pk])
        self.assertEqual(response.context['saved_mitra_ids'], [self.mitra.pk])
        self.assertContains(response, 'id="loc-saved-mitra-ids"')

    def test_saved_list_shows_mitra_with_link_to_reviews(self):
        self.post()
        response = self.client.get(reverse('locations:saved'))
        self.assertContains(response, 'Usaha bengkel')
        self.assertContains(response, 'Mitra bener.in')
        self.assertContains(response, reverse('reviews:mitra', args=[self.mitra.pk]))
        self.assertNotContains(response, 'openstreetmap.org/mitra')

    def test_saved_mitra_can_be_deleted_and_restored(self):
        saved_id = self.post().json()['saved']['id']
        self.client.post(reverse('locations:saved_delete', args=[saved_id]), **AJAX)
        self.assertEqual(SavedPlace.objects.count(), 0)
        self.client.post(reverse('locations:saved_restore', args=[saved_id]), **AJAX)
        self.assertEqual(SavedPlace.objects.count(), 1)
