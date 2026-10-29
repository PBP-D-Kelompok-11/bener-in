from django.contrib.auth import login
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
        user = form.save()
        login(request, user, backend=backend)

        if is_mitra:
            customer_instance, _ = Customer.objects.get_or_create(
                username=user.username,
                defaults={'email': getattr(user, 'email', '')}
            )

            nama_toko_input = form.cleaned_data.get('nama_usaha') or getattr(user, 'nama_usaha', f"Toko {user.username}")
            kontak_input = form.cleaned_data.get('no_hp') or form.cleaned_data.get('kontak') or getattr(user, 'no_hp', '')
            alamat_input = form.cleaned_data.get('alamat') or "Belum diatur"

            layanan_input = form.cleaned_data.get('layanan') or form.cleaned_data.get('layanan_dikerjakan')
            if isinstance(layanan_input, list):
                layanan_input = ", ".join(layanan_input)
            elif not layanan_input:
                layanan_input = "Layanan Reparasi"

            Mitra.objects.get_or_create(
                user=customer_instance,
                defaults={
                    'nama_toko': nama_toko_input,
                    'layanan': layanan_input,
                    'alamat': alamat_input,
                    'kontak': kontak_input
                }
            )
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