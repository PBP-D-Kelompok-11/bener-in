import time

from django.core.management.base import BaseCommand, CommandError

from locations.models import RepairPlace
from locations.services import CATEGORY_TAGS, OverpassUnavailable, search_places

# Area di Jabodetabek (south, west, north, east). Masing-masing < 0.6 derajat.
AREAS = {
    'Jakarta Pusat': (-6.20, 106.79, -6.14, 106.87),
    'Jakarta Selatan': (-6.31, 106.76, -6.22, 106.85),
    'Depok': (-6.43, 106.74, -6.34, 106.87),
    'Tangerang Selatan': (-6.36, 106.64, -6.25, 106.75),
    'Bekasi': (-6.30, 106.95, -6.20, 107.05),
}


class Command(BaseCommand):
    help = (
        'Isi tabel RepairPlace dengan data nyata dari OpenStreetMap (Overpass API) '
        'sampai jumlahnya minimal --min. Butuh koneksi internet.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--min', type=int, default=50, help='Jumlah minimal tempat (default 50).')
        parser.add_argument('--delay', type=float, default=1.0,
                            help='Jeda antar permintaan, detik (sopan ke server publik).')

    def handle(self, *args, **options):
        target, delay = options['min'], options['delay']
        for area, bbox in AREAS.items():
            for category in CATEGORY_TAGS:
                if RepairPlace.objects.count() >= target:
                    break
                try:
                    result = search_places(category, *bbox)
                except OverpassUnavailable:
                    self.stderr.write(f'Lewati {area}/{category}: Overpass tidak dapat dihubungi.')
                    continue
                finally:
                    time.sleep(delay)
                self.stdout.write(f'{area} / {category}: {len(result.places)} tempat')
            if RepairPlace.objects.count() >= target:
                break

        total = RepairPlace.objects.count()
        if total < target:
            raise CommandError(f'Baru {total} tempat (target {target}). Coba jalankan lagi nanti.')
        self.stdout.write(self.style.SUCCESS(f'Selesai: {total} tempat tersimpan.'))
