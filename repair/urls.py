from django.urls import path

from . import views

app_name = 'repair'

urlpatterns = [
    path('new/', views.create_request, name='create'),
    path('submitted/<int:pk>/', views.request_confirmation, name='confirmation'),
]
