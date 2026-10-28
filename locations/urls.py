from django.urls import path

from . import api, views

app_name = 'locations'

urlpatterns = [
    path('', views.discover, name='discover'),
    path('api/places/', api.places_api, name='api_places'),
    path('api/mitra/', api.mitra_api, name='api_mitra'),
    path('api/reverse/', api.reverse_api, name='api_reverse'),
    path('saved/', views.saved_list, name='saved'),
    path('saved/create/', views.saved_create, name='saved_create'),
    path('saved/<int:pk>/edit/', views.saved_edit, name='saved_edit'),
    path('saved/<int:pk>/delete/', views.saved_delete, name='saved_delete'),
    path('saved/<int:pk>/restore/', views.saved_restore, name='saved_restore'),
]
