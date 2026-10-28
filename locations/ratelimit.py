from functools import wraps

from django.core.cache import cache
from django.http import JsonResponse


def client_key(request):
    """Pakai id pengguna kalau login, kalau tidak alamat IP."""
    if request.user.is_authenticated:
        return f'u{request.user.pk}-{request.user.role}'
    return 'ip' + request.META.get('REMOTE_ADDR', 'unknown')


def rate_limit(name, limit, window):
    """Batasi `limit` request per `window` detik per klien. Lebih → 429."""

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            key = f'ratelimit:{name}:{client_key(request)}'
            cache.add(key, 0, window)  # set awal + kadaluarsa hanya jika belum ada
            count = cache.incr(key)
            if count > limit:
                response = JsonResponse(
                    {'ok': False, 'message': 'Terlalu banyak permintaan. Coba lagi sebentar lagi.'},
                    status=429,
                )
                response['Retry-After'] = str(window)
                return response
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator
