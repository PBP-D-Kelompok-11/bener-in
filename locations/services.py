"""Integrasi OpenStreetMap (Overpass API) dan pencarian mitra terdekat.

Pemanggilan Overpass dilakukan dari server (bukan browser) supaya:
  - hasilnya bisa di cache (mengurangi beban ke server publik Overpass),
  - kalo server utama mati, coba mirror lalu data lama (stale),
  - hasilnya tersimpan di tabel RepairPlace jadi bisa disimpan pengguna.
"""
import json
import math
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

from django.conf import settings
from django.core.cache import cache

from authentication.models import KategoriBarang, MitraReparasi
from .models import MITRA_SOURCE, RepairPlace

CATEGORY_TAGS = {
    'gadget': [('shop', 'mobile_phone'), ('shop', 'computer'), ('craft', 'electronics_repair'), ('shop', 'electronics_repair')],
    'elektronik': [('craft', 'electronics_repair'), ('shop', 'electronics_repair'), ('shop', 'appliance'), ('craft', 'electrician')],
    'mobil': [('shop', 'car_repair')],
    'motor': [('shop', 'motorcycle_repair'), ('shop', 'motorcycle')],
    'sepeda': [('shop', 'bicycle')],
    'furnitur': [('craft', 'carpenter'), ('craft', 'upholsterer'), ('shop', 'furniture')],
    'sepatu': [('craft', 'shoemaker'), ('shop', 'shoe_repair')],
    'pakaian': [('craft', 'tailor'), ('shop', 'tailor')],
    'jam': [('craft', 'watchmaker')],
    'perhiasan': [('craft', 'jeweller')],
    'lainnya': [('shop', 'repair')],
}

DEFAULT_ENDPOINTS = (
    'https://overpass-api.de/api/interpreter',
    'https://overpass.kumi.systems/api/interpreter',
)
MAX_BBOX_SPAN = 0.6      # derajat; mencegah query satu negara sekaligus
MAX_RESULTS = 100
HTTP_TIMEOUT = 25        # detik
CACHE_TTL = 60 * 60      # hasil segar: 1 jam
STALE_TTL = 60 * 60 * 24 * 7  # cadangan kalau Overpass mati: 7 hari
USER_AGENT = 'bener.in-student-project/1.0 (PBP UI)'

NOMINATIM_URL = 'https://nominatim.openstreetmap.org/reverse'
REVERSE_TIMEOUT = 10             # detik
REVERSE_TTL = 60 * 60 * 24 * 7   # alamat suatu titik jarang berubah: 7 hari


class OverpassUnavailable(Exception):
    """Semua endpoint Overpass gagal dan tidak ada data cadangan."""


class GeocodeUnavailable(Exception):
    """Nominatim tidak dapat dihubungi dan titik ini belum ada di cache."""


class AddressNotFound(Exception):
    """Nominatim tidak menemukan alamat untuk titik ini (mis. di laut)."""


@dataclass
class SearchResult:
    places: list = field(default_factory=list)
    cached: bool = False
    stale: bool = False


def validate_bbox(south, west, north, east):
    try:
        south, west, north, east = (float(v) for v in (south, west, north, east))
    except (TypeError, ValueError):
        raise ValueError('Batas peta harus berupa angka.')
    if not all(math.isfinite(v) for v in (south, west, north, east)):
        raise ValueError('Batas peta harus berupa angka.')
    if not (-90 <= south < north <= 90 and -180 <= west < east <= 180):
        raise ValueError('Batas peta tidak valid.')
    if (north - south) > MAX_BBOX_SPAN or (east - west) > MAX_BBOX_SPAN:
        raise ValueError('Area terlalu luas. Perbesar peta lalu coba lagi.')
    return south, west, north, east


def build_query(category, bbox):
    south, west, north, east = bbox
    box = f'({south},{west},{north},{east})'
    parts = ''.join(f'nwr["{k}"="{v}"]{box};' for k, v in CATEGORY_TAGS[category])
    return f'[out:json][timeout:25];({parts});out center {MAX_RESULTS};'


def _http_post(url, query):
    """Satu-satunya titik yang menyentuh jaringan"""
    request = urllib.request.Request(
        url,
        data=urllib.parse.urlencode({'data': query}).encode(),
        headers={'User-Agent': USER_AGENT},
    )
    with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response:
        return json.loads(response.read().decode('utf-8'))


def _query_overpass(category, bbox):
    endpoints = getattr(settings, 'OVERPASS_ENDPOINTS', DEFAULT_ENDPOINTS)
    query = build_query(category, bbox)
    for url in endpoints:
        try:
            data = _http_post(url, query)
        except (urllib.error.URLError, OSError, ValueError):
            continue  # coba mirror berikutnya
        if isinstance(data, dict) and isinstance(data.get('elements'), list):
            return data['elements']
    raise OverpassUnavailable('Server OpenStreetMap sedang tidak dapat dihubungi.')


def _clip(value, length):
    return (value or '')[:length]


def element_to_fields(element):
    """Ubah satu elemen Overpass menjadi dict field RepairPlace, atau None."""
    lat = element.get('lat', (element.get('center') or {}).get('lat'))
    lon = element.get('lon', (element.get('center') or {}).get('lon'))
    osm_type, osm_id = element.get('type'), element.get('id')
    if osm_type not in ('node', 'way', 'relation') or osm_id is None:
        return None
    if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
        return None
    tags = element.get('tags') or {}
    address = ' '.join(filter(None, [tags.get('addr:street'), tags.get('addr:housenumber')]))
    if tags.get('addr:city'):
        address = f"{address}, {tags['addr:city']}" if address else tags['addr:city']
    return {
        'osm_type': osm_type,
        'osm_id': osm_id,
        'name': _clip(tags.get('name'), 255) or 'Tempat tanpa nama',
        'latitude': round(lat, 6),
        'longitude': round(lon, 6),
        'address': _clip(address, 255),
        'phone': _clip(tags.get('phone') or tags.get('contact:phone'), 60),
    }


def save_elements(category, elements):
    """Simpan elemen Overpass ke RepairPlace. Kategori awal tidak ditimpa."""
    places = []
    for element in elements:
        fields = element_to_fields(element)
        if fields is None:
            continue
        key = {'osm_type': fields.pop('osm_type'), 'osm_id': fields.pop('osm_id')}
        place, created = RepairPlace.objects.get_or_create(
            **key, defaults={**fields, 'category': category},
        )
        if not created:
            for name, value in fields.items():
                setattr(place, name, value)
            place.save()
        places.append(place)
    return places


def _cache_keys(category, bbox):
    # Dibulatkan 2 desimal (~1 km) supaya geseran kecil memakai cache yang sama.
    coords = ':'.join(f'{v:.2f}' for v in bbox)
    return f'overpass:{category}:{coords}', f'overpass-stale:{category}:{coords}'


def _places_from_pks(pks):
    return list(RepairPlace.objects.filter(pk__in=pks))


def search_places(category, south, west, north, east):
    if category not in CATEGORY_TAGS:
        raise ValueError('Kategori tidak dikenal.')
    bbox = validate_bbox(south, west, north, east)
    fresh_key, stale_key = _cache_keys(category, bbox)

    pks = cache.get(fresh_key)
    if pks is not None:
        return SearchResult(_places_from_pks(pks), cached=True)

    try:
        elements = _query_overpass(category, bbox)
    except OverpassUnavailable:
        stale = cache.get(stale_key)
        if stale is None:
            raise
        return SearchResult(_places_from_pks(stale), cached=True, stale=True)

    places = save_elements(category, elements)
    pks = [p.pk for p in places]
    cache.set(fresh_key, pks, CACHE_TTL)
    cache.set(stale_key, pks, STALE_TTL)
    return SearchResult(places)


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi, dlmb = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def nearby_mitra(lat, lng, radius_km, category=None, limit=50):
    """Mitra terdaftar bener.in dalam radius tertentu, terdekat lebih dulu."""
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        raise ValueError('Koordinat tidak valid.')
    if not (0 < radius_km <= 100):
        raise ValueError('Radius harus antara 0 dan 100 km.')
    if category is not None and category not in CATEGORY_TAGS:
        raise ValueError('Kategori tidak dikenal.')
    found = []
    for mitra in MitraReparasi.objects.filter(is_active=True):
        if category and category not in (mitra.layanan or []):
            continue
        distance = haversine_km(lat, lng, float(mitra.latitude), float(mitra.longitude))
        if distance <= radius_km:
            found.append((distance, mitra))
    found.sort(key=lambda pair: pair[0])
    return found[:limit]


def place_for_mitra(mitra):
    """RepairPlace "cermin" untuk mitra bener.in, dibuat/diperbarui saat disimpan.

    Dengan begitu mitra bisa masuk ke daftar tempat tersimpan lewat SavedPlace
    yang sama seperti tempat OSM. Datanya disalin ulang setiap kali ada yang
    menyimpan, jadi tidak tertinggal jauh dari profil mitra. Kategori dipilih
    tetap (layanan pertama yang valid) karena baris ini dipakai bersama semua
    customer.
    """
    category = next((c for c in (mitra.layanan or []) if c in KategoriBarang.values),
                    KategoriBarang.LAINNYA.value)
    place, _ = RepairPlace.objects.update_or_create(
        osm_type=MITRA_SOURCE, osm_id=mitra.pk,
        defaults={
            'name': _clip(mitra.nama_usaha, 255) or 'Mitra bener.in',
            'category': category,
            'latitude': mitra.latitude,
            'longitude': mitra.longitude,
            'address': _clip(' '.join((mitra.alamat or '').split()), 255),
            'phone': _clip(mitra.no_hp, 60),
        },
    )
    return place


def _first(address, *keys):
    return next((address[k] for k in keys if address.get(k)), '')


def format_address(data):
    """Susun alamat ringkas dari jawaban Nominatim (tanpa negara)."""
    address = data.get('address') or {}
    street = ' '.join(filter(None, [
        _first(address, 'road', 'pedestrian', 'footway', 'path'),
        address.get('house_number'),
    ]))
    parts = [
        street,
        _first(address, 'neighbourhood', 'quarter', 'hamlet'),
        _first(address, 'suburb', 'village'),
        _first(address, 'city_district', 'subdistrict'),
        _first(address, 'city', 'town', 'municipality', 'county'),
        _first(address, 'state'),
        _first(address, 'postcode'),
    ]
    seen, ordered = set(), []
    for part in (p.strip() for p in parts):
        if part and part.lower() not in seen:
            seen.add(part.lower())
            ordered.append(part)
    return _clip(', '.join(ordered) or data.get('display_name'), 500)


def _http_get_json(url):
    """Satu-satunya titik reverse geocoding yang menyentuh jaringan."""
    request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(request, timeout=REVERSE_TIMEOUT) as response:
        return json.loads(response.read().decode('utf-8'))


def reverse_geocode(lat, lng):
    """Alamat teks untuk sebuah titik peta (Nominatim, di-cache per ~11 m)."""
    try:
        lat, lng = float(lat), float(lng)
    except (TypeError, ValueError):
        raise ValueError('Koordinat tidak valid.')
    if not (math.isfinite(lat) and math.isfinite(lng)
            and -90 <= lat <= 90 and -180 <= lng <= 180):
        raise ValueError('Koordinat tidak valid.')

    key = f'reverse:{lat:.4f}:{lng:.4f}'
    address = cache.get(key)
    if address is not None:
        return address

    query = urllib.parse.urlencode({
        'format': 'jsonv2', 'lat': f'{lat:.6f}', 'lon': f'{lng:.6f}',
        'zoom': 18, 'addressdetails': 1, 'accept-language': 'id',
    })
    try:
        data = _http_get_json(f'{NOMINATIM_URL}?{query}')
    except (urllib.error.URLError, OSError, ValueError):
        raise GeocodeUnavailable('Layanan alamat OpenStreetMap sedang tidak dapat dihubungi.')
    if not isinstance(data, dict) or data.get('error'):
        raise AddressNotFound('Tidak ada alamat di titik ini.')
    address = format_address(data)
    if not address:
        raise AddressNotFound('Tidak ada alamat di titik ini.')
    cache.set(key, address, REVERSE_TTL)
    return address
