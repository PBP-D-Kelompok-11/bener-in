from io import StringIO
from unittest import mock

from django.core.management import CommandError, call_command

from locations.models import RepairPlace
from locations.services import OverpassUnavailable, SearchResult

from .base import LocationsTestCase

TARGET = 'locations.management.commands.seed_repair_places.search_places'


def run(**options):
    out, err = StringIO(), StringIO()
    call_command('seed_repair_places', delay=0, stdout=out, stderr=err, **options)
    return out.getvalue(), err.getvalue()


class SeedCommandTests(LocationsTestCase):
    def test_stops_once_minimum_is_reached(self):
        counter = iter(range(1, 1000))

        def fake(category, *bbox):
            places = [RepairPlace.objects.create(
                osm_type='node', osm_id=next(counter), name='T', category=category,
                latitude='-6.2', longitude='106.8') for _ in range(20)]
            return SearchResult(places)

        with mock.patch(TARGET, side_effect=fake) as search:
            out, _ = run(min=50)
        self.assertEqual(search.call_count, 3)  # 20 + 20 + 20 >= 50
        self.assertIn('Selesai: 60 tempat', out)

    def test_already_seeded_does_nothing(self):
        for i in range(3):
            RepairPlace.objects.create(osm_type='node', osm_id=i, name='T', category='jam',
                                       latitude='-6.2', longitude='106.8')
        with mock.patch(TARGET) as search:
            out, _ = run(min=3)
        search.assert_not_called()
        self.assertIn('Selesai: 3 tempat', out)

    def test_fails_when_target_not_reached(self):
        with mock.patch(TARGET, return_value=SearchResult([])):
            with self.assertRaisesMessage(CommandError, 'Baru 0 tempat'):
                run(min=5)

    def test_skips_areas_when_overpass_is_down(self):
        with mock.patch(TARGET, side_effect=OverpassUnavailable('mati')):
            with self.assertRaises(CommandError):
                out = StringIO()
                err = StringIO()
                call_command('seed_repair_places', min=1, delay=0, stdout=out, stderr=err)
        # tidak crash walau semua gagal; pesan dilewati ditulis ke stderr
        self.assertIn('Lewati', err.getvalue())
