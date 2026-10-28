from unittest import mock

from django.urls import reverse

from locations.services import AddressNotFound, GeocodeUnavailable, OverpassUnavailable

from .base import LocationsTestCase, make_customer, make_mitra

PARAMS = {'category': 'gadget', 'south': -6.25, 'west': 106.75, 'north': -6.15, 'east': 106.85}
ELEMENT = {'type': 'node', 'id': 7, 'lat': -6.2, 'lon': 106.8,
           'tags': {'name': 'Servis HP Maju', 'addr:street': 'Jl. Melati', 'phone': '021-555'}}


def overpass(elements=(ELEMENT,)):
    return mock.patch('locations.services._http_post', return_value={'elements': list(elements)})


class PlacesApiTests(LocationsTestCase):
    url = reverse('locations:api_places')

    def test_anonymous_gets_places_without_phone(self):
        with overpass():
            data = self.client.get(self.url, PARAMS).json()
        self.assertTrue(data['ok'])
        self.assertTrue(data['contact_hidden'])
        self.assertEqual(data['count'], 1)
        place = data['places'][0]
        self.assertEqual(place['name'], 'Servis HP Maju')
        self.assertEqual(place['phone'], '')
        self.assertEqual(place['osm_url'], 'https://www.openstreetmap.org/node/7')

    def test_logged_in_user_sees_phone(self):
        self.login_customer(make_customer())
        with overpass():
            data = self.client.get(self.url, PARAMS).json()
        self.assertFalse(data['contact_hidden'])
        self.assertEqual(data['places'][0]['phone'], '021-555')

    def test_mitra_login_also_sees_phone(self):
        self.login_mitra(make_mitra())
        with overpass():
            data = self.client.get(self.url, PARAMS).json()
        self.assertEqual(data['places'][0]['phone'], '021-555')

    def test_keyword_filter(self):
        other = {**ELEMENT, 'id': 8, 'tags': {'name': 'Bengkel Lain'}}
        with overpass([ELEMENT, other]):
            data = self.client.get(self.url, {**PARAMS, 'q': 'melati'}).json()  # cocok alamat
            self.assertEqual(data['count'], 1)
            data = self.client.get(self.url, {**PARAMS, 'q': 'LAIN'}).json()  # tidak peka huruf besar
            self.assertEqual([p['name'] for p in data['places']], ['Bengkel Lain'])

    def test_invalid_category_is_400(self):
        response = self.client.get(self.url, {**PARAMS, 'category': 'roket'})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()['ok'])

    def test_invalid_bbox_is_400(self):
        response = self.client.get(self.url, {**PARAMS, 'south': 'abc'})
        self.assertEqual(response.status_code, 400)

    def test_missing_params_is_400(self):
        self.assertEqual(self.client.get(self.url, {'category': 'gadget'}).status_code, 400)

    def test_overpass_down_is_503(self):
        with mock.patch('locations.api.search_places', side_effect=OverpassUnavailable('mati')):
            response = self.client.get(self.url, PARAMS)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()['message'], 'mati')

    def test_stale_flag_is_reported(self):
        with overpass():
            self.client.get(self.url, PARAMS)
        from django.core.cache import cache
        from locations import services
        fresh, _ = services._cache_keys('gadget', services.validate_bbox(*[PARAMS[k] for k in ('south', 'west', 'north', 'east')]))
        cache.delete(fresh)
        with mock.patch('locations.services._http_post', side_effect=OSError('down')):
            data = self.client.get(self.url, PARAMS).json()
        self.assertTrue(data['stale'])

    def test_post_not_allowed(self):
        self.assertEqual(self.client.post(self.url, PARAMS).status_code, 405)

    def test_rate_limit(self):
        bad = {'category': 'roket'}  # murah: tidak memanggil jaringan, tapi tetap dihitung
        codes = [self.client.get(self.url, bad).status_code for _ in range(31)]
        self.assertEqual(codes[:30], [400] * 30)
        self.assertEqual(codes[30], 429)
        last = self.client.get(self.url, bad)
        self.assertIn('Retry-After', last)


class MitraApiTests(LocationsTestCase):
    url = reverse('locations:api_mitra')

    def setUp(self):
        super().setUp()
        self.mitra = make_mitra('dekat', '-6.2010', '106.8000', layanan=['gadget'])
        make_mitra('sepeda', '-6.2020', '106.8000', layanan=['sepeda'])
        make_mitra('jauh', '-6.9000', '107.6000')

    def get(self, **params):
        return self.client.get(self.url, {'lat': -6.2, 'lng': 106.8, 'radius_km': 10, **params})

    def test_returns_nearby_sorted_with_distance(self):
        data = self.get().json()
        self.assertEqual([m['name'] for m in data['mitra']], ['Usaha dekat', 'Usaha sepeda'])
        self.assertGreater(data['mitra'][0]['distance_km'], 0)
        self.assertEqual(data['mitra'][0]['reviews_url'], f'/reviews/mitra/{self.mitra.pk}/')

    def test_category_filter(self):
        data = self.get(category='sepeda').json()
        self.assertEqual([m['name'] for m in data['mitra']], ['Usaha sepeda'])

    def test_contact_hidden_for_anonymous_and_shown_after_login(self):
        self.assertEqual(self.get().json()['mitra'][0]['phone'], '')
        self.assertTrue(self.get().json()['contact_hidden'])
        self.login_customer(make_customer())
        data = self.get().json()
        self.assertEqual(data['mitra'][0]['phone'], '0899')
        self.assertFalse(data['contact_hidden'])

    def test_default_radius(self):
        response = self.client.get(self.url, {'lat': -6.2, 'lng': 106.8})
        self.assertEqual(response.json()['count'], 2)

    def test_bad_input_is_400(self):
        self.assertEqual(self.client.get(self.url).status_code, 400)  # tanpa lat/lng
        self.assertEqual(self.get(lat='x').status_code, 400)
        self.assertEqual(self.get(radius_km=0).status_code, 400)
        self.assertEqual(self.get(radius_km=500).status_code, 400)
        self.assertEqual(self.get(category='roket').status_code, 400)
        self.assertEqual(self.get(lat=95).status_code, 400)


class ReverseApiTests(LocationsTestCase):
    url = reverse('locations:api_reverse')

    def get(self, **params):
        return self.client.get(self.url, {'lat': -6.2, 'lng': 106.8, **params})

    def test_anonymous_gets_address(self):
        with mock.patch('locations.api.reverse_geocode', return_value='Jl. Melati 5, Depok') as geocode:
            response = self.get()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'ok': True, 'address': 'Jl. Melati 5, Depok'})
        geocode.assert_called_once_with('-6.2', '106.8')

    def test_bad_coordinates_are_400(self):
        for params in ({'lat': 'abc'}, {'lat': 95}, {'lng': 'nan'}):
            response = self.get(**params)
            self.assertEqual(response.status_code, 400, params)
            self.assertFalse(response.json()['ok'])

    def test_missing_coordinates_are_400(self):
        self.assertEqual(self.client.get(self.url).status_code, 400)

    def test_no_address_is_404(self):
        with mock.patch('locations.api.reverse_geocode', side_effect=AddressNotFound('kosong')):
            response = self.get()
        self.assertEqual((response.status_code, response.json()['message']), (404, 'kosong'))

    def test_nominatim_down_is_503(self):
        with mock.patch('locations.api.reverse_geocode', side_effect=GeocodeUnavailable('mati')):
            response = self.get()
        self.assertEqual((response.status_code, response.json()['message']), (503, 'mati'))

    def test_only_get_allowed(self):
        self.assertEqual(self.client.post(self.url).status_code, 405)

    def test_rate_limited_after_20_requests_per_minute(self):
        with mock.patch('locations.api.reverse_geocode', return_value='x'):
            codes = [self.get().status_code for _ in range(21)]
        self.assertEqual(codes[:20], [200] * 20)
        self.assertEqual(codes[20], 429)
