from uuid import uuid4

from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from authentication.models import Customer, KategoriBarang, MitraReparasi

from .forms import RepairRequestCreateForm
from .models import RepairRequest


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
