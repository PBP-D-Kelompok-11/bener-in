from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from authentication.models import Customer

from .forms import MitraForm
from .models import Mitra


def get_mitra_list(request):
    mitra_list = Mitra.objects.all().values('id', 'nama_toko', 'layanan', 'alamat', 'kontak')
    return JsonResponse(list(mitra_list), safe=False)


def mitra_list_view(request):
    mitra_list = Mitra.objects.all()
    return render(request, 'mitra/mitra_list.html', {'mitra_list': mitra_list})


def _current_mitra_profile(request):
    """Return the legacy profile owned by the signed-in mitra account."""
    if getattr(request.user, 'role', None) != 'mitra':
        return None
    owner = Customer.objects.filter(username=request.user.username).first()
    if owner is None:
        return None
    return Mitra.objects.filter(user=owner).first()


@login_required
def mitra_profile(request):
    if getattr(request.user, 'role', None) != 'mitra':
        return HttpResponseForbidden('Hanya akun Mitra yang dapat melihat profil ini.')
    profile = _current_mitra_profile(request)
    return render(request, 'mitra/mitra_profile.html', {
        'user_mitra_list': [profile] if profile else [],
    })


@login_required
def create_mitra(request):
    if getattr(request.user, 'role', None) != 'mitra':
        return HttpResponseForbidden('Hanya akun Mitra yang dapat mengelola profil ini.')
    existing_mitra = _current_mitra_profile(request)
    if request.method == 'POST':
        form = MitraForm(request.POST, instance=existing_mitra)
        if form.is_valid():
            profile = form.save(commit=False)
            if existing_mitra is None:
                owner = Customer.objects.filter(username=request.user.username).first()
                if owner is None:
                    return HttpResponseForbidden('Profil akun Mitra tidak ditemukan.')
                profile.user = owner
            profile.save()
            return redirect('mitra:mitra_profile')
    else:
        form = MitraForm(instance=existing_mitra)

    title = 'Edit Profil Mitra' if existing_mitra else 'Pendaftaran Mitra Baru'
    return render(request, 'mitra/mitra_form.html', {'form': form, 'title': title})


@login_required
def update_mitra(request, id):
    if getattr(request.user, 'role', None) != 'mitra':
        return HttpResponseForbidden('Hanya akun Mitra yang dapat mengelola profil ini.')
    profile = get_object_or_404(Mitra, pk=id)
    if profile.user.username != request.user.username:
        return HttpResponseForbidden('Kamu hanya dapat mengubah profil milikmu.')
    return create_mitra(request)


@login_required
@require_POST
def delete_mitra(request, id):
    if getattr(request.user, 'role', None) != 'mitra':
        return HttpResponseForbidden('Hanya akun Mitra yang dapat mengelola profil ini.')
    profile = get_object_or_404(Mitra, pk=id)
    if profile.user.username != request.user.username:
        return HttpResponseForbidden('Kamu hanya dapat menghapus profil milikmu.')
    profile.delete()
    return redirect('mitra:mitra_profile')
