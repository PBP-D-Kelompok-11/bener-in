from django.urls import path

from . import views

app_name = 'reviews'

urlpatterns = [
    path('', views.my_reviews, name='mine'),
    path('impact/', views.impact_dashboard, name='impact'),
    path('repair/<int:repair_id>/new/', views.review_create, name='create'),
    path('<int:pk>/edit/', views.review_edit, name='edit'),
    path('<int:pk>/delete/', views.review_delete, name='delete'),
    path('mitra/', views.mitra_own_reviews, name='mitra_own'),
    path('mitra/<int:mitra_id>/', views.mitra_reviews, name='mitra'),
]