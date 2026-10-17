from django.urls import path
from .views import get_mitra_list

app_name = 'mitra'

urlpatterns = [
    path('api/list/', get_mitra_list, name='get_mitra_list'),
]