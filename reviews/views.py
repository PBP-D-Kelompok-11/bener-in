from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render

from authentication.models import Customer
from repair.models import RepairRequest

from .impact import get_impact_summary


@login_required(login_url='authentication:login')
def impact_dashboard(request):
    if not isinstance(request.user, Customer) or request.user.role != 'customer' or not request.user.is_active:
        return HttpResponseForbidden('Hanya akun Customer yang dapat melihat Impact Tracker.')
    saved_count = RepairRequest.objects.filter(
        customer=request.user, status=RepairRequest.Status.COMPLETED,
    ).count()

    return render(request, 'reviews/impact_dashboard.html', {
        'summary': get_impact_summary(saved_count),
    })
