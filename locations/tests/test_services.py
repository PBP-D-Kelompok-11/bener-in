import json
import urllib.error
from unittest import mock

from django.core.cache import cache
from django.test import SimpleTestCase

from locations import services
from locations.models import RepairPlace
from locations.services import OverpassUnavailable

from .base import LocationsTestCase, make_mitra, make_place

BBOX = (-6.25, 106.75, -6.15, 106.85)


def node(osm_id=1, name='Servis HP Maju', **tags):
    return {'type': 'node', 'id': osm_id, 'lat': -6.2, 'lon': 106.8,
            'tags': {'name': name, **tags}}


class ValidateBboxTests(SimpleTestCase):
    def test_valid(self):
        self.assertEqual(services.validate_bbox(*BBOX), BBOX)

    def test_accepts_numeric_strings(self):
        self.assertEqual(services.validate_bbox('-6.25', '106.75', '-6.15', '106.85'), BBOX)

    def test_rejects_non_numbers(self):
        for bad in (None, 'abc', ''):
            with self.assertRaises(ValueError):
                services.validate_bbox(bad, 106.75, -6.15, 106.85)

    def test_rejects_nan_and_inf(self):
        with self.assertRaises(ValueError):
            services.validate_bbox('nan', 106.75, -6.15, 106.85)
        with self.assertRaises(ValueError):
            services.validate_bbox(-6.25, 106.75, 'inf', 106.85)

    def test_rejects_inverted_or_out_of_range(self):
        with self.assertRaises(ValueError):
            services.validate_bbox(-6.15, 106.75, -6.25, 106.85)
        with self.assertRaises(ValueError):
            services.validate_bbox(-91, 0, 0, 1)

    def test_rejects_too_large_area(self):
        with self.assertRaises(ValueError):
            services.validate_bbox(-7, 106, -6, 107)


class BuildQueryTests(SimpleTestCase):
    def test_contains_tags_and_bbox(self):
        query = services.build_query('sepeda', BBOX)
        self.assertIn('nwr["shop"="bicycle"](-6.25,106.75,-6.15,106.85);', query)
        self.assertIn('out center 100;', query)

    def test_category_keys_match_kategori_barang(self):
        from authentication.models import KategoriBarang
        self.assertEqual(set(services.CATEGORY_TAGS), set(KategoriBarang.values))


class ElementToFieldsTests(SimpleTestCase):
    def test_node(self):
        fields = services.element_to_fields(node(**{'addr:street': 'Jl. A', 'addr:housenumber': '9',
                                                    'addr:city': 'Depok', 'phone': '021-1'}))
        self.assertEqual(fields['address'], 'Jl. A 9, Depok')
        self.assertEqual(fields['phone'], '021-1')
        self.assertEqual((fields['latitude'], fields['longitude']), (-6.2, 106.8))

    def test_way_uses_center(self):
        el = {'type': 'way', 'id': 5, 'center': {'lat': -6.3, 'lon': 106.9}, 'tags': {'name': 'X'}}
        self.assertEqual(services.element_to_fields(el)['latitude'], -6.3)

    def test_city_only_address_and_contact_phone(self):
        fields = services.element_to_fields(node(**{'addr:city': 'Bekasi', 'contact:phone': '08'}))
        self.assertEqual(fields['address'], 'Bekasi')
        self.assertEqual(fields['phone'], '08')

    def test_missing_name_gets_placeholder(self):
        el = {'type': 'node', 'id': 1, 'lat': 1, 'lon': 1}
        self.assertEqual(services.element_to_fields(el)['name'], 'Tempat tanpa nama')

    def test_skips_invalid_elements(self):
        self.assertIsNone(services.element_to_fields({'type': 'node', 'id': 1}))  # tanpa koordinat
        self.assertIsNone(services.element_to_fields({'type': 'area', 'id': 1, 'lat': 1, 'lon': 1}))
        self.assertIsNone(services.element_to_fields({'type': 'node', 'lat': 1, 'lon': 1}))

    def test_long_values_are_clipped(self):
        fields = services.element_to_fields(node(name='n' * 400, phone='9' * 200))
        self.assertEqual(len(fields['name']), 255)
        self.assertEqual(len(fields['phone']), 60)


class HttpPostTests(SimpleTestCase):
    def test_parses_json_response(self):
        response = mock.MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps({'elements': []}).encode()
        with mock.patch('locations.services.urllib.request.urlopen', return_value=response) as urlopen:
            data = services._http_post('https://example.test/api', 'QUERY')
        self.assertEqual(data, {'elements': []})
        request = urlopen.call_args.args[0]
        self.assertIn(b'data=QUERY', request.data)
        self.assertIn('bener.in', request.get_header('User-agent'))


class SearchPlacesTests(LocationsTestCase):
    def search(self, category='gadget'):
        return services.search_places(category, *BBOX)

    def test_unknown_category(self):
        with self.assertRaises(ValueError):
            self.search('roket')

    def test_success_saves_places(self):
        with mock.patch('locations.services._http_post', return_value={'elements': [node(1), node(2, 'B')]}):
            result = self.search()
        self.assertEqual(len(result.places), 2)
        self.assertFalse(result.cached)
        self.assertEqual(RepairPlace.objects.count(), 2)
        self.assertEqual(RepairPlace.objects.get(osm_id=1).category, 'gadget')

    def test_second_call_is_served_from_cache(self):
        with mock.patch('locations.services._http_post', return_value={'elements': [node(1)]}) as post:
            self.search()
            result = self.search()
        self.assertEqual(post.call_count, 1)
        self.assertTrue(result.cached)
        self.assertFalse(result.stale)
        self.assertEqual(len(result.places), 1)

    def test_falls_back_to_mirror(self):
        responses = [urllib.error.URLError('down'), {'elements': [node(1)]}]
        with mock.patch('locations.services._http_post', side_effect=responses) as post:
            result = self.search()
        self.assertEqual(post.call_count, 2)
        self.assertEqual(len(result.places), 1)

    def test_timeout_and_bad_json_also_fall_back(self):
        responses = [TimeoutError(), ValueError('bad json')]
        with mock.patch('locations.services._http_post', side_effect=responses):
            with self.assertRaises(OverpassUnavailable):
                self.search()

    def test_unexpected_payload_counts_as_failure(self):
        with mock.patch('locations.services._http_post', return_value={'remark': 'runtime error'}):
            with self.assertRaises(OverpassUnavailable):
                self.search()

    def test_all_endpoints_down_without_cache_raises(self):
        with mock.patch('locations.services._http_post', side_effect=urllib.error.URLError('down')):
            with self.assertRaises(OverpassUnavailable):
                self.search()

    def test_all_endpoints_down_serves_stale_copy(self):
        with mock.patch('locations.services._http_post', return_value={'elements': [node(1)]}):
            self.search()
        fresh_key, _ = services._cache_keys('gadget', BBOX)
        cache.delete(fresh_key)  # cache segar kedaluwarsa, cadangan masih ada
        with mock.patch('locations.services._http_post', side_effect=urllib.error.URLError('down')):
            result = self.search()
        self.assertTrue(result.stale)
        self.assertEqual(len(result.places), 1)

    def test_custom_endpoints_from_settings(self):
        with self.settings(OVERPASS_ENDPOINTS=('https://only.test/api',)):
            with mock.patch('locations.services._http_post', return_value={'elements': []}) as post:
                self.search()
        self.assertEqual(post.call_args.args[0], 'https://only.test/api')

    def test_existing_place_updates_fields_but_keeps_category(self):
        with mock.patch('locations.services._http_post', return_value={'elements': [node(1, 'Nama Lama')]}):
            self.search('gadget')
        cache.clear()
        with mock.patch('locations.services._http_post', return_value={'elements': [node(1, 'Nama Baru')]}):
            self.search('elektronik')
        place = RepairPlace.objects.get(osm_id=1)
        self.assertEqual(place.name, 'Nama Baru')
        self.assertEqual(place.category, 'gadget')
        self.assertEqual(RepairPlace.objects.count(), 1)

    def test_invalid_elements_are_skipped(self):
        elements = [node(1), {'type': 'node', 'id': 9}]
        with mock.patch('locations.services._http_post', return_value={'elements': elements}):
            self.assertEqual(len(self.search().places), 1)


class DistanceTests(SimpleTestCase):
    def test_haversine_known_distance(self):
        # Monas ke Bundaran HI: sekitar 2,2 km.
        km = services.haversine_km(-6.1754, 106.8272, -6.1951, 106.8230)
        self.assertTrue(2.0 < km < 2.4, km)

    def test_zero_distance(self):
        self.assertAlmostEqual(services.haversine_km(1, 1, 1, 1), 0)


class NearbyMitraTests(LocationsTestCase):
    def test_orders_by_distance_and_filters_radius(self):
        make_mitra('dekat', '-6.2000', '106.8000')
        make_mitra('sedang', '-6.2300', '106.8000')
        make_mitra('jauh', '-6.9000', '107.6000')
        found = services.nearby_mitra(-6.2, 106.8, 10)
        self.assertEqual([m.username for _, m in found], ['dekat', 'sedang'])
        self.assertLess(found[0][0], found[1][0])

    def test_category_filter(self):
        make_mitra('hp', layanan=['gadget'])
        make_mitra('sepeda', layanan=['sepeda'])
        found = services.nearby_mitra(-6.2, 106.8, 10, category='sepeda')
        self.assertEqual([m.username for _, m in found], ['sepeda'])

    def test_inactive_mitra_excluded(self):
        make_mitra('off', active=False)
        self.assertEqual(services.nearby_mitra(-6.2, 106.8, 10), [])

    def test_limit(self):
        for i in range(3):
            make_mitra(f'm{i}')
        self.assertEqual(len(services.nearby_mitra(-6.2, 106.8, 10, limit=2)), 2)

    def test_invalid_input(self):
        for args, kwargs in [((95, 0, 10), {}), ((0, 0, 0), {}), ((0, 0, 101), {}),
                             ((0, 0, 5), {'category': 'roket'})]:
            with self.assertRaises(ValueError):
                services.nearby_mitra(*args, **kwargs)
