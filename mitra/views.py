from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from .models import Mitra
from .forms import MitraForm
from authentication.models import Customer

def get_mitra_list(request):
    mitra_list = Mitra.objects.all().values('id', 'nama_toko', 'layanan', 'alamat', 'kontak')
    return JsonResponse(list(mitra_list), safe=False)

def mitra_list_view(request):
    mitra_list = Mitra.objects.all()
    return render(request, 'mitra/mitra_list.html', {'mitra_list': mitra_list})

@login_required
def mitra_profile(request):
    user_mitra_list = []
    
    customer_instance = None
    if isinstance(request.user, Customer):
        customer_instance = request.user
    elif hasattr(request.user, 'customer'):
        customer_instance = request.user.customer
    else:
        customer_instance = Customer.objects.filter(username=request.user.username).first()

    if customer_instance:
        user_mitra_list = Mitra.objects.filter(user=customer_instance)

    context = {
        'user_mitra_list': user_mitra_list,
    }
    return render(request, 'mitra/mitra_profile.html', context)

@login_required
def create_mitra(request):
    customer_instance = None
    if isinstance(request.user, Customer):
        customer_instance = request.user
    elif hasattr(request.user, 'customer'):
        customer_instance = request.user.customer
    else:
        customer_instance = Customer.objects.filter(username=request.user.username).first()

    existing_mitra = None
    if customer_instance:
        existing_mitra = Mitra.objects.filter(user=customer_instance).first()

    if request.method == 'POST':
        form = MitraForm(request.POST, instance=existing_mitra) if existing_mitra else MitraForm(request.POST)
        if form.is_valid():
            mitra = form.save(commit=False)
            
            if not customer_instance:
                customer_instance, _ = Customer.objects.get_or_create(
                    username=request.user.username,
                    defaults={'email': getattr(request.user, 'email', '')}
                )
            
            mitra.user = customer_instance
            mitra.save()
            return redirect('mitra:mitra_profile')
    else:
        form = MitraForm(instance=existing_mitra) if existing_mitra else MitraForm()
        
    title = 'Edit Profil Mitra' if existing_mitra else 'Pendaftaran Mitra Baru'
    return render(request, 'mitra/mitra_form.html', {'form': form, 'title': title})

@login_required
def update_mitra(request, id):
    return create_mitra(request)

@login_required
def delete_mitra(request, id):
    return redirect('mitra:mitra_profile')