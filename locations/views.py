from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from authentication.models import KategoriBarang, MitraReparasi

from .decorators import customer_required, is_ajax
from .forms import SavedPlaceForm
from .models import MITRA_SOURCE, RepairPlace, SavedPlace
from .services import place_for_mitra


def discover(request):
    """Halaman peta pencarian. Terbuka untuk umum; menyimpan butuh login."""
    saved_ids, saved_mitra_ids = [], []
    if getattr(request.user, 'role', None) == 'customer':
        mine = SavedPlace.objects.filter(customer=request.user)
        # Tempat OSM dikenali lewat pk RepairPlace, mitra lewat pk akun mitra.
        saved_ids = list(
            mine.exclude(place__osm_type=MITRA_SOURCE).values_list('place_id', flat=True)
        )
        saved_mitra_ids = list(
            mine.filter(place__osm_type=MITRA_SOURCE).values_list('place__osm_id', flat=True)
        )
    return render(request, 'locations/discover.html', {
        'categories': KategoriBarang.choices,
        'saved_ids': saved_ids,
        'saved_mitra_ids': saved_mitra_ids,
        'is_customer': getattr(request.user, 'role', None) == 'customer',
    })


@customer_required
def saved_list(request):
    items = SavedPlace.objects.filter(customer=request.user).select_related('place')
    q = request.GET.get('q', '').strip()
    category = request.GET.get('category', '')
    status = request.GET.get('status', '')
    if q:
        items = items.filter(
            Q(place__name__icontains=q) | Q(place__address__icontains=q) | Q(note__icontains=q)
        )
    if category in KategoriBarang.values:
        items = items.filter(place__category=category)
    else:
        category = ''
    if status in SavedPlace.Status.values:
        items = items.filter(status=status)
    else:
        status = ''
    return render(request, 'locations/saved_list.html', {
        'items': items,
        'q': q,
        'category': category,
        'status': status,
        'categories': KategoriBarang.choices,
        'statuses': SavedPlace.Status.choices,
        'filtered': bool(q or category or status),
    })


def _owned_or_403(request, pk, manager=None):
    """Ambil SavedPlace milik pengguna. Milik orang lain → 403 (bukan 404),
    supaya halaman 403 bisa memberi penjelasan yang jelas."""
    manager = manager or SavedPlace.objects
    saved = get_object_or_404(manager.select_related('place'), pk=pk)
    if saved.customer_id != request.user.pk:
        raise PermissionDenied
    return saved


def _payload(saved):
    return {
        'id': saved.pk,
        'place_id': saved.place_id,
        'edit_url': reverse('locations:saved_edit', args=[saved.pk]),
        'delete_url': reverse('locations:saved_delete', args=[saved.pk]),
        'restore_url': reverse('locations:saved_restore', args=[saved.pk]),
    }


def _respond(request, ok, message, status=200, **extra):
    if is_ajax(request):
        return JsonResponse({'ok': ok, 'message': message, **extra}, status=status)
    (messages.success if ok else messages.error)(request, message)
    return redirect('locations:saved')


def _find_target(request):
    """Yang mau disimpan: `mitra_id` (mitra bener.in) atau `place_id` (tempat OSM).

    Hanya membaca database; None jika tidak ditemukan.
    """
    if request.POST.get('mitra_id'):
        try:
            return MitraReparasi.objects.get(pk=int(request.POST['mitra_id']), is_active=True)
        except (ValueError, MitraReparasi.DoesNotExist):
            return None
    try:
        return RepairPlace.objects.get(pk=int(request.POST.get('place_id', '')))
    except (ValueError, RepairPlace.DoesNotExist):
        return None


@customer_required
@require_POST
def saved_create(request):
    target = _find_target(request)
    if target is None:
        return _respond(request, False, 'Tempat tidak ditemukan.', 404)

    form = SavedPlaceForm(request.POST)
    if not form.is_valid():
        return _respond(request, False, 'Data tidak valid.', 400, errors=form.errors.get_json_data())

    # Cermin RepairPlace untuk mitra baru dibuat setelah input lolos validasi.
    place = place_for_mitra(target) if isinstance(target, MitraReparasi) else target

    existing = SavedPlace.all_objects.filter(customer=request.user, place=place).first()
    if existing and not existing.is_deleted:
        return _respond(request, True, 'Tempat ini sudah ada di daftar simpananmu.', 200,
                        saved=_payload(existing))
    try:
        with transaction.atomic():
            if existing:  # pernah dihapus: hidupkan lagi dengan data baru
                existing.note = form.cleaned_data['note']
                existing.status = form.cleaned_data['status']
                existing.deleted_at = None
                existing.save()
                saved = existing
            else:
                saved = form.save(commit=False)
                saved.customer, saved.place = request.user, place
                saved.save()
    except IntegrityError:  # dikirim dua kali bersamaan
        saved = SavedPlace.objects.get(customer=request.user, place=place)
    return _respond(request, True, f'{place.name} disimpan.', 201, saved=_payload(saved))


@customer_required
def saved_edit(request, pk):
    saved = _owned_or_403(request, pk)
    form = SavedPlaceForm(request.POST or None, instance=saved)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Perubahan disimpan.')
        return redirect('locations:saved')
    return render(request, 'locations/saved_form.html', {'form': form, 'saved': saved})


@customer_required
def toggle(request, pk):
    obj = get_object_or_404(SavedPlace, pk=pk)
    if obj.Status == 'visited'or obj.Status == 'Sudah dikunjungi':
        return obj.STATUS == 'want' or 'Ingin dikunjungi'
    else:
        return obj.STATUS == "WANT"


@customer_required
@require_POST
def saved_delete(request, pk):
    saved = _owned_or_403(request, pk)
    saved.soft_delete()
    return _respond(request, True, f'{saved.place.name} dihapus dari simpanan.', 200,
                    restore_url=reverse('locations:saved_restore', args=[saved.pk]))


@customer_required
@require_POST
def saved_restore(request, pk):
    saved = _owned_or_403(request, pk, manager=SavedPlace.all_objects)
    if saved.is_deleted:
        saved.restore()
    return _respond(request, True, f'{saved.place.name} dikembalikan.', 200)
