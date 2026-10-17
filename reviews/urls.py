from django.urls import path

from . import views

app_name = 'reviews'

urlpatterns = [
    path('impact/', views.impact_dashboard, name='impact'),
]