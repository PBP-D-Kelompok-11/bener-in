from django.urls import path
from .views import (
    get_mitra_list,
    mitra_list_view,
    create_mitra,
    update_mitra,
    delete_mitra,
    mitra_profile,
)

app_name = 'mitra'

urlpatterns = [
    path('', mitra_list_view, name='mitra_list'),
    path('profile/', mitra_profile, name='mitra_profile'),  # <--- TAMBAHKAN BARIS INI!
    path('api/list/', get_mitra_list, name='get_mitra_list'),
    path('add/', create_mitra, name='create_mitra'),
    path('edit/<int:id>/', update_mitra, name='update_mitra'),
    path('delete/<int:id>/', delete_mitra, name='delete_mitra'),
]