from django.urls import path

from . import views

app_name = 'repair'

urlpatterns = [
    path('', views.request_list, name='list'),
    path('new/', views.create_request, name='create'),
    path('submitted/<int:pk>/', views.request_confirmation, name='confirmation'),
    path('incoming/', views.mitra_dashboard, name='incoming'),
    path('incoming/<int:pk>/transition/', views.mitra_transition, name='mitra_transition'),
    path('<int:pk>/', views.request_detail, name='detail'),
    path('<int:pk>/edit/', views.edit_request, name='edit'),
    path('<int:pk>/cancel/', views.cancel_request, name='cancel'),
]
