from uuid import uuid4

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import OuterRef, Subquery
from django.http import HttpResponseForbidden, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render

from authentication.models import Customer, KategoriBarang, MitraReparasi

from .forms import RepairRequestCreateForm, RepairRequestEditForm
from .models import RepairRequest, RepairStatusHistory


TOKEN_SALT = 'repair-request-create'
TOKEN_MAX_AGE = 60 * 60 * 6


def _new_token(customer):
    return signing.dumps(
        {'customer_id': customer.pk, 'nonce': uuid4().hex}, salt=TOKEN_SALT,
    )


def _valid_token(token, customer):
    try:
        value = signing.loads(token, salt=TOKEN_SALT, max_age=TOKEN_MAX_AGE)
    except (signing.BadSignature, signing.SignatureExpired):
        return False
    return isinstance(value, dict) and value.get('customer_id') == customer.pk and isinstance(value.get('nonce'), str)


def _partner_cards(category, selected_id):
    category_labels = dict(KategoriBarang.choices)
    matching, others = [], []
    for mitra in MitraReparasi.objects.filter(is_active=True).order_by('nama_usaha', 'pk'):
        services = mitra.layanan if isinstance(mitra.layanan, list) else []
        service_keys = [key for key in services if isinstance(key, str) and key in category_labels]
        card = {
            'pk': mitra.pk,
            'name': mitra.nama_usaha,
            'address': mitra.alamat,
            'services': [category_labels[key] for key in service_keys],
            'service_keys': service_keys,
            'selected': str(mitra.pk) == str(selected_id),
        }
        (matching if category in service_keys else others).append(card)
    return matching, others


def _render_create(request, form, token, *, preview=False):
    category = form['category'].value()
    selected_id = form['mitra'].value()
    matching, others = _partner_cards(category, selected_id)
    selected_partner = next(
        (card['name'] for card in matching + others if card['selected']), None,
    )
    first_error_step = 0
    for field, step in (
        ('category', 0), ('mitra', 1), ('item_name', 2),
        ('description', 2), ('__all__', 3),
    ):
        if field in form.errors:
            first_error_step = step
            break
    return render(request, 'repair/request_create.html', {
        'form': form,
        'token': token,
        'matching_partners': matching,
        'other_partners': others,
        'has_partners': bool(matching or others),
        'preview': preview,
        'first_error_step': first_error_step,
        'displayed_category': category or '',
        'summary': {
            'category': dict(KategoriBarang.choices).get(category),
            'mitra': selected_partner,
            'item_name': form['item_name'].value(),
            'description': form['description'].value(),
        },
    })


def _customer_allowed(request):
    return isinstance(request.user, Customer) and request.user.role == 'customer' and request.user.is_active


def _mitra_allowed(request):
    return isinstance(request.user, MitraReparasi) and request.user.role == 'mitra' and request.user.is_active


STATUS_GUIDANCE = {
    RepairRequest.Status.PENDING: 'Permintaan sedang menunggu tanggapan mitra.',
    RepairRequest.Status.ACCEPTED: 'Mitra telah menerima permintaan ini.',
    RepairRequest.Status.IN_PROGRESS: 'Barang sedang dalam proses reparasi.',
    RepairRequest.Status.COMPLETED: 'Reparasi telah selesai.',
    RepairRequest.Status.REJECTED: 'Mitra menolak permintaan ini. Lihat alasannya di riwayat status.',
    RepairRequest.Status.CANCELLED: 'Permintaan ini telah dibatalkan oleh pelanggan.',
    RepairRequest.Status.UNABLE_TO_REPAIR: 'Mitra tidak dapat menyelesaikan reparasi. Lihat alasannya di riwayat status.',
}


@login_required
def request_list(request):
    if not _customer_allowed(request):
        return HttpResponseForbidden('Hanya akun Customer yang dapat melihat daftar permintaan.')
    if request.method != 'GET':
        return HttpResponseNotAllowed(['GET'])

    status_filter = request.GET.get('status', 'all')
    if status_filter not in RepairRequest.Status.values:
        status_filter = 'all'
    owned = RepairRequest.objects.filter(customer=request.user)
    latest_event = RepairStatusHistory.objects.filter(
        request_id=OuterRef('pk'),
    ).order_by('-pk')
    repairs = owned.select_related('mitra').annotate(
        last_status_at=Subquery(latest_event.values('occurred_at')[:1]),
    )
    if status_filter != 'all':
        repairs = repairs.filter(status=status_filter)
    repairs = repairs.order_by('-created_at', '-pk')
    filters = [{'value': 'all', 'label': 'Semua'}] + [
        {'value': value, 'label': label}
        for value, label in RepairRequest.Status.choices
    ]
    return render(request, 'repair/request_list.html', {
        'repairs': repairs,
        'has_any_requests': owned.exists(),
        'status_filter': status_filter,
        'filters': filters,
        'selected_filter_label': next(
            item['label'] for item in filters if item['value'] == status_filter
        ),
    })


@login_required
def request_detail(request, pk):
    if request.method != 'GET':
        return HttpResponseNotAllowed(['GET'])
    if _customer_allowed(request):
        repairs = RepairRequest.objects.filter(customer=request.user)
        viewer_is_customer = True
    elif _mitra_allowed(request):
        repairs = RepairRequest.objects.filter(mitra=request.user)
        viewer_is_customer = False
    else:
        return HttpResponseForbidden('Akun ini tidak dapat melihat permintaan reparasi.')

    repair = get_object_or_404(
        repairs.select_related('customer', 'mitra'), pk=pk,
    )
    history = list(repair.status_history.select_related(
        'customer_actor', 'mitra_actor',
    ).order_by('occurred_at', 'pk'))
    for event in history:
        if event.customer_actor_id:
            event.actor_label = 'Anda' if viewer_is_customer else event.customer_actor.nama_lengkap
        elif event.mitra_actor_id:
            event.actor_label = event.mitra_actor.nama_usaha if viewer_is_customer else 'Anda'
        else:
            event.actor_label = 'Tidak diketahui'
    latest_event = max(history, key=lambda event: event.pk, default=None)
    return render(request, 'repair/request_detail.html', {
        'repair': repair,
        'history': history,
        'latest_event': latest_event,
        'viewer_is_customer': viewer_is_customer,
        'can_manage': viewer_is_customer and repair.status == RepairRequest.Status.PENDING,
        'status_guidance': STATUS_GUIDANCE.get(repair.status, ''),
    })


@login_required
def edit_request(request, pk):
    if not _customer_allowed(request):
        return HttpResponseForbidden('Hanya pemilik permintaan yang dapat mengedit.')
    if request.method not in ('GET', 'POST'):
        return HttpResponseNotAllowed(['GET', 'POST'])
    repair = get_object_or_404(
        RepairRequest.objects.select_related('mitra'), pk=pk, customer=request.user,
    )
    if repair.status != RepairRequest.Status.PENDING:
        if request.method == 'POST':
            messages.error(request, 'Status permintaan telah berubah. Detail tidak dapat diedit lagi.')
            return redirect('repair:detail', pk=repair.pk)
        return HttpResponseForbidden('Hanya permintaan Pending yang dapat diedit.')

    form = RepairRequestEditForm(request.POST or None, instance=repair)
    if request.method == 'POST' and form.is_valid():
        try:
            form.save()
        except ValidationError as error:
            repair.refresh_from_db()
            if repair.status != RepairRequest.Status.PENDING:
                messages.error(request, 'Status permintaan berubah saat disimpan. Detail tidak diubah.')
                return redirect('repair:detail', pk=repair.pk)
            if hasattr(error, 'message_dict'):
                for field, errors in error.message_dict.items():
                    form.add_error(field if field in form.fields else None, errors)
            else:
                form.add_error(None, error)
        else:
            messages.success(request, 'Detail permintaan berhasil diperbarui.')
            return redirect('repair:detail', pk=repair.pk)
    return render(request, 'repair/request_edit.html', {'repair': repair, 'form': form})


@login_required
def cancel_request(request, pk):
    if not _customer_allowed(request):
        return HttpResponseForbidden('Hanya pemilik permintaan yang dapat membatalkan.')
    if request.method not in ('GET', 'POST'):
        return HttpResponseNotAllowed(['GET', 'POST'])
    repair = get_object_or_404(
        RepairRequest.objects.select_related('mitra'), pk=pk, customer=request.user,
    )
    if repair.status != RepairRequest.Status.PENDING:
        if request.method == 'POST':
            messages.error(request, 'Status permintaan telah berubah. Pembatalan tidak dapat dilakukan.')
            return redirect('repair:detail', pk=repair.pk)
        return HttpResponseForbidden('Hanya permintaan Pending yang dapat dibatalkan.')
    if request.method == 'POST':
        try:
            repair.transition_to(RepairRequest.Status.CANCELLED, request.user)
        except ValidationError:
            messages.error(request, 'Status permintaan berubah saat dibatalkan. Muat ulang detail permintaan.')
        else:
            messages.success(request, 'Permintaan berhasil dibatalkan. Riwayatnya tetap tersimpan.')
        return redirect('repair:detail', pk=repair.pk)
    return render(request, 'repair/request_cancel.html', {'repair': repair})


@login_required
def create_request(request):
    if not _customer_allowed(request):
        return HttpResponseForbidden('Hanya akun Customer yang dapat membuat permintaan reparasi.')

    if request.method == 'POST':
        data = request.POST.copy()
        if data.get('displayed_category') and data['displayed_category'] != data.get('category'):
            data['mitra'] = ''
        token = request.POST.get('submission_token', '')
        token_valid = _valid_token(token, request.user)
        if token_valid:
            existing = RepairRequest.objects.filter(
                customer=request.user, submission_token=token,
            ).first()
            if existing:
                return redirect('repair:confirmation', pk=existing.pk)

        action = request.POST.get('action')
        if action == 'refresh_partners':
            form = RepairRequestCreateForm(initial={
                name: data.get(name, '')
                for name in ('category', 'mitra', 'item_name', 'description')
            })
            if not token_valid:
                form.add_error(None, 'Formulir tidak valid atau sudah kedaluwarsa. Periksa kembali isian Anda.')
                token = _new_token(request.user)
            return _render_create(request, form, token)

        form = RepairRequestCreateForm(data)
        form_valid = form.is_valid()
        if not token_valid:
            form.add_error(None, 'Formulir tidak valid atau sudah kedaluwarsa. Periksa kembali isian Anda.')
            token = _new_token(request.user)

        if form_valid and token_valid:
            if action == 'preview':
                return _render_create(request, form, token, preview=True)
            repair = form.save(commit=False)
            repair.customer = request.user
            repair.submission_token = token
            try:
                repair.save()
            except IntegrityError:
                existing = RepairRequest.objects.filter(
                    customer=request.user, submission_token=token,
                ).first()
                if existing:
                    return redirect('repair:confirmation', pk=existing.pk)
                raise
            except ValidationError as error:
                existing = RepairRequest.objects.filter(
                    customer=request.user, submission_token=token,
                ).first()
                if existing:
                    return redirect('repair:confirmation', pk=existing.pk)
                if hasattr(error, 'message_dict'):
                    for field, messages in error.message_dict.items():
                        form.add_error(field if field in form.fields else None, messages)
                else:
                    form.add_error(None, error)
            else:
                return redirect('repair:confirmation', pk=repair.pk)
        return _render_create(request, form, token)

    return _render_create(
        request, RepairRequestCreateForm(), _new_token(request.user),
    )


@login_required
def request_confirmation(request, pk):
    if not _customer_allowed(request):
        return HttpResponseForbidden('Hanya akun Customer yang dapat melihat konfirmasi ini.')
    repair = get_object_or_404(
        RepairRequest.objects.select_related('mitra'), pk=pk, customer=request.user,
    )
    return render(request, 'repair/request_confirmation.html', {'repair': repair})
