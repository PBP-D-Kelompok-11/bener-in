from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from .models import Mitra
from .forms import MitraForm

# Read (API List untuk JSON)
def get_mitra_list(request):
    mitra_list = Mitra.objects.all().values('id', 'nama_toko', 'layanan', 'alamat', 'kontak')
    return JsonResponse(list(mitra_list), safe=False)

# Read (Halaman Daftar Mitra)
def mitra_list_view(request):
    mitra_list = Mitra.objects.all()
    return render(request, 'mitra/mitra_list.html', {'mitra_list': mitra_list})

# Create (Tambah Profil Mitra)
@login_required
def create_mitra(request):
    if request.method == 'POST':
        form = MitraForm(request.POST)
        if form.is_valid():
            mitra = form.save(commit=False)
            mitra.user = request.user
            mitra.save()
            return redirect('mitra:mitra_list')
    else:
        form = MitraForm()
    return render(request, 'mitra/mitra_form.html', {'form': form, 'title': 'Pendaftaran Mitra Baru'})

# Update (Edit Profil Mitra)
@login_required
def update_mitra(request, id):
    mitra = get_object_or_404(Mitra, id=id)
    if request.method == 'POST':
        form = MitraForm(request.POST, instance=mitra)
        if form.is_valid():
            form.save()
            return redirect('mitra:mitra_list')
    else:
        form = MitraForm(instance=mitra)
    return render(request, 'mitra/mitra_form.html', {'form': form, 'title': 'Edit Profil Mitra'})

# Delete (Hapus Profil Mitra)
@login_required
def delete_mitra(request, id):
    mitra = get_object_or_404(Mitra, id=id)
    if request.method == 'POST':
        mitra.delete()
        return redirect('mitra:mitra_list')
    return render(request, 'mitra/mitra_confirm_delete.html', {'mitra': mitra})

@login_required
def mitra_profile(request):
    # Ambil data toko mitra yang CUMA dimiliki oleh user yang lagi login
    user_mitra_list = Mitra.objects.filter(user=request.user)
    
    context = {
        'user_mitra_list': user_mitra_list,
    }
    return render(request, 'mitra/mitra_profile.html', context)