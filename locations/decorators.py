from functools import wraps

from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import resolve_url


def is_ajax(request):
    return request.headers.get('x-requested-with') == 'XMLHttpRequest'


def customer_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            if is_ajax(request):
                return JsonResponse({
                    'ok': False,
                    'message': 'Masuk sebagai customer dulu untuk menyimpan tempat.',
                    'login_url': resolve_url(settings.LOGIN_URL),
                }, status=401)
            return redirect_to_login(request.get_full_path())
        if getattr(request.user, 'role', None) != 'customer':
            raise PermissionDenied
        return view_func(request, *args, **kwargs)

    return wrapper
