from django.urls import path

from . import views

app_name = 'mobile_api'

urlpatterns = [
    path('auth/csrf/', views.csrf_token, name='csrf'),
    path('auth/login/', views.LoginView.as_view(), name='login'),
    path('auth/me/', views.me, name='me'),
    path('auth/logout/', views.sign_out, name='logout'),
    path('repairs/', views.repair_list, name='repairs'),
    path('mitra/<int:pk>/', views.mitra_detail, name='mitra-detail'),
    path('locations/mitra/', views.mitra_nearby, name='mitra-nearby'),
    path('impact/', views.impact_summary, name='impact'),
]
