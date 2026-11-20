from django.urls import path

from . import views

app_name = 'mobile_api'

urlpatterns = [
    path('auth/csrf/', views.csrf_token, name='csrf'),
    path('auth/login/', views.LoginView.as_view(), name='login'),
    path('auth/me/', views.me, name='me'),
    path('auth/logout/', views.sign_out, name='logout'),
]
