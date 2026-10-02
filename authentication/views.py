from django.contrib.auth import login
from django.shortcuts import redirect, render

from .forms import CustomerRegisterForm, MitraRegisterForm


def register_choice(request):
    return render(request, 'authentication/register_choice.html')


def _register(request, form_class, backend, template):
    if request.user.is_authenticated:
        return redirect('/')
    form = form_class(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        login(request, user, backend=backend)
        return redirect('/')
    return render(request, template, {'form': form})


def register_customer(request):
    return _register(request, CustomerRegisterForm,
                     'authentication.backends.CustomerBackend',
                     'authentication/register_customer.html')


def register_mitra(request):
    return _register(request, MitraRegisterForm,
                     'authentication.backends.MitraBackend',
                     'authentication/register_mitra.html')