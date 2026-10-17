from uuid import uuid4

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import Count, OuterRef, Q, Subquery
from django.http import (
    HttpResponseForbidden, HttpResponseNotAllowed, HttpResponseRedirect, JsonResponse,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse

from authentication.models import Customer, KategoriBarang, MitraReparasi

from .forms import MitraTransitionForm, RepairRequestCreateForm, RepairRequestEditForm
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

MITRA_GROUPS = {
    'incoming': (RepairRequest.Status.PENDING,),
    'active': (RepairRequest.Status.ACCEPTED, RepairRequest.Status.IN_PROGRESS),
    'history': (
        RepairRequest.Status.COMPLETED, RepairRequest.Status.REJECTED,
        RepairRequest.Status.CANCELLED, RepairRequest.Status.UNABLE_TO_REPAIR,
    ),
}


def _is_ajax(request):
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest'


def _mitra_dashboard_context(request):
    group = request.GET.get('group', 'incoming')
    if group not in MITRA_GROUPS:
        group = 'incoming'
    category = request.GET.get('category', '')
    if category not in KategoriBarang.values:
        category = ''
    status = request.GET.get('status', '')
    if status not in RepairRequest.Status.values:
        status = ''
    search = request.GET.get('q', '').strip()

    assigned = RepairRequest.objects.filter(mitra=request.user)
    by_status = {
        row['status']: row['total']
        for row in assigned.values('status').annotate(total=Count('pk'))
    }
    counts = {
        key: sum(by_status.get(value, 0) for value in statuses)
        for key, statuses in MITRA_GROUPS.items()
    }
    repairs = assigned.filter(status__in=MITRA_GROUPS[group]).select_related('customer')
    if category:
        repairs = repairs.filter(category=category)
    if status:
        repairs = repairs.filter(status=status)
    if search:
        repairs = repairs.filter(
            Q(item_name__icontains=search)
            | Q(description__icontains=search)
            | Q(customer__nama_lengkap__icontains=search)
            | Q(customer__username__icontains=search)
        )
    repairs = repairs.order_by('-created_at', '-pk')
    return {
        'repairs': repairs,
        'result_count': repairs.count(),
        'counts': counts,
        'group': group,
        'category_filter': category,
        'status_filter': status,
        'search_query': search,
        'category_choices': KategoriBarang.choices,
        'status_choices': RepairRequest.Status.choices,
        'filter_query': request.GET.urlencode(),
    }


@login_required
def mitra_dashboard(request):
    if not _mitra_allowed(request):
        return HttpResponseForbidden('Hanya akun Mitra yang dapat melihat permintaan masuk.')
    if request.method != 'GET':
        return HttpResponseNotAllowed(['GET'])
    context = _mitra_dashboard_context(request)
    template = 'repair/_mitra_results.html' if _is_ajax(request) else 'repair/mitra_dashboard.html'
    return render(request, template, context)


def _mitra_action_response(request, status_code, message, *, errors=None, event=None, repair=None):
    if _is_ajax(request):
        if event is None:
            return JsonResponse({'ok': False, 'error': message, 'errors': errors or {}}, status=status_code)
        context = _mitra_dashboard_context(request)
        return JsonResponse({
            'ok': True,
            'message': message,
            'request': {
                'id': repair.pk,
                'status': repair.status,
                'status_label': repair.get_status_display(),
            },
            'event': {
                'id': event.pk,
                'from_status': event.from_status,
                'to_status': event.to_status,
                'occurred_at': event.occurred_at.isoformat(),
                'reason': event.reason,
                'actor': request.user.nama_usaha,
            },
            'counts': context['counts'],
            'results_html': render_to_string('repair/_mitra_results.html', context, request=request),
        })
    if status_code == 200:
        messages.success(request, message)
    else:
        messages.error(request, message)
    destination = reverse('repair:incoming')
    if request.GET:
        destination += '?' + request.GET.urlencode()
    return HttpResponseRedirect(destination)


@login_required
def mitra_transition(request, pk):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    if not _mitra_allowed(request):
        return _mitra_action_response(request, 403, 'Hanya mitra yang dituju dapat mengubah status.')
    repair = RepairRequest.objects.filter(pk=pk, mitra=request.user).first()
    if repair is None:
        return _mitra_action_response(request, 404, 'Permintaan ini tidak tersedia untuk akun Anda.')

    form = MitraTransitionForm(request.POST)
    if not form.is_valid():
        errors = {field: list(values) for field, values in form.errors.items()}
        message = next(iter(form.errors.values()))[0]
        return _mitra_action_response(request, 400, message, errors=errors)
    target = form.cleaned_data['to_status']
    expected = form.cleaned_data['expected_status']
    if repair.status != expected:
        return _mitra_action_response(request, 409, 'Status permintaan telah berubah. Muat ulang daftar sebelum mencoba lagi.')
    if RepairRequest.TRANSITIONS.get(expected, {}).get(target) != 'mitra':
        return _mitra_action_response(request, 400, 'Perubahan status ini tidak diizinkan.')
    if target in RepairRequest.REASON_REQUIRED and not form.cleaned_data['reason']:
        message = 'Alasan wajib diisi untuk keputusan ini.'
        return _mitra_action_response(request, 400, message, errors={'reason': [message]})
    try:
        event = repair.transition_to(target, request.user, reason=form.cleaned_data['reason'])
    except ValidationError:
        repair.refresh_from_db()
        if repair.status != expected:
            return _mitra_action_response(request, 409, 'Status permintaan telah berubah. Muat ulang daftar sebelum mencoba lagi.')
        return _mitra_action_response(request, 400, 'Perubahan status tidak valid. Periksa isian dan coba lagi.')
    return _mitra_action_response(request, 200, 'Status permintaan berhasil diperbarui.', event=event, repair=repair)


@login_required
def request_list(request):
    if not _customer_allowed(request):
        return HttpResponseForbidden('Hanya akun Customer yang dapat melihat daftar permintaan.')
    if request.method != 'GET':
        return HttpResponseNotAllowed(['GET'])

    status_filter = request.GET.get('status', '')
    if status_filter not in RepairRequest.Status.values:
        status_filter = ''
    category_filter = request.GET.get('category', '')
    if category_filter not in KategoriBarang.values:
        category_filter = ''
    search_query = request.GET.get('q', '').strip()
    owned = RepairRequest.objects.filter(customer=request.user)
    latest_event = RepairStatusHistory.objects.filter(
        request_id=OuterRef('pk'),
    ).order_by('-pk')
    repairs = owned.select_related('mitra').annotate(
        last_status_at=Subquery(latest_event.values('occurred_at')[:1]),
    )
    if status_filter:
        repairs = repairs.filter(status=status_filter)
    if category_filter:
        repairs = repairs.filter(category=category_filter)
    if search_query:
        repairs = repairs.filter(
            Q(item_name__icontains=search_query)
            | Q(description__icontains=search_query)
            | Q(mitra__nama_usaha__icontains=search_query)
        )
    repairs = repairs.order_by('-created_at', '-pk')
    return render(request, 'repair/_customer_results.html' if _is_ajax(request) else 'repair/request_list.html', {
        'repairs': repairs,
        'result_count': repairs.count(),
        'has_any_requests': owned.exists(),
        'status_filter': status_filter,
        'category_filter': category_filter,
        'search_query': search_query,
        'status_choices': RepairRequest.Status.choices,
        'category_choices': KategoriBarang.choices,
        'selected_filter_label': dict(RepairRequest.Status.choices).get(status_filter),
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
