from django.shortcuts import render
from django.http import JsonResponse
from .models import Mitra

def get_mitra_list(request):
    mitra_list = Mitra.objects.all().values('id', 'nama_toko', 'layanan', 'alamat', 'kontak')
    return JsonResponse(list(mitra_list), safe=False)