from django.urls import path

from . import api

app_name = 'locations'

urlpatterns = [
    path('api/places/', api.places_api, name='api_places'),
    path('api/mitra/', api.mitra_api, name='api_mitra'),
]
