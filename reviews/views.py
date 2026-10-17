from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .impact import get_impact_summary


@login_required(login_url='authentication:login')
def impact_dashboard(request):
    # TODO: ganti dengan jumlah RepairRequest berstatus Completed milik user
    # setelah model Modul B (Akmal) tersedia.
    saved_count = 0

    # Hanya untuk tes tampilan saat DEBUG: /reviews/impact/?demo=7
    if settings.DEBUG and request.GET.get('demo', '').isdigit():
        saved_count = int(request.GET['demo'])

    return render(request, 'reviews/impact_dashboard.html', {
        'summary': get_impact_summary(saved_count),
    })