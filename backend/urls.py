from django.urls import path
from . import views


urlpatterns = [
    path('', views.HomeView.as_view(), name='home'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('profile/', views.profile_view, name='profile'),
    path('health/', views.health_check, name='health_check'),
    
    # CP-ABE API endpoints
    path('api/abe/secret-key/', views.get_user_secret_key, name='get_user_secret_key'),
    path('api/abe/public-key/', views.get_public_parameters, name='get_public_parameters'),
    path('api/abe/session-key/', views.get_session_secret_key, name='get_session_secret_key'),
]