from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.db.models import Avg, Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from authentication.models import MitraReparasi
from repair.models import RepairRequest

from .forms import ReviewForm
from .impact import get_impact_summary
from .models import Review


def customer_required(view_func):
    """Harus login dan berperan customer. Mitra mendapat 403."""

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if getattr(request.user, 'role', None) != 'customer':
            raise PermissionDenied
        return view_func(request, *args, **kwargs)

    return login_required(wrapper)


@customer_required
def impact_dashboard(request):
    saved_count = RepairRequest.objects.filter(
        customer=request.user, status=RepairRequest.Status.COMPLETED,
    ).count()
    return render(request, 'reviews/impact_dashboard.html', {
        'summary': get_impact_summary(saved_count),
    })


@customer_required
def my_reviews(request):
    reviews = Review.objects.filter(
        repair_request__customer=request.user,
    ).select_related('repair_request__mitra')
    pending = RepairRequest.objects.filter(
        customer=request.user,
        status=RepairRequest.Status.COMPLETED,
        review__isnull=True,
    ).select_related('mitra')
    return render(request, 'reviews/my_reviews.html', {
        'reviews': reviews,
        'pending': pending,
    })


@customer_required
def review_create(request, repair_id):
    repair = get_object_or_404(
        RepairRequest.objects.select_related('mitra'),
        pk=repair_id, customer=request.user,
    )
    if not repair.is_successful:
        messages.error(request, 'Review hanya bisa ditulis setelah repair berstatus Completed.')
        return redirect('reviews:mine')

    existing = Review.objects.filter(repair_request=repair).first()
    if existing:
        messages.info(request, 'Kamu sudah mengulas repair ini. Kamu bisa mengubahnya di sini.')
        return redirect('reviews:edit', pk=existing.pk)

    review = Review(repair_request=repair)
    if request.method == 'POST':
        form = ReviewForm(request.POST, instance=review)
        if form.is_valid():
            try:
                with transaction.atomic():
                    form.save()
            except IntegrityError:
                # Terkirim dua kali bersamaan: review pertama yang berlaku.
                messages.info(request, 'Review untuk repair ini sudah tersimpan.')
            else:
                messages.success(request, 'Terima kasih! Review kamu sudah tersimpan.')
            return redirect('reviews:mine')
    else:
        form = ReviewForm(instance=review)

    return render(request, 'reviews/review_form.html', {
        'form': form, 'repair': repair, 'is_edit': False,
    })


@customer_required
def review_edit(request, pk):
    review = get_object_or_404(
        Review.objects.select_related('repair_request__mitra'),
        pk=pk, repair_request__customer=request.user,
    )
    if request.method == 'POST':
        form = ReviewForm(request.POST, instance=review)
        if form.is_valid():
            form.save()
            messages.success(request, 'Review kamu sudah diperbarui.')
            return redirect('reviews:mine')
    else:
        form = ReviewForm(instance=review)

    return render(request, 'reviews/review_form.html', {
        'form': form, 'repair': review.repair_request, 'is_edit': True,
    })


@customer_required
def review_delete(request, pk):
    review = get_object_or_404(
        Review.objects.select_related('repair_request__mitra'),
        pk=pk, repair_request__customer=request.user,
    )
    if request.method == 'POST':
        repair = review.repair_request
        review.delete()
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            # Dipanggil lewat fetch dari halaman "Review saya": balas JSON.
            return JsonResponse({
                'ok': True,
                'message': 'Review kamu sudah dihapus.',
                'pending': {
                    'item': repair.item_name,
                    'mitra': repair.mitra.nama_usaha,
                    'url': reverse('reviews:create', args=[repair.pk]),
                },
            })
        messages.success(request, 'Review kamu sudah dihapus.')
        return redirect('reviews:mine')
    return render(request, 'reviews/review_confirm_delete.html', {'review': review})


@login_required
def mitra_own_reviews(request):
    """Pintasan untuk mitra: arahkan ke halaman review miliknya sendiri."""
    if getattr(request.user, 'role', None) != 'mitra':
        raise PermissionDenied
    return redirect('reviews:mitra', mitra_id=request.user.pk)


def mitra_reviews(request, mitra_id):
    """Daftar review satu mitra. Terbuka untuk semua pengunjung."""
    mitra = get_object_or_404(MitraReparasi, pk=mitra_id, is_active=True)
    reviews = Review.objects.filter(
        repair_request__mitra=mitra,
    ).select_related('repair_request__customer')
    stats = reviews.aggregate(average=Avg('rating'), total=Count('pk'))

    average = None
    average_stars = ''
    if stats['average'] is not None:
        average = round(stats['average'], 1)
        filled = round(stats['average'])
        average_stars = '★' * filled + '☆' * (5 - filled)

    return render(request, 'reviews/mitra_reviews.html', {
        'mitra': mitra,
        'reviews': reviews,
        'average': average,
        'average_stars': average_stars,
        'total': stats['total'],
    })