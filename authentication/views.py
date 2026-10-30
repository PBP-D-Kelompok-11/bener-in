from django.contrib.auth import login
from django.db import transaction
from django.shortcuts import redirect, render
from mitra.models import Mitra
from authentication.models import Customer

from .forms import CustomerRegisterForm, MitraRegisterForm


def register_choice(request):
    return render(request, 'authentication/register_choice.html')


def _register(request, form_class, backend, template, is_mitra=False):
    if request.user.is_authenticated:
        return redirect('/')
    form = form_class(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            user = form.save()
            if is_mitra:
                # The legacy Mitra profile still points at AUTH_USER_MODEL (Customer).
                # Populate its required identity fields until that model is consolidated.
                customer_instance, _ = Customer.objects.get_or_create(
                    username=user.username,
                    defaults={
                        'email': user.email,
                        'nama_lengkap': user.nama_lengkap,
                        'no_hp': user.no_hp,
                        'alamat': form.cleaned_data['alamat'],
                    },
                )
                layanan = form.cleaned_data.get('layanan') or []
                Mitra.objects.get_or_create(
                    user=customer_instance,
                    defaults={
                        'nama_toko': user.nama_usaha,
                        'layanan': ', '.join(layanan) or 'Layanan Reparasi',
                        'alamat': form.cleaned_data['alamat'],
                        'kontak': user.no_hp,
                    },
                )

        login(request, user, backend=backend)
        if is_mitra:
            return redirect('mitra:mitra_profile')

        return redirect('/')
    return render(request, template, {'form': form})


def register_customer(request):
    return _register(
        request,
        CustomerRegisterForm,
        'authentication.backends.CustomerBackend',
        'authentication/register_customer.html',
        is_mitra=False
    )


def register_mitra(request):
    return _register(
        request,
        MitraRegisterForm,
        'authentication.backends.MitraBackend',
        'authentication/register_mitra.html',
        is_mitra=True
    )
