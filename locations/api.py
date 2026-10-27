"""Endpoint JSON untuk peta: proxy Overpass dan mitra terdekat."""
from django.http import JsonResponse
from django.urls import reverse
from django.views.decorators.http import require_GET

from .ratelimit import rate_limit
from .services import OverpassUnavailable, nearby_mitra, search_places


def _error(message, status):
    return JsonResponse({'ok': False, 'message': message}, status=status)


def serialize_place(place, show_contact):
    return {
        'id': place.pk,
        'name': place.name,
        'category': place.category,
        'lat': float(place.latitude),
        'lng': float(place.longitude),
        'address': place.address,
        # Kontak hanya untuk pengguna yang sudah login.
        'phone': place.phone if show_contact else '',
        'osm_url': place.osm_url,
    }


@require_GET
@rate_limit('places', limit=30, window=60)
def places_api(request):
    """Cari tempat reparasi OSM di area peta. Filter: category (wajib), q."""
    g = request.GET
    try:
        result = search_places(
            g.get('category', ''), g.get('south'), g.get('west'), g.get('north'), g.get('east'),
        )
    except ValueError as exc:
        return _error(str(exc), 400)
    except OverpassUnavailable as exc:
        return _error(str(exc), 503)

    show_contact = request.user.is_authenticated
    keyword = g.get('q', '').strip().lower()
    places = [
        p for p in result.places
        if not keyword or keyword in p.name.lower() or keyword in p.address.lower()
    ]
    return JsonResponse({
        'ok': True,
        'count': len(places),
        'cached': result.cached,
        'stale': result.stale,
        'contact_hidden': not show_contact,
        'places': [serialize_place(p, show_contact) for p in places],
    })


@require_GET
@rate_limit('mitra', limit=60, window=60)
def mitra_api(request):
    """Mitra terdaftar bener.in di sekitar titik tertentu."""
    g = request.GET
    try:
        lat, lng = float(g.get('lat')), float(g.get('lng'))
        radius = float(g.get('radius_km', 10))
        found = nearby_mitra(lat, lng, radius, category=g.get('category') or None)
    except (TypeError, ValueError) as exc:
        message = str(exc) if str(exc) and 'float' not in str(exc) else 'Koordinat atau radius tidak valid.'
        return _error(message, 400)

    show_contact = request.user.is_authenticated
    return JsonResponse({
        'ok': True,
        'count': len(found),
        'contact_hidden': not show_contact,
        'mitra': [{
            'id': m.pk,
            'name': m.nama_usaha,
            'address': m.alamat,
            'layanan': m.layanan,
            'lat': float(m.latitude),
            'lng': float(m.longitude),
            'distance_km': round(distance, 2),
            'phone': m.no_hp if show_contact else '',
            'reviews_url': reverse('reviews:mitra', args=[m.pk]),
        } for distance, m in found],
    })
