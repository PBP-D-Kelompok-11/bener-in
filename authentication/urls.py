from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path

from . import views

app_name = 'authentication'

urlpatterns = [
    path('register/', views.register_choice, name='register'),
    path('register/customer/', views.register_customer, name='register_customer'),
    path('register/mitra/', views.register_mitra, name='register_mitra'),
    path('login/', LoginView.as_view(template_name='authentication/login.html',
                                     redirect_authenticated_user=True), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
]